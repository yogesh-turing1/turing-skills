#!/usr/bin/env python3
"""Ground truth for a whole corpus: build each task's image, run its verifier on an empty
workspace, and record exactly what it wrote to reward.json and reward.txt.

Regex cannot keep up with the shapes a binarizing fix can take (inline guard, helper function,
shell literal). Execution can. Harbor reads reward.json first, so both files are read and
judged by the same rules as verify_reward_binary.py: a value is binary when it is the number
0 or 1 ("0", "1", "0.0" and "1.0" all qualify), reward.json values are all numeric, and the two
files agree. A float-formatted value ("0.0") is reported as a note, not a failure: on its own
it does not prove the writer is still fractional - only a non-0/1 value does.

This also catches a fix that is inert because the image bakes a stale mirror.

    sudo python3 verify_reward_runtime.py WORK_DIR [--report REPORT.json] [--workers 16] [--sudo]

WORK_DIR is a directory of task directories (each with environment/Dockerfile).
"""
import argparse
import concurrent.futures as cf
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_reward_binary import judge, verifier_env  # noqa: E402  same rules as the single-task check


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("work_dir", type=Path)
    ap.add_argument("--report", type=Path, help="where to write the JSON report (default: WORK_DIR/../reward_runtime.json)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--sudo", action="store_true", help="prefix docker with sudo")
    a = ap.parse_args()
    work = a.work_dir.resolve()
    tasks = sorted(p for p in work.iterdir() if (p / "environment/Dockerfile").exists())
    report = a.report or (work.parent / "reward_runtime.json")
    docker = (["sudo"] if a.sudo else []) + ["docker"]

    def dk(*args, **kw):
        return subprocess.run([*docker, *args], capture_output=True, text=True, **kw)

    def one(t: Path) -> dict:
        tag = "rv/" + re.sub(r"[^a-z0-9]+", "-", t.name.lower())[:40].strip("-")
        b = dk("build", "-q", "-f", str(t / "environment/Dockerfile"), "-t", tag + ":v",
               str(t / "environment"), timeout=1800)
        if b.returncode:
            return {"task": t.name, "built": False, "reward": None, "binary": False, "note": "build failed"}
        r = dk("run", "-d", tag + ":v", "sleep", "300", timeout=120)
        if r.returncode:
            return {"task": t.name, "built": True, "reward": None, "binary": False, "note": "run failed"}
        cid = r.stdout.strip()
        try:
            dk("exec", "-u", "0", cid, "mkdir", "-p", "/tests", "/logs/verifier", timeout=60)
            subprocess.run([*docker, "cp", f"{t}/tests/.", f"{cid}:/tests/"], capture_output=True, text=True, timeout=300)
            dk("exec", "-u", "0", *verifier_env(t), cid, "bash", "/tests/test.sh", timeout=900)
            txt = dk("exec", "-u", "0", cid, "cat", "/logs/verifier/reward.txt", timeout=60).stdout.strip()
            jsn = dk("exec", "-u", "0", cid, "cat", "/logs/verifier/reward.json", timeout=60).stdout.strip()
            val, problems = judge(txt, jsn)
            note = "; ".join(problems)
            if not problems and "." in (txt or ""):
                note = "float-formatted value (binary, but check the writer is the binarized one)"
            return {"task": t.name, "built": True, "reward": val, "reward_txt": txt, "reward_json": jsn,
                    "binary": not problems, "note": note}
        finally:
            dk("rm", "-f", cid, timeout=120)

    res = []
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one, t): t for t in tasks}
        for i, f in enumerate(cf.as_completed(futs), 1):
            try:
                res.append(f.result())
            except Exception as e:
                res.append({"task": futs[f].name, "built": None, "reward": None, "binary": False, "note": str(e)[:120]})
            if i % 25 == 0:
                print(f"  {i}/{len(tasks)}", flush=True)

    res.sort(key=lambda r: r["task"])
    report.write_text(json.dumps(res, indent=1) + "\n")
    ok = [r for r in res if r.get("binary")]
    bad = [r for r in res if r.get("built") and not r.get("binary") and r.get("reward") is not None]
    none = [r for r in res if r.get("reward") is None]
    print(f"\nbinary 0/1        : {len(ok)}/{len(res)}")
    print(f"not binary        : {len(bad)}")
    print(f"no reward / failed: {len(none)}")
    for r in bad[:25]:
        print(f"   BAD  {r['task'][:54]:54s} {r['note'][:80]}")
    for r in none[:15]:
        print(f"   NONE {r['task'][:54]:54s} {r.get('note', '')[:60]}")
    print(f"report: {report}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
