#!/usr/bin/env python3
"""Prove a task's verifier emits a binary final reward, in the real image.

The contract is that the FINAL reward is exactly 0 or 1. Reading the code is not
proof — Harbor reads reward.txt first and reward.json second, and a package may bake
a second copy of tests/ into the image via `COPY _app/tests/`. This runs the actual
verifier in the actual image and reports what it actually wrote.

    sudo python3 verify_reward_binary.py TASK_DIR --image TAG [--solution-cmd CMD]

Checks, in order:
  1. the image copy of the verifier matches the source copy (catches the _app trap)
  2. an empty workspace grades to exactly 0
  3. if --solution-cmd is given, the golden workspace grades to exactly 1

Exit 0 only when every executed check produced a value in {0, 1} and no mismatch
between the image and source copies was found.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def dk(*args, **kw):
    return subprocess.run(["docker", *args], capture_output=True, text=True, **kw)


def read_reward(cid: str) -> tuple[str, str]:
    txt = dk("exec", "-u", "0", cid, "cat", "/logs/verifier/reward.txt").stdout.strip()
    jsn = dk("exec", "-u", "0", cid, "cat", "/logs/verifier/reward.json").stdout.strip()
    return txt, jsn


def verifier_env(task: Path) -> list[str]:
    """Harbor injects [verifier.env] during the verifier phase.

    Without it an LLM-judge task hits its infrastructure guard and deliberately
    writes NO reward rather than scoring an ungraded run as 0 — which reads as a
    broken package when nothing is wrong.
    """
    toml = task / "task.toml"
    if not toml.exists():
        return []
    blk = re.search(r"\[verifier\.env\]([^\[]*)", toml.read_text(errors="replace"))
    out = []
    for k, v in re.findall(r'^\s*([A-Z][A-Z0-9_]*)\s*=\s*"([^"]*)"', blk.group(1) if blk else "", re.M):
        v = re.sub(r"\$\{(\w+)(:-[^}]*)?\}", lambda m: os.environ.get(m.group(1), ""), v)
        if v:
            out += ["-e", f"{k}={v}"]
    return out


def grade(cid: str, task: Path) -> tuple[str, str]:
    # Harbor runs the verifier phase as root. Images ending `USER <non-root>` cannot
    # create /logs, which yields an empty reward.txt that looks like a mismatch.
    dk("exec", "-u", "0", cid, "rm", "-rf", "/logs/verifier")
    dk("exec", "-u", "0", cid, "mkdir", "-p", "/logs/verifier", "/tests")
    subprocess.run(["bash", "-c", f"docker cp {task}/tests/. {cid}:/tests/"],
                   capture_output=True, text=True)
    dk("exec", "-u", "0", *verifier_env(task), cid, "bash", "/tests/test.sh")
    return read_reward(cid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--image", required=True)
    ap.add_argument("--solution-cmd", help="shell run inside the container to stage the golden answer")
    a = ap.parse_args()
    task = Path(a.task).resolve()
    failures = []

    r = dk("run", "-d", a.image, "sleep", "600")
    if r.returncode:
        print("could not start container:", r.stderr[-400:])
        return 2
    cid = r.stdout.strip()
    try:
        # 1. image/source divergence — the _app mirror trap
        for src in task.glob("tests/*.py"):
            inimg = dk("exec", "-u", "0", cid, "cat", f"/app/tests/{src.name}").stdout
            if inimg and inimg != src.read_text(errors="replace"):
                failures.append(f"image /app/tests/{src.name} differs from source tests/{src.name}"
                                " — run the package's sync_app_mirror.sh and rebuild")

        # 2. empty workspace must be exactly 0
        txt, jsn = grade(cid, task)
        print(f"empty workspace : reward.txt={txt!r} reward.json={jsn!r}")
        if txt not in ("0", "0.0"):
            failures.append(f"empty workspace produced {txt!r}, expected 0")

        # 3. golden must be exactly 1
        if a.solution_cmd:
            dk("exec", "-u", "0", cid, "bash", "-lc", a.solution_cmd)
            txt, jsn = grade(cid, task)
            print(f"golden solution : reward.txt={txt!r} reward.json={jsn!r}")
            if txt not in ("1", "1.0"):
                failures.append(f"golden produced {txt!r}, expected 1")
        else:
            print("golden solution : SKIPPED (no --solution-cmd) — binary contract only partly proven")
    finally:
        dk("rm", "-f", cid)

    for f in failures:
        print("FAIL:", f)
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 0 if not failures else 1


sys.exit(main())
