#!/usr/bin/env python3
"""Append-only change ledger. Every edit in this fix pass goes through here.

    ledger.py add --step A1-digest --task X --file f --action rewrite-line \
        --before '...' --after '...' --rationale '...' --agent digest-fixer [--line 7]
    ledger.py verify --seq 7 --verified-by 'docker build succeeded'
    ledger.py decision --key digest-choice --chose '...' --evidence '...' --approved-by user
    ledger.py csv
"""
import argparse, csv, hashlib, json, os, subprocess, sys
from pathlib import Path

L = Path(os.environ.get("FIXDIR", os.path.expanduser("~/harbor_gce/fix-5task-20260918"))) / "ledger"
CH, DE, CS = L / "changes.json", L / "decisions.json", L / "changes.csv"
FIELDS = ["seq","timestamp","step","task","file","action","line","before","after",
          "rationale","sha256_before","sha256_after","verified_by","agent","reversible"]


def now():
    return subprocess.run(["date","-u","+%Y-%m-%dT%H:%M:%SZ"],capture_output=True,text=True).stdout.strip()


def load(p):
    return json.loads(p.read_text()) if p.exists() else []


def save(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=1) + "\n")


def sha(p):
    p = Path(p)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def to_csv():
    rows = load(CH)
    with open(CS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (str(r.get(k, ""))[:300]) for k in FIELDS})
    return len(rows)


a = argparse.ArgumentParser(); s = a.add_subparsers(dest="cmd", required=True)
p = s.add_parser("add")
for f in ("step","task","file","action","before","after","rationale","agent"):
    p.add_argument("--"+f, default="")
p.add_argument("--line", default=""); p.add_argument("--path", default="")
p.add_argument("--irreversible", action="store_true")
v = s.add_parser("verify"); v.add_argument("--seq", type=int, required=True); v.add_argument("--verified-by", required=True)
d = s.add_parser("decision")
for f in ("key","chose","evidence","approved-by"): d.add_argument("--"+f, default="")
s.add_parser("csv")
args = a.parse_args()

if args.cmd == "add":
    rows = load(CH)
    rec = {"seq": len(rows)+1, "timestamp": now(), "step": args.step, "task": args.task,
           "file": args.file, "action": args.action, "line": args.line,
           "before": args.before, "after": args.after, "rationale": args.rationale,
           "sha256_before": args.__dict__.get("_sb"), "sha256_after": sha(args.path) if args.path else None,
           "verified_by": None, "agent": args.agent, "reversible": not args.irreversible}
    rows.append(rec); save(CH, rows); to_csv(); print(rec["seq"])
elif args.cmd == "verify":
    rows = load(CH)
    for r in rows:
        if r["seq"] == args.seq: r["verified_by"] = args.verified_by
    save(CH, rows); to_csv(); print("ok")
elif args.cmd == "decision":
    rows = load(DE)
    rows.append({"timestamp": now(), "key": args.key, "chose": args.chose,
                 "evidence": args.evidence, "approved_by": getattr(args, "approved_by")})
    save(DE, rows); print("ok")
elif args.cmd == "csv":
    print(to_csv())
