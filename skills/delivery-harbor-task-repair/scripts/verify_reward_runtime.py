#!/usr/bin/env python3
"""Ground truth: run each task's verifier on an empty workspace and record the exact
string written to reward.txt.

Regex cannot keep up with the shapes a binarizing fix can take (inline guard, helper
function, shell literal). Execution can. A binarized writer emits exactly "0"; an
un-binarized one emits "0.0", "0.0000", "0.058824" and so on — the string form is the
tell. This also catches a fix that is inert because the image bakes a stale mirror.
"""
import concurrent.futures as cf, json, re, subprocess, sys
from pathlib import Path

W = Path.home() / "harbor_gce/harbor-autofix-20260918-152639"
tasks = sorted(p for p in (W / "work").iterdir() if (p / "environment/Dockerfile").exists())


def dk(*a, **k):
    return subprocess.run(["sudo", "docker", *a], capture_output=True, text=True, **k)


def one(t: Path) -> dict:
    tag = "rv/" + re.sub(r"[^a-z0-9]+$", "", t.name.lower()[:40])
    b = dk("build", "-q", "-f", str(t / "environment/Dockerfile"), "-t", tag + ":v",
           str(t / "environment"), timeout=1800)
    if b.returncode:
        return {"task": t.name, "built": False, "reward": None, "note": "build failed"}
    r = dk("run", "-d", tag + ":v", "sleep", "300", timeout=120)
    if r.returncode:
        return {"task": t.name, "built": True, "reward": None, "note": "run failed"}
    cid = r.stdout.strip()
    try:
        dk("exec", "-u", "0", cid, "mkdir", "-p", "/tests", "/logs/verifier", timeout=60)
        # Harbor injects [verifier.env] during the verifier phase. Without it, an
        # LLM-judge task hits its infrastructure guard and deliberately writes NO
        # reward rather than scoring an ungraded run as 0 — which reads as a false
        # "no reward" for every judge task in the corpus.
        venv = []
        toml = (t / "task.toml")
        if toml.exists():
            blk = re.search(r"\[verifier\.env\]([^\[]*)", toml.read_text(errors="replace"))
            for k, v in re.findall(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*\"([^\"]*)\"", blk.group(1) if blk else "", re.M):
                v = re.sub(r"\$\{(\w+)(:-[^}]*)?\}", lambda m: __import__("os").environ.get(m.group(1), ""), v)
                if v:
                    venv += ["-e", f"{k}={v}"]
        subprocess.run(["bash", "-c", f"sudo docker cp {t}/tests/. {cid}:/tests/"],
                       capture_output=True, text=True, timeout=300)
        dk("exec", "-u", "0", *venv, cid, "bash", "/tests/test.sh", timeout=900)
        got = dk("exec", "-u", "0", cid, "cat", "/logs/verifier/reward.txt", timeout=60).stdout.strip()
        return {"task": t.name, "built": True, "reward": got,
                "binary": got in ("0", "1"), "note": ""}
    finally:
        dk("rm", "-f", cid, timeout=120)


res = []
with cf.ThreadPoolExecutor(max_workers=16) as ex:
    futs = {ex.submit(one, t): t for t in tasks}
    for i, f in enumerate(cf.as_completed(futs), 1):
        try:
            res.append(f.result())
        except Exception as e:
            res.append({"task": futs[f].name, "built": None, "reward": None,
                        "binary": False, "note": str(e)[:120]})
        if i % 25 == 0:
            print(f"  {i}/{len(tasks)}", flush=True)

res.sort(key=lambda r: r["task"])
(W / "reports/reward_runtime.json").write_text(json.dumps(res, indent=1) + "\n")
ok = [r for r in res if r.get("binary")]
frac = [r for r in res if r.get("reward") and not r.get("binary")]
none = [r for r in res if r.get("reward") in (None, "")]
print(f"\nexact 0/1 : {len(ok)}/{len(res)}")
print(f"fractional: {len(frac)}")
print(f"no reward : {len(none)}")
for r in frac[:25]:
    print(f"   FRAC {r['task'][:54]:54s} {r['reward']!r}")
for r in none[:15]:
    print(f"   NONE {r['task'][:54]:54s} {r.get('note','')[:40]}")
