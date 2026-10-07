#!/usr/bin/env python3
"""Report which edited packages now have stale run evidence. Read-only; never re-runs anything.

    python3 stale_runs.py BEFORE AFTER [--json] [--fail-on-stale]

BEFORE / AFTER may each be a task directory, a directory of task directories, a task .zip, or a
directory of .zip files. Tasks are paired by their root folder name.

How it decides. It does NOT recompute or compare a task hash. It lists the files that differ
between BEFORE and AFTER (byte comparison: changed, added or removed), then sorts each one by
whether it is a file Harbor's task hash reads. A task is STALE only when at least one changed file
is in that set; otherwise its recorded runs still describe the same task.

The set is copied from Harbor's own Packager.collect_files (harbor/publisher/packager.py, 0.21),
which is the function infra and the client QC call to fingerprint a task
(audit_oracle.py task_digests, oracle_l3.task_digest, qc/final_qc_gate.py content_digest):
    task.toml, instruction.md, README.md            (task root only)
    environment/**, tests/**, solution/**, steps/**
    minus files matched by the task's .gitignore, or, with no .gitignore, Harbor's defaults:
    __pycache__/, *.pyc, .DS_Store, *.swp, *.swo, *~
Everything else - evaluations/**, review.csv, client_qc*, qc_report.html, other root files -
cannot make a run stale. So binarizing recorded rewards under evaluations/ never does; editing the
verifier (tests/), the Dockerfile (environment/) or README.md does.

Two further effects are reported separately and do not set STALE:
  - certificate: a package that carries qc_report.html has an embedded certificate covering
    EVERY file, so any change at all (evaluations/ included) stops it verifying.
  - oracle-evidence digest: infra's package_evidence.core_task_digest (task.toml,
    instruction.md, tests/, environment/, solution/) applies no ignore rules, so a changed cache
    or editor file there, which Harbor ignores, still breaks the Oracle solvability binding.

If a task has a .gitignore and the `pathspec` package is not installed, its ignore rules cannot
be applied; such tasks are reported as UNSURE with the files in question rather than guessed.

This script only reports. When it lists stale tasks, stop and ask the user how to proceed
(re-run QC / the Oracle for those tasks, accept and declare the staleness, or revert the edit).
Never start a QC or Oracle run on your own.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT_FILES = ("task.toml", "instruction.md", "README.md")
TREES = ("environment", "tests", "solution", "steps")
DEFAULT_IGNORES = ["__pycache__/", "*.pyc", ".DS_Store", "*.swp", "*.swo", "*~"]
ORACLE_DIGEST_ROOTS = ("task.toml", "instruction.md", "tests", "environment", "solution")


def _default_ignored(rel: str) -> bool:
    parts = rel.split("/")
    if "__pycache__" in parts[:-1]:
        return True
    return any(fnmatch.fnmatch(parts[-1], pat) for pat in DEFAULT_IGNORES if not pat.endswith("/"))


def ignore_rule(gitignore_text: str | None):
    """Return (is_ignored(rel) or None when it cannot be evaluated, note)."""
    if gitignore_text is None:
        return _default_ignored, None
    try:
        import pathspec  # Harbor's own dependency
    except ImportError:
        return None, "task has a .gitignore but `pathspec` is not installed, so its ignore rules were not applied"
    return pathspec.PathSpec.from_lines("gitignore", gitignore_text.splitlines()).match_file, None


def in_hash_scope(rel: str) -> bool:
    top = rel.split("/")[0]
    return rel in ROOT_FILES or (top in TREES and "/" in rel)


def in_oracle_digest(rel: str) -> bool:
    top = rel.split("/")[0]
    return rel in ("task.toml", "instruction.md") or (top in ORACLE_DIGEST_ROOTS and "/" in rel)


class Task:
    """A task's files as {relative path: sha256}, read from a directory or a zip."""

    def __init__(self, name: str, files: dict[str, str], gitignore: str | None):
        self.name, self.files, self.gitignore = name, files, gitignore

    @staticmethod
    def from_dir(d: Path) -> "Task":
        files = {p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(d.rglob("*")) if p.is_file()}
        gi = d / ".gitignore"
        return Task(d.name, files, gi.read_text(errors="replace") if gi.is_file() else None)

    @staticmethod
    def from_zip(z: Path) -> list["Task"]:
        zf = zipfile.ZipFile(z)
        by_root: dict[str, dict[str, str]] = {}
        gitignores: dict[str, str] = {}
        for info in zf.infolist():
            if info.is_dir():
                continue
            root, _, rel = info.filename.replace("\\", "/").partition("/")
            if not rel:
                continue
            data = zf.read(info.filename)
            by_root.setdefault(root, {})[rel] = hashlib.sha256(data).hexdigest()
            if rel == ".gitignore":
                gitignores[root] = data.decode("utf-8", "replace")
        return [Task(r, f, gitignores.get(r)) for r, f in by_root.items() if "task.toml" in f]


def load(target: Path) -> dict[str, Task]:
    tasks: list[Task] = []
    if target.is_file() and target.suffix == ".zip":
        tasks = Task.from_zip(target)
    elif (target / "task.toml").is_file():
        tasks = [Task.from_dir(target)]
    elif target.is_dir():
        for child in sorted(target.iterdir()):
            if child.is_file() and child.suffix == ".zip":
                tasks += Task.from_zip(child)
            elif child.is_dir() and (child / "task.toml").is_file():
                tasks.append(Task.from_dir(child))
    else:
        raise SystemExit(f"not a task dir, zip, or folder of either: {target}")
    out: dict[str, Task] = {}
    for t in tasks:
        if t.name in out:
            raise SystemExit(f"two tasks named {t.name!r} under {target}; pair them explicitly")
        out[t.name] = t
    return out


def classify(b: Task, a: Task) -> dict:
    changed = sorted(rel for rel in set(b.files) | set(a.files) if b.files.get(rel) != a.files.get(rel))
    kind = {rel: ("added" if rel not in b.files else "removed" if rel not in a.files else "changed") for rel in changed}
    ignore_b, note_b = ignore_rule(b.gitignore)
    ignore_a, note_a = ignore_rule(a.gitignore)
    affects, outside, unsure, oracle_only = [], [], [], []
    for rel in changed:
        if not in_hash_scope(rel):
            outside.append(rel)
            continue
        # Harbor applies the ignore rules of whichever side the file is on; a file counts if
        # either side's hash would include it.
        verdicts = [None if fn is None else not fn(rel)
                    for fn, present in ((ignore_b, rel in b.files), (ignore_a, rel in a.files)) if present]
        if any(v is True for v in verdicts):
            affects.append(rel)
        elif any(v is None for v in verdicts):
            unsure.append(rel)
        else:
            outside.append(rel)
            if in_oracle_digest(rel):
                oracle_only.append(rel)
    if ".gitignore" in changed:
        # a changed .gitignore can change which unchanged files Harbor reads
        unsure.append(".gitignore")
    status = "stale" if affects else "unsure" if unsure else "fresh"
    return {
        "task": b.name,
        "status": status,
        "files_affecting_hash": [f"{rel} ({kind[rel]})" for rel in affects],
        "files_unsure": [f"{rel} ({kind.get(rel, 'changed')})" for rel in unsure],
        "files_outside_hash": [f"{rel} ({kind[rel]})" for rel in outside],
        "oracle_evidence_digest_only": oracle_only,
        "certificate_present": "qc_report.html" in a.files,
        "certificate_breaks": "qc_report.html" in a.files and any(r != "qc_report.html" for r in changed),
        "notes": [n for n in {note_b, note_a} if n],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--fail-on-stale", action="store_true", help="exit 3 when any task is stale or unsure")
    a = ap.parse_args()

    before, after = load(a.before), load(a.after)
    if len(before) == 1 and len(after) == 1 and set(before) != set(after):
        # two single tasks given explicitly: pair them even if the folder names differ
        bn, at = next(iter(before)), next(iter(after.values()))
        at.name = bn
        after = {bn: at}
    rows = []
    for name in sorted(set(before) | set(after)):
        if name not in before or name not in after:
            rows.append({"task": name, "status": "unpaired", "missing_from": "before" if name not in before else "after"})
        else:
            rows.append(classify(before[name], after[name]))

    stale = [r for r in rows if r["status"] == "stale"]
    unsure = [r for r in rows if r["status"] == "unsure"]
    cert = [r for r in rows if r.get("certificate_breaks")]
    if a.json:
        print(json.dumps({"tasks": rows, "stale": len(stale), "unsure": len(unsure),
                          "certificate_breaks": len(cert)}, indent=1))
    else:
        for r in rows:
            if r["status"] == "unpaired":
                print(f"UNPAIRED  {r['task']}  (missing from {r['missing_from']})")
                continue
            extra = "  certificate breaks" if r["certificate_breaks"] else ""
            print(f"{r['status'].upper():9} {r['task']}{extra}")
            for label, key in (("affects hash", "files_affecting_hash"), ("unsure", "files_unsure")):
                for rel in r[key][:12]:
                    print(f"            {label}: {rel}")
                if len(r[key]) > 12:
                    print(f"            ... and {len(r[key]) - 12} more")
            if r["files_outside_hash"]:
                print(f"            {len(r['files_outside_hash'])} changed file(s) outside the hash (do not make runs stale)")
            for rel in r["oracle_evidence_digest_only"]:
                print(f"            note: {rel} is ignored by Harbor but read by infra's Oracle-evidence digest")
            for n in r["notes"]:
                print(f"            note: {n}")
        print(f"\n{len(stale)} of {len(rows)} task(s) stale, {len(unsure)} unsure; "
              f"{len(cert)} carry an embedded certificate that no longer verifies.")
        if stale or unsure or cert:
            print("Do NOT re-run anything automatically. Report this list to the user and ask how to proceed.")
    return 3 if (a.fail_on_stale and (stale or unsure)) else 0


if __name__ == "__main__":
    sys.exit(main())
