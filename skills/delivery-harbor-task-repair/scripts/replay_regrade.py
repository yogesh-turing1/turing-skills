#!/usr/bin/env python3
"""Rebuild a model run's workspace from its trajectory, then re-grade it N times.

Stability re-grades one frozen answer repeatedly and requires the score never to move. When a
package retained no workspace artifacts (artifacts/manifest.json is "empty"), the answer is
reconstructed by replaying the trajectory's own tool calls in a fresh container built from the
task's Dockerfile.

This script PROVES reproduction; it does not write stability evidence. It exits 0 only when:
  - the source run recorded reward exactly 1 (stability needs a passing source - a reward-0 run
    that is replayed badly also grades 0 and would "reproduce" for the wrong reason),
  - every tool call that changes the workspace was replayed (anything it cannot replay - e.g.
    patch / apply_patch / unknown tools - makes it refuse unless --allow-skip is given),
  - the rebuilt workspace grades to the SAME reward the original recorded, and
  - every repeat grades identically.
Writing the repeats in the format infra validates (repeat-01..05, source_trial bound to
evaluations/solvability/r1, agent/frozen_trajectory.json with its sha256, per-check verdicts)
is infra's harbor_gce/stability.py job - use that once this proof passes.

Before using this on an Oracle-frozen stability finding, check whether the existing repeats
still bind: recompute package_evidence.oracle_replay_digest(evaluations/solvability/r1) (infra
harbor_gce/package_evidence.py). If it matches the repeats' declared digest, the evidence is
valid and only the frozen artifact needs restoring - no replay is needed.

    python3 replay_regrade.py <task-dir> <source-trial-rel> [--repeats 5] [--network none]
                              [--allow-skip] [--keep]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_reward_binary import judge, verifier_env  # noqa: E402

# Tools that cannot change the graded workspace. `task` (a subagent) is NOT here: its own tool calls are
# not in this trajectory, so a run that used subagents cannot be fully replayed.
READ_ONLY = {"read", "glob", "grep", "list", "ls", "view", "webfetch", "websearch", "todowrite", "todoread"}


def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def dk(*args, **kw):
    return sh("docker", *args, **kw)


def recorded_reward(res: dict):
    r = ((res.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    if r is None:
        r = res.get("reward")
    if isinstance(r, bool) or not isinstance(r, (int, float)):
        return None
    return float(r)


def write_file(cid: str, path: str, content) -> bool:
    if not isinstance(content, str):
        # ATIF recorders sometimes store JSON file content as a parsed object
        content = json.dumps(content, indent=2)
    if dk("exec", cid, "mkdir", "-p", str(Path(path).parent)).returncode:
        return False
    proc = subprocess.run(["docker", "exec", "-i", cid, "bash", "-c", f"cat > {path!r}"],
                          input=content, capture_output=True, text=True)
    return proc.returncode == 0


def edit_file(cid: str, path: str, old: str, new: str, replace_all: bool = False) -> str:
    payload = json.dumps({"p": path, "o": old, "n": new, "a": replace_all})
    code = ("import json,sys;d=json.load(sys.stdin);s=open(d['p']).read();"
            "assert d['o'] in s, 'oldString not found';"
            "open(d['p'],'w').write(s.replace(d['o'],d['n']) if d['a'] else s.replace(d['o'],d['n'],1))")
    proc = subprocess.run(["docker", "exec", "-i", cid, "python3", "-c", code],
                          input=payload, capture_output=True, text=True)
    return "" if proc.returncode == 0 else (proc.stderr.strip()[:200] or "edit failed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task")
    ap.add_argument("trial", help="e.g. evaluations/difficulty/r3 (a reward-1 model run)")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--network", default="none", help="docker --network for the replay container (default none)")
    ap.add_argument("--allow-skip", action="store_true", help="continue even if some tool calls cannot be replayed")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.apply:
        print("--apply is not supported: this script only proves reproduction. Write the stability repeats "
              "with infra's harbor_gce/stability.py once this check passes.")
        return 2

    task = Path(a.task).resolve()
    trial = task / a.trial
    traj = json.loads((trial / "agent" / "trajectory.json").read_text())
    res = json.loads((trial / "result.json").read_text())
    want = recorded_reward(res)
    name = re.sub(r"[^a-z0-9]+", "-", task.name.lower())[:40].strip("-")
    tag = f"regrade/{name}:latest"
    cid = None

    print(f"task   {task.name}\ntrial  {a.trial}\nreward to reproduce: {want}")
    if want != 1.0:
        print("REFUSED: the source run did not record reward exactly 1. Stability needs a passing source; "
              "a reward-0 source would 'reproduce' even when the replay rebuilt nothing.")
        return 6

    print("\n[1/4] building image")
    b = dk("build", "-q", "-f", str(task / "environment" / "Dockerfile"), "-t", tag, str(task / "environment"))
    if b.returncode:
        print("BUILD FAILED\n" + b.stderr[-2000:])
        return 2
    print("      ok")

    print("[2/4] replaying trajectory")
    r = dk("run", "-d", "--network", a.network, tag, "sleep", "infinity")
    if r.returncode:
        print("RUN FAILED\n" + r.stderr[-1000:])
        return 2
    cid = r.stdout.strip()
    try:
        counts = {"bash": 0, "bash_nonzero": 0, "write": 0, "edit": 0, "read_only": 0}
        skipped = []
        for step in traj.get("steps", []):
            for tc in (step.get("tool_calls") or []):
                fn = (tc.get("function_name") or "").lower()
                arg = tc.get("arguments") or {}
                if fn == "bash":
                    c = dk("exec", cid, "bash", "-lc", arg.get("command", ""))
                    counts["bash"] += 1
                    counts["bash_nonzero"] += c.returncode != 0
                elif fn == "write":
                    p = arg.get("filePath") or arg.get("file_path") or arg.get("path")
                    if not p or not write_file(cid, p, arg.get("content", "")):
                        print(f"      WRITE FAILED on {p}")
                        return 3
                    counts["write"] += 1
                elif fn == "edit":
                    p = arg.get("filePath") or arg.get("file_path") or arg.get("path")
                    err = edit_file(cid, p, arg.get("oldString", arg.get("old_string", "")),
                                    arg.get("newString", arg.get("new_string", "")),
                                    bool(arg.get("replaceAll", arg.get("replace_all", False))))
                    if err:
                        print(f"      EDIT FAILED on {p}: {err}")
                        return 3
                    counts["edit"] += 1
                elif fn == "multiedit":
                    p = arg.get("filePath") or arg.get("file_path") or arg.get("path")
                    for e in arg.get("edits") or []:
                        err = edit_file(cid, p, e.get("oldString", e.get("old_string", "")),
                                        e.get("newString", e.get("new_string", "")),
                                        bool(e.get("replaceAll", e.get("replace_all", False))))
                        if err:
                            print(f"      MULTIEDIT FAILED on {p}: {err}")
                            return 3
                        counts["edit"] += 1
                elif fn in READ_ONLY or fn.startswith(("read", "list", "search", "get")):
                    counts["read_only"] += 1
                else:
                    skipped.append(fn or "?")
        print(f"      {counts}  not replayable: {len(skipped)} {sorted(set(skipped))}")
        if counts["bash_nonzero"]:
            print(f"      note: {counts['bash_nonzero']} bash call(s) exited non-zero (often benign; the grade below decides)")
        if skipped and not a.allow_skip:
            print("REFUSED: some tool calls could not be replayed, so the rebuilt workspace may be incomplete. "
                  "Re-run with --allow-skip only if those calls cannot change the graded workspace.")
            return 7

        print("[3/4] grading rebuilt workspace")
        env = verifier_env(task)
        dk("exec", "-u", "0", cid, "mkdir", "-p", "/tests", "/logs/verifier")
        sh("docker", "cp", f"{task}/tests/.", f"{cid}:/tests/")
        rewards = []
        for i in range(a.repeats + 1):
            dk("exec", "-u", "0", cid, "rm", "-rf", "/logs/verifier")
            dk("exec", "-u", "0", cid, "mkdir", "-p", "/logs/verifier")
            dk("exec", "-u", "0", *env, cid, "bash", "/tests/test.sh")
            txt = dk("exec", "-u", "0", cid, "cat", "/logs/verifier/reward.txt").stdout.strip()
            jsn = dk("exec", "-u", "0", cid, "cat", "/logs/verifier/reward.json").stdout.strip()
            got, problems = judge(txt, jsn)
            rewards.append(got)
            label = "verify" if i == 0 else f"repeat-{i:02d}"
            print(f"      {label}: reward={got!r}" + (f"  problems={problems}" if problems else ""))
            if i == 0 and (problems or got is None or float(got) != want):
                print(f"\nMISMATCH: rebuilt workspace scores {got!r}, original scored {want}")
                print("Replay did not reproduce the graded answer. Refusing to treat it as stable.")
                return 4
        stable = len(set(rewards)) == 1
        print(f"\n[4/4] {a.repeats} repeats, all equal: {stable}  values={sorted(set(map(str, rewards)))}")
        return 0 if stable else 5
    finally:
        if cid and not a.keep:
            dk("rm", "-f", cid)


if __name__ == "__main__":
    sys.exit(main())
