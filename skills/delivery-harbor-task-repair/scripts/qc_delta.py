#!/usr/bin/env python3
"""Diff raw QC finding counts per task and per area, before vs after a repair pass.

    python3 qc_delta.py BEFORE_DIR AFTER_DIR

Each directory holds one sub-folder per task containing a QC report; tasks are paired by that
sub-folder name (report formats disagree on how they name the task). Three report shapes are read:
  - client QC report.json   {"task": {"name"}, "findings": [{"outcome", "area_id"}]}      (fail = outcome "fail")
  - infra Harbor Check / Final QC report.json
                            {"task_id", "findings": [{"category_id"}], "category_results": [...]}
                            (every listed finding is a failure)
  - client framework findings.csv   columns task/area_id/status (or outcome); fail = status/outcome
                                    FAIL/FINDING
Raw counts are compared, never sets of criteria (sets dedupe and will not reconcile with totals).
A task with no after-report is reported separately: it is unmeasured, not passing.
"""
import collections
import csv
import json
import sys
from pathlib import Path

FAIL_WORDS = {"fail", "failed", "finding"}


def _fails_from_json(report: dict) -> list[str]:
    findings = report.get("findings")
    if findings is None:
        findings = [f for c in report.get("category_results") or [] for f in (c.get("findings") or [])]
    out = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        outcome = str(f.get("outcome", f.get("status", "fail"))).lower()
        if outcome in FAIL_WORDS:
            out.append(f.get("area_id") or f.get("category_id") or f.get("criterion") or "unknown")
    return out


def _fails_from_csv(path: Path) -> list[str]:
    out = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            status = str(row.get("status") or row.get("outcome") or "").lower()
            if status in FAIL_WORDS:
                out.append(row.get("area_id") or row.get("category_id") or "unknown")
    return out


def load(root: Path) -> dict[str, list[str]]:
    reports: dict[str, list[str]] = {}
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        rj, fc = folder / "report.json", folder / "findings.csv"
        if rj.is_file():
            fails = _fails_from_json(json.loads(rj.read_text()))
        elif fc.is_file():
            fails = _fails_from_csv(fc)
        else:
            continue
        reports[folder.name] = fails
    return reports


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit("usage: qc_delta.py BEFORE_TASKS_DIR AFTER_TASKS_DIR")
    b, a = load(Path(sys.argv[1])), load(Path(sys.argv[2]))
    print("tasks with a BEFORE report:", len(b), "| with an AFTER report:", len(a))
    both = sorted(set(a) & set(b))
    tb = ta = 0
    for name in both:
        bc, ac = collections.Counter(b[name]), collections.Counter(a[name])
        tb += sum(bc.values())
        ta += sum(ac.values())
        print(f"### {name}   {sum(bc.values())} -> {sum(ac.values())} fails")
        for area in sorted(set(bc) | set(ac)):
            d = ac[area] - bc[area]
            mark = "  (unchanged)" if d == 0 else f"  ({d:+d})"
            print(f"     {area:34s} {bc[area]:2d} -> {ac[area]:2d}{mark}")
    print(f"\nRAW TOTALS over the {len(both)} task(s) with BOTH reports: {tb} -> {ta}  (net {ta - tb:+d})")
    missing = sorted(set(b) - set(a))
    if missing:
        print(f"NO AFTER-REPORT ({len(missing)}) - unmeasured, not passing: {missing}")
    extra = sorted(set(a) - set(b))
    if extra:
        print(f"AFTER-ONLY ({len(extra)}) - no before-report to compare against: {extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
