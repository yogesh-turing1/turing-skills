#!/usr/bin/env python3
"""--candidate-list lets a manifest be the candidate side.

The script could only ever read candidates as real zips. The 275 exist as a
manifest long before anyone has the packages in a folder, and the delivered
side already accepts a manifest, so the asymmetry was the only thing stopping
a dedup from running.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "dedup_check.py"


def run(args, cwd):
    return subprocess.run([sys.executable, str(SCRIPT)] + args,
                          capture_output=True, text=True, cwd=str(cwd))


def write(p, obj):
    pathlib.Path(p).write_text(json.dumps(obj), encoding="utf-8")


def test_candidate_list_flags_a_name_already_delivered():
    with tempfile.TemporaryDirectory() as d:
        write(f"{d}/delivered.json", {"batch": "Batch 1", "tasks": [
            {"task_name": "already-shipped", "sha256": "a" * 64}]})
        write(f"{d}/cand.json", {"tasks": [
            {"name": "already-shipped"}, {"name": "brand-new"}]})
        r = run(["--candidate-list", f"{d}/cand.json",
                 "--delivered", f"{d}/delivered.json",
                 "--out", f"{d}/rep", "--no-fail"], d)
        assert r.returncode == 0, r.stderr
        s = json.loads(pathlib.Path(f"{d}/rep/summary.json").read_text(encoding="utf-8"))
        assert s["candidates_read"] == 2, s
        assert s["already_delivered_by_name"] == 1, s
        assert s["unique_new_tasks"] == 1, s


def test_namespace_is_ignored_when_matching():
    with tempfile.TemporaryDirectory() as d:
        write(f"{d}/delivered.json", {"tasks": [{"task_name": "gen-g63-thing"}]})
        write(f"{d}/cand.json", {"tasks": [{"name": "harbor/gen-g63-thing"}]})
        r = run(["--candidate-list", f"{d}/cand.json",
                 "--delivered", f"{d}/delivered.json",
                 "--out", f"{d}/rep", "--no-fail"], d)
        assert r.returncode == 0, r.stderr
        s = json.loads(pathlib.Path(f"{d}/rep/summary.json").read_text(encoding="utf-8"))
        assert s["unique_new_tasks"] == 0, s


def test_duplicate_inside_the_candidate_list_is_collapsed():
    with tempfile.TemporaryDirectory() as d:
        write(f"{d}/delivered.json", {"tasks": []})
        write(f"{d}/cand.json", {"tasks": [{"name": "twice"}, {"name": "twice"},
                                           {"name": "once"}]})
        r = run(["--candidate-list", f"{d}/cand.json",
                 "--delivered", f"{d}/delivered.json",
                 "--out", f"{d}/rep", "--no-fail"], d)
        assert r.returncode == 0, r.stderr
        s = json.loads(pathlib.Path(f"{d}/rep/summary.json").read_text(encoding="utf-8"))
        assert s["duplicate_within_batch"] == 1, s
        assert s["unique_new_tasks"] == 2, s


def test_a_declared_name_overrides_the_listed_name():
    """A list may carry the folder name; a declared name, when present, wins."""
    with tempfile.TemporaryDirectory() as d:
        write(f"{d}/delivered.json", {"tasks": [{"task_name": "real-declared-name"}]})
        write(f"{d}/cand.json", {"tasks": [
            {"name": "folder-name-that-differs", "declared_name": "real-declared-name"}]})
        r = run(["--candidate-list", f"{d}/cand.json",
                 "--delivered", f"{d}/delivered.json",
                 "--out", f"{d}/rep", "--no-fail"], d)
        assert r.returncode == 0, r.stderr
        s = json.loads(pathlib.Path(f"{d}/rep/summary.json").read_text(encoding="utf-8"))
        assert s["unique_new_tasks"] == 0, s


def test_zips_and_a_list_can_be_given_together():
    with tempfile.TemporaryDirectory() as d:
        write(f"{d}/delivered.json", {"tasks": []})
        write(f"{d}/cand.json", {"tasks": [{"name": "from-list"}]})
        r = run(["--candidate-list", f"{d}/cand.json", "--candidates", d,
                 "--delivered", f"{d}/delivered.json",
                 "--out", f"{d}/rep", "--no-fail"], d)
        assert r.returncode == 0, r.stderr
        s = json.loads(pathlib.Path(f"{d}/rep/summary.json").read_text(encoding="utf-8"))
        assert s["candidates_read"] == 1, s
