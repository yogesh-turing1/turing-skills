#!/usr/bin/env python3
"""Repair doubled Docker digests: `name:tag@sha256:A@sha256:B` -> `name@sha256:B`.

Two digests concatenated on one reference is not a parseable OCI reference, so the
image never builds and the failure cascades into Layer 3 oracle, Layer 4 environment
and Layer 5 calibration findings.

The FINAL digest is authoritative. Evidence: the package's own
client_qc/access-receipt.json names the second digest and never the first; the first
is an identical injected prefix shared across affected packages; the second matches
what healthy packages pin on their own.

Rewrites on raw bytes so line endings and every other byte survive. Asserts exactly
one substitution per line, so a surprise never gets silently applied.

    python3 fix_digest.py TASK_DIR [TASK_DIR ...] [--apply]

Without --apply it reports what it would change and exits.
"""
import re
import sys
from pathlib import Path

# name[:tag]@sha256:<64hex>@sha256:<64hex>  ->  keep name + the final digest
DOUBLED = re.compile(
    rb"([A-Za-z0-9._/-]+?)(?::[A-Za-z0-9._-]+)?"     # image name, optional :tag
    rb"@sha256:[0-9a-f]{64}"                          # first (injected) digest
    rb"(@sha256:[0-9a-f]{64})"                        # final (authoritative) digest
)

CANDIDATES = ("environment/Dockerfile", "task.toml", "environment/_app/task.toml")


def repair(path: Path, apply: bool) -> list[tuple[str, str]]:
    raw = path.read_bytes()
    if not DOUBLED.search(raw):
        return []
    changes = []
    out = []
    for line in raw.split(b"\n"):
        hits = DOUBLED.findall(line)
        if not hits:
            out.append(line)
            continue
        if len(hits) != 1:
            raise SystemExit(f"{path}: expected one doubled reference per line, found {len(hits)}")
        new = DOUBLED.sub(rb"\1\2", line)
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
        for rel in CANDIDATES:
            p = task / rel
            if not p.exists():
                continue
            for before, after in repair(p, apply):
                total += 1
                print(f"{task.name}/{rel}")
                print(f"  - {before.strip()[:120]}")
                print(f"  + {after.strip()[:120]}")
    print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {total} line(s)")
    if apply and total:
        print("VERIFY: docker build -f <task>/environment/Dockerfile <task>/environment")
        print("NOTE: if the Dockerfile COPYs _app/, run the package's sync_app_mirror.sh and rebuild.")
    return 0


sys.exit(main())
