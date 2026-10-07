#!/usr/bin/env python3
"""Prove a task's verifier emits a binary final reward, in the real image.

The contract is that the FINAL reward is exactly 0 or 1. Reading the code is not proof.
Harbor (0.21/0.22) reads `reward.json` FIRST - every value in it must be a number - and only
falls back to `reward.txt` when there is no reward.json. A package may also bake a second copy
of tests/ into the image via `COPY _app/tests/`. This runs the actual verifier in the actual
image and reports what it actually wrote, checking both files.

    sudo python3 verify_reward_binary.py TASK_DIR --image TAG [--solution-cmd CMD] [--remove PATH ...]

Checks, in order:
  1. the package's environment/_app/tests mirror (if any) matches tests/ file for file, and the
     image's /app/tests copy (if the image bakes one) matches tests/ file for file
  2. an empty workspace grades to exactly 0
  3. if --remove is given: after staging the golden answer and deleting those paths (a required
     deliverable), the workspace grades to exactly 0 - a floor zero cannot fake this one
  4. if --solution-cmd is given, the golden workspace grades to exactly 1

"Binary" means: reward.json, when present, is a JSON object whose values are all numbers and
whose `reward` value is 0 or 1; reward.txt, when present, parses as the number 0 or 1 ("0", "1",
"0.0" and "1.0" all qualify); and when both exist they agree. Exit 0 only when every executed check
passed.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

_TEMPLATE = re.compile(r"\$\{(\w+)(?::-(.*?))?\}")


def dk(*args, **kw):
    return subprocess.run(["docker", *args], capture_output=True, text=True, **kw)


def _expand(value: str) -> str:
    """Expand ${VAR} and ${VAR:-default} the way Harbor does."""
    return _TEMPLATE.sub(lambda m: os.environ.get(m.group(1)) or (m.group(2) or ""), value)


def verifier_env(task: Path) -> list[str]:
    """Harbor injects [verifier.env] during the verifier phase.

    Without it an LLM-judge task hits its infrastructure guard and deliberately writes NO
    reward rather than scoring an ungraded run as 0 - which reads as a broken package when
    nothing is wrong. Defaults written as ${VAR:-default} are honoured.
    """
    toml = task / "task.toml"
    if not toml.exists():
        return []
    env = {}
    if tomllib is not None:
        try:
            env = (tomllib.loads(toml.read_text(errors="replace")).get("verifier") or {}).get("env") or {}
        except Exception:
            env = {}
    if not env:  # fallback parser for very old Pythons or malformed files
        blk = re.search(r"\[verifier\.env\]([^\[]*)", toml.read_text(errors="replace"))
        for k, q, v in re.findall(r"""^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(["'])(.*?)\2""", blk.group(1) if blk else "", re.M):
            env[k] = v
    out = []
    for k, v in env.items():
        v = _expand(str(v))
        if v:
            out += ["-e", f"{k}={v}"]
    return out


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def judge(txt: str, jsn: str) -> tuple[float | None, list[str]]:
    """Return (the reward Harbor would read, problems)."""
    problems, harbor_reads = [], None
    if jsn:
        try:
            obj = json.loads(jsn)
        except json.JSONDecodeError:
            obj = None
            problems.append(f"reward.json is not valid JSON: {jsn[:80]!r}")
        if obj is not None:
            if not isinstance(obj, dict):
                problems.append("reward.json is not a JSON object")
            else:
                bad = [k for k, v in obj.items() if isinstance(v, bool) or not isinstance(v, (int, float))]
                if bad:
                    problems.append(f"reward.json has non-numeric values {bad} - Harbor rejects it")
                harbor_reads = obj.get("reward") if isinstance(obj.get("reward"), (int, float)) and not isinstance(obj.get("reward"), bool) else None
                if harbor_reads is None:
                    problems.append("reward.json has no numeric `reward` key")
                elif harbor_reads not in (0, 1):
                    problems.append(f"reward.json reward={harbor_reads!r} is not 0 or 1")
    t = _num(txt) if txt else None
    if txt and t is None:
        problems.append(f"reward.txt is not a number: {txt[:40]!r}")
    if t is not None and t not in (0, 1):
        problems.append(f"reward.txt={txt!r} is not 0 or 1")
    if harbor_reads is None and not jsn:
        harbor_reads = t
    if jsn and txt and t is not None and isinstance(harbor_reads, (int, float)) and float(harbor_reads) != t:
        problems.append(f"reward.json ({harbor_reads}) and reward.txt ({txt}) disagree")
    if not jsn and not txt:
        problems.append("no reward.json and no reward.txt written")
    return harbor_reads, problems


def read_reward(cid: str) -> tuple[str, str]:
    txt = dk("exec", "-u", "0", cid, "cat", "/logs/verifier/reward.txt").stdout.strip()
    jsn = dk("exec", "-u", "0", cid, "cat", "/logs/verifier/reward.json").stdout.strip()
    return txt, jsn


def grade(cid: str, task: Path) -> tuple[str, str]:
    # The scripts run the verifier phase as root so images ending `USER <non-root>` can create
    # /logs; otherwise the empty reward reads like a mismatch.
    dk("exec", "-u", "0", cid, "rm", "-rf", "/logs/verifier")
    dk("exec", "-u", "0", cid, "mkdir", "-p", "/logs/verifier", "/tests")
    subprocess.run(["docker", "cp", f"{task}/tests/.", f"{cid}:/tests/"], capture_output=True, text=True)
    dk("exec", "-u", "0", *verifier_env(task), cid, "bash", "/tests/test.sh")
    return read_reward(cid)


def mirror_problems(task: Path, cid: str) -> list[str]:
    problems = []
    src = {p.relative_to(task / "tests").as_posix(): p.read_bytes()
           for p in (task / "tests").rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    mirror = task / "environment" / "_app" / "tests"
    if mirror.is_dir():
        mir = {p.relative_to(mirror).as_posix(): p.read_bytes()
               for p in mirror.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        for rel in sorted(set(src) | set(mir)):
            if src.get(rel) != mir.get(rel):
                problems.append(f"environment/_app/tests/{rel} differs from tests/{rel} - run sync_app_mirror.sh and rebuild")
    dockerfile = task / "environment" / "Dockerfile"
    bakes = dockerfile.exists() and re.search(r"COPY\s+.*_app/tests", dockerfile.read_text(errors="replace"))
    has_img = dk("exec", "-u", "0", cid, "test", "-d", "/app/tests").returncode == 0
    if bakes and not has_img:
        problems.append("Dockerfile copies _app/tests but the image has no /app/tests - cannot confirm the graded copy")
    if has_img:
        with tempfile.TemporaryDirectory() as tmp:
            dk("cp", f"{cid}:/app/tests/.", tmp)
            img = {p.relative_to(tmp).as_posix(): p.read_bytes()
                   for p in Path(tmp).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        for rel in sorted(set(src) | set(img)):
            if src.get(rel) != img.get(rel):
                problems.append(f"image /app/tests/{rel} differs from source tests/{rel} - run sync_app_mirror.sh and rebuild")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task")
    ap.add_argument("--image", required=True)
    ap.add_argument("--solution-cmd", help="shell run inside the container to stage the golden answer")
    ap.add_argument("--remove", action="append", default=[],
                    help="after staging the golden answer, delete this path (a required deliverable); expect 0. Repeatable")
    a = ap.parse_args()
    task = Path(a.task).resolve()
    failures = []

    r = dk("run", "-d", a.image, "sleep", "1200")
    if r.returncode:
        print("could not start container:", r.stderr[-400:])
        return 2
    cid = r.stdout.strip()
    try:
        # 1. mirror / image divergence - the _app trap
        failures += mirror_problems(task, cid)

        # 2. empty workspace must be exactly 0
        txt, jsn = grade(cid, task)
        val, probs = judge(txt, jsn)
        print(f"empty workspace : reward.json={jsn!r} reward.txt={txt!r} -> Harbor reads {val!r}")
        failures += [f"empty workspace: {p}" for p in probs]
        if not probs and val != 0:
            failures.append(f"empty workspace graded {val!r}, expected 0")

        if a.solution_cmd:
            # 3. golden with a required deliverable removed must be exactly 0
            if a.remove:
                dk("exec", "-u", "0", cid, "bash", "-lc", a.solution_cmd)
                for path in a.remove:
                    dk("exec", "-u", "0", cid, "rm", "-rf", path)
                txt, jsn = grade(cid, task)
                val, probs = judge(txt, jsn)
                print(f"golden minus {a.remove}: reward.json={jsn!r} reward.txt={txt!r} -> Harbor reads {val!r}")
                failures += [f"broken workspace: {p}" for p in probs]
                if not probs and val != 0:
                    failures.append(f"golden minus a required deliverable graded {val!r}, expected 0")
            # 4. golden must be exactly 1
            dk("exec", "-u", "0", cid, "bash", "-lc", a.solution_cmd)
            txt, jsn = grade(cid, task)
            val, probs = judge(txt, jsn)
            print(f"golden solution : reward.json={jsn!r} reward.txt={txt!r} -> Harbor reads {val!r}")
            failures += [f"golden: {p}" for p in probs]
            if not probs and val != 1:
                failures.append(f"golden graded {val!r}, expected 1")
        else:
            print("golden solution : SKIPPED (no --solution-cmd) - binary contract only partly proven")
    finally:
        dk("rm", "-f", cid)

    for f in failures:
        print("FAIL:", f)
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
