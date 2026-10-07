#!/usr/bin/env python3
"""Append-only change ledger. Every edit in this fix pass goes through here.

    ledger.py add --step A1-digest --task X --file f --action rewrite-line \
        --before '...' --after '...' --rationale '...' --agent digest-fixer \
        --path /abs/work/X/f [--baseline-path /abs/baseline/X/f] [--line 7] [--irreversible]
    ledger.py verify --seq 7 --verified-by 'docker build succeeded'
    ledger.py decision --key digest-choice --chose '...' --evidence '...' --approved-by user
    ledger.py csv

The ledger lives in $FIXDIR/ledger (FIXDIR defaults to the current directory).
`sha256_before` is the hash of the unedited file: pass --baseline-path, or keep the frozen copy at
$FIXDIR/baseline/<task>/<file> and it is found automatically. `sha256_after` is the hash of --path.
Writes are serialised with a file lock, so concurrent agents cannot lose each other's records.
"""
import argparse
import contextlib
import csv
import fcntl
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

FIXDIR = Path(os.environ.get("FIXDIR", os.getcwd()))
L = FIXDIR / "ledger"
CH, DE, CS, LOCK = L / "changes.json", L / "decisions.json", L / "changes.csv", L / ".lock"
FIELDS = ["seq", "timestamp", "step", "task", "file", "action", "line", "before", "after",
          "rationale", "sha256_before", "sha256_after", "verified_by", "agent", "reversible"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextlib.contextmanager
def locked():
    L.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def load(p):
    return json.loads(p.read_text()) if p.exists() else []


def save(p, d):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(d, indent=1) + "\n")
    tmp.replace(p)


def sha(p):
    p = Path(p)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def to_csv():
    rows = load(CH)
    with open(CS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (str(r.get(k, ""))[:300]) for k in FIELDS})
    return len(rows)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = a.add_subparsers(dest="cmd", required=True)
    p = s.add_parser("add")
    for f in ("step", "task", "file", "action", "before", "after", "rationale", "agent"):
        p.add_argument("--" + f, default="")
    p.add_argument("--line", default="")
    p.add_argument("--path", default="", help="the edited file (hashed into sha256_after)")
    p.add_argument("--baseline-path", default="", help="the unedited copy (hashed into sha256_before)")
    p.add_argument("--irreversible", action="store_true")
    v = s.add_parser("verify")
    v.add_argument("--seq", type=int, required=True)
    v.add_argument("--verified-by", required=True)
    d = s.add_parser("decision")
    for f in ("key", "chose", "evidence", "approved-by"):
        d.add_argument("--" + f, default="")
    s.add_parser("csv")
    args = a.parse_args()

    with locked():
        if args.cmd == "add":
            base = args.baseline_path
            if not base and args.task and args.file:
                guess = FIXDIR / "baseline" / args.task / args.file
                base = str(guess) if guess.is_file() else ""
            sb = sha(base) if base else None
            if sb is None:
                print("warning: no baseline copy found, sha256_before is null "
                      "(pass --baseline-path or keep the frozen copy under $FIXDIR/baseline/)", file=sys.stderr)
            rows = load(CH)
            rec = {"seq": len(rows) + 1, "timestamp": now(), "step": args.step, "task": args.task,
                   "file": args.file, "action": args.action, "line": args.line,
                   "before": args.before, "after": args.after, "rationale": args.rationale,
                   "sha256_before": sb, "sha256_after": sha(args.path) if args.path else None,
                   "verified_by": None, "agent": args.agent, "reversible": not args.irreversible}
            rows.append(rec)
            save(CH, rows)
            to_csv()
            print(rec["seq"])
        elif args.cmd == "verify":
            rows = load(CH)
            hit = [r for r in rows if r["seq"] == args.seq]
            if not hit:
                print(f"error: no ledger record with seq {args.seq}", file=sys.stderr)
                return 1
            for r in hit:
                r["verified_by"] = args.verified_by
            save(CH, rows)
            to_csv()
            print("ok")
        elif args.cmd == "decision":
            rows = load(DE)
            rows.append({"timestamp": now(), "key": args.key, "chose": args.chose,
                         "evidence": args.evidence, "approved_by": args.approved_by})
            save(DE, rows)
            print("ok")
        elif args.cmd == "csv":
            print(to_csv())
    return 0


if __name__ == "__main__":
    sys.exit(main())
