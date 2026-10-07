#!/usr/bin/env python3
"""Repair repeated Docker digests: `name:tag@sha256:A@sha256:B` -> `name:tag@sha256:B`.

Two (or more) digests concatenated on one reference is not a parseable OCI reference, so the
image never builds and the failure cascades into Layer 3 oracle, Layer 4 environment and
Layer 5 calibration findings.

The FINAL digest is authoritative. Evidence: the package's own client_qc/access-receipt.json
names the second digest and never the first; the first is an identical injected prefix shared
across affected packages; the second matches what healthy packages (and infra's golden
reference package) pin on their own. Do NOT use infra's qc/client_feedback_fix.py
`doubled_image_digest` auto-fix on these packages: it keeps the FIRST digest.

Only the digest bytes change: the image name and its `:tag` are kept exactly as written, and
every other byte of the file (line endings included) survives. Each reference must collapse to
exactly one digest, so a surprise never gets silently applied.

Files scanned (as the client rubric and infra's lint do): every Dockerfile* and every
docker-compose / compose *.yml|*.yaml under environment/, and every task.toml in the package
(root, environment/_app/ and any nested copy).

    python3 fix_digest.py TASK_DIR [TASK_DIR ...] [--apply]

Without --apply it reports what it would change and exits.
"""
import re
import sys
from pathlib import Path

# A reference followed by two or more digests. Group 1 = name[:tag] (kept verbatim),
# group 2 = every digest, of which only the last one survives.
REPEATED = re.compile(
    rb"([A-Za-z0-9._/:-]*[A-Za-z0-9._/-])"           # registry/name[:tag], kept as written
    rb"((?:@sha256:[0-9a-f]{64}){2,})"                # two or more digests in a row
)
DIGEST = re.compile(rb"@sha256:[0-9a-f]{64}")


def candidates(task: Path) -> list[Path]:
    out = set()
    env = task / "environment"
    if env.is_dir():
        out.update(p for p in env.rglob("Dockerfile*") if p.is_file())
        for pat in ("docker-compose*.yml", "docker-compose*.yaml", "compose*.yml", "compose*.yaml"):
            out.update(p for p in env.rglob(pat) if p.is_file())
    out.update(p for p in task.rglob("task.toml") if p.is_file() and "evaluations" not in p.relative_to(task).parts)
    return sorted(out)


def collapse(match: re.Match) -> bytes:
    digests = DIGEST.findall(match.group(2))
    return match.group(1) + digests[-1]


def repair(path: Path, apply: bool) -> list[tuple[str, str]]:
    raw = path.read_bytes()
    if not REPEATED.search(raw):
        return []
    changes, out = [], []
    for line in raw.split(b"\n"):
        if not REPEATED.search(line):
            out.append(line)
            continue
        new = REPEATED.sub(collapse, line)
        leftover = [m for m in re.finditer(rb"(?:@sha256:[0-9a-f]{64}){2,}", new)]
        if leftover:
            raise SystemExit(f"{path}: a reference still carries more than one digest after repair; fix by hand")
        changes.append((line.decode(errors="replace"), new.decode(errors="replace")))
        out.append(new)
    if apply:
        path.write_bytes(b"\n".join(out))
    return changes


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    if not args:
        raise SystemExit(__doc__)
    total = 0
    for task in args:
        task = Path(task)
        for p in candidates(task):
            for before, after in repair(p, apply):
                total += 1
                print(f"{task.name}/{p.relative_to(task)}")
                print(f"  - {before.strip()[:160]}")
                print(f"  + {after.strip()[:160]}")
    print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {total} line(s)")
    if apply and total:
        print("VERIFY: docker build -f <task>/environment/Dockerfile <task>/environment")
        print("NOTE: if the Dockerfile COPYs _app/, run the package's sync_app_mirror.sh and rebuild.")
        print("NOTE: environment/ is part of Harbor's content hash - run stale_runs.py and report the stale tasks to the user.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
