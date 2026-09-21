#!/usr/bin/env python3
"""Rebuild a model run's workspace from its trajectory, then re-grade it N times.

Stability re-grades one frozen answer repeatedly and requires the score never to move.
These packages retained no workspace artifacts (artifacts/manifest.json is "empty"), so the
answer is reconstructed by replaying the trajectory's own tool calls in a fresh container
built from the task's Dockerfile.

The replay is only trusted if the rebuilt workspace grades to the SAME reward the original
run recorded. If it does not, this refuses to write anything: a frozen answer that is not
the graded answer proves nothing.

    python3 replay_regrade.py <task-dir> <source-trial-rel> [--repeats 5] [--apply]
"""
import argparse, json, re, subprocess, sys, hashlib, shutil, tempfile, os
from pathlib import Path


def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def dk(*args, **kw):
    return sh("docker", *args, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("trial", help="e.g. evaluations/solvability/r2")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    task = Path(a.task).resolve()
    trial = task / a.trial
    traj = json.loads((trial / "agent" / "trajectory.json").read_text())
    res = json.loads((trial / "result.json").read_text())
    want = res.get("reward")
    if want is None:
        want = ((res.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    name = re.sub(r"[^a-z0-9]+$", "", task.name.lower()[:40].replace("_", "-"))
    tag = f"regrade/{name}:latest"
    cid = None

    print(f"task   {task.name}\ntrial  {a.trial}\nreward to reproduce: {want}")

    print("\n[1/4] building image")
    b = dk("build", "-q", "-f", str(task / "environment" / "Dockerfile"), "-t", tag,
           str(task / "environment"))
    if b.returncode:
        print("BUILD FAILED\n" + b.stderr[-2000:]); return 2
    print("      ok")

    print("[2/4] replaying trajectory")
    r = dk("run", "-d", "--network", "none", tag, "sleep", "infinity")
    if r.returncode:
        print("RUN FAILED\n" + r.stderr[-1000:]); return 2
    cid = r.stdout.strip()
    try:
        n_bash = n_write = n_edit = n_skip = 0
        for step in traj["steps"]:
            for tc in (step.get("tool_calls") or []):
                fn, arg = tc.get("function_name"), (tc.get("arguments") or {})
                if fn == "bash":
                    c = dk("exec", cid, "bash", "-lc", arg.get("command", ""))
                    n_bash += 1
                elif fn == "write":
                    p = arg["filePath"]
                    # ATIF recorders sometimes store JSON file content as a parsed
                    # object rather than literal text. subprocess input= needs a str,
                    # so re-serialise; otherwise the replay dies with
                    # AttributeError: 'dict' object has no attribute 'encode'
                    if not isinstance(arg.get("content"), str):
                        arg = dict(arg)
                        arg["content"] = json.dumps(arg.get("content"), indent=2)
                    dk("exec", cid, "mkdir", "-p", str(Path(p).parent))
                    proc = subprocess.run(
                        ["docker", "exec", "-i", cid, "bash", "-c", f"cat > {p!r}"],
                        input=arg.get("content", ""), capture_output=True, text=True)
                    n_write += 1
                elif fn == "edit":
                    payload = json.dumps({"p": arg["filePath"], "o": arg.get("oldString", ""),
                                          "n": arg.get("newString", "")})
                    code = ("import json,sys;d=json.load(sys.stdin);"
                            "s=open(d['p']).read();"
                            "assert d['o'] in s, 'oldString not found';"
                            "open(d['p'],'w').write(s.replace(d['o'],d['n'],1))")
                    proc = subprocess.run(["docker", "exec", "-i", cid, "python3", "-c", code],
                                          input=payload, capture_output=True, text=True)
                    if proc.returncode:
                        print(f"      EDIT FAILED on {arg['filePath']}: {proc.stderr.strip()[:200]}")
                        return 3
                    n_edit += 1
                else:
                    n_skip += 1
        print(f"      bash {n_bash}  write {n_write}  edit {n_edit}  skipped {n_skip}")

        print("[3/4] grading rebuilt workspace")
        dk("exec", "-u", "0", cid, "mkdir", "-p", "/tests", "/logs/verifier")
        sh("bash", "-c", f"docker cp {task}/tests/. {cid}:/tests/")  # root-owned via -u 0 mkdir above
        rewards = []
        for i in range(a.repeats + 1):
            dk("exec", "-u", "0", cid, "rm", "-rf", "/logs/verifier")
            dk("exec", "-u", "0", cid, "mkdir", "-p", "/logs/verifier")
            g = dk("exec", "-u", "0", cid, "bash", "/tests/test.sh")
            got = dk("exec", "-u", "0", cid, "cat", "/logs/verifier/reward.txt").stdout.strip()
            rewards.append(got)
            label = "verify" if i == 0 else f"repeat-{i:02d}"
            print(f"      {label}: reward={got}")
            if i == 0 and str(float(got or -1)) != str(float(want)):
                print(f"\nMISMATCH: rebuilt workspace scores {got}, original scored {want}")
                print("Replay did not reproduce the graded answer. Refusing to freeze it.")
                return 4
        stable = len(set(rewards)) == 1
        print(f"\n[4/4] {a.repeats} repeats, all equal: {stable}  values={sorted(set(rewards))}")
        return 0 if stable else 5
    finally:
        if cid and not a.keep:
            dk("rm", "-f", cid)


sys.exit(main())
