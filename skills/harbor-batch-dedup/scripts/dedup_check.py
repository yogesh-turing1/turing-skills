#!/usr/bin/env python3
"""Harbor batch deduplication - standalone, standard library only (Python 3.8+; 3.11+ uses tomllib).

Identity is the declared [task] name in each package's own top-level task.toml - never the bucket folder or the
zip file name. A candidate is excluded when:
  * its declared name (full, or the leaf after the last "/") was already delivered, or
  * its archive sha256 was already delivered, or
  * another candidate in the same batch declares the same name (the newest archive is kept).
A candidate whose task.toml cannot be read is held out, never assumed new.

  # check a candidate batch against earlier deliveries (folders of zips, zips, or saved lists)
  python3 dedup_check.py --candidates ./new-batch --delivered ./batch-1 ./batch-2 delivered.csv

  # save a reusable list of what has been delivered (name + sha256) from folders of shipped zips
  python3 dedup_check.py --build-delivered-list delivered.csv --delivered ./batch-1 ./batch-2

Exit code: 0 = no duplicates, 1 = duplicates or unreadable packages found (use --no-fail to always exit 0),
2 = bad arguments. Reports go to --out (default ./dedup-report): summary.json, keep.csv, excluded.csv.
Read-only on every input.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import zipfile

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def find_zips(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for dp, dn, fn in os.walk(p):
                out += [os.path.join(dp, f) for f in fn if f.lower().endswith(".zip") and not f.startswith("._")]
        elif p.lower().endswith(".zip") and os.path.isfile(p):
            out.append(p)
    return sorted(set(out))


def toml_task_name(text):
    if tomllib is not None:
        return ((tomllib.loads(text).get("task") or {}).get("name") or None)
    in_task = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_task = s == "[task]"
            continue
        m = re.match(r'name\s*=\s*["\']([^"\']+)["\']', s) if in_task else None
        if m:
            return m.group(1)
    return None


def declared_name(zpath):
    """[task] name from the package's own task.toml: the shallowest one, never under environment/ or evaluations/."""
    with zipfile.ZipFile(zpath) as z:
        cands = [n for n in z.namelist() if n.endswith("task.toml")
                 and not any(part in ("environment", "evaluations") for part in n.split("/")[:-1])]
        if not cands:
            raise ValueError("no top-level task.toml")
        n = sorted(cands, key=lambda x: (x.count("/"), x))[0]
        name = toml_task_name(z.read(n).decode("utf-8", "replace"))
        if not name:
            raise ValueError("task.toml has no [task] name")
        return name, n


def leaf(name):
    return (name or "").strip().split("/")[-1].lower()


def read_package(zpath):
    r = {"path": zpath, "zip_name": os.path.basename(zpath)[:-4], "sha256": sha256_file(zpath),
         "mtime": os.path.getmtime(zpath), "task_name": None, "toml_path": None, "error": None}
    try:
        r["task_name"], r["toml_path"] = declared_name(zpath)
    except Exception as e:  # noqa: BLE001
        r["error"] = "%s: %s" % (type(e).__name__, e)
    return r


def load_delivered(paths):
    """Delivered entries from folders/zips of shipped packages and/or saved CSV / JSON lists."""
    entries, problems = [], []
    for p in paths:
        low = p.lower()
        if low.endswith(".csv") and os.path.isfile(p):
            with open(p, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    entries.append({"task_name": row.get("task_name") or row.get("name"), "sha256": row.get("sha256"),
                                    "source": row.get("source") or row.get("batch") or row.get("delivery_id")
                                    or os.path.basename(p)})
        elif low.endswith(".json") and os.path.isfile(p):
            d = json.load(open(p, encoding="utf-8"))
            rows = d.get("tasks", []) if isinstance(d, dict) else d
            for t in rows:
                t = t if isinstance(t, dict) else {"task_name": t}
                entries.append({"task_name": t.get("task_name") or t.get("name"), "sha256": t.get("sha256"),
                                "source": (d.get("batch") if isinstance(d, dict) else None) or os.path.basename(p)})
    zips = find_zips([p for p in paths if not p.lower().endswith((".csv", ".json"))])
    for z in zips:
        r = read_package(z)
        if r["error"]:
            problems.append({"path": z, "error": r["error"]})
        entries.append({"task_name": r["task_name"], "sha256": r["sha256"], "source": os.path.dirname(z) or "."})
    return entries, problems


def load_candidate_list(paths):
    """Candidates from a saved .csv/.json list instead of the packages themselves.

    A batch exists as a manifest long before anyone holds its zips, and the
    delivered side already accepts one, so this removes an asymmetry rather
    than adding a mode. `declared_name` wins over `name` where a list carries
    both: the declared task.toml name is the identity, and a list that only
    knows the folder name says so by leaving it out.
    """
    out = []
    for p in paths:
        low = p.lower()
        if low.endswith(".csv") and os.path.isfile(p):
            with open(p, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        elif low.endswith(".json") and os.path.isfile(p):
            d = json.load(open(p, encoding="utf-8"))
            rows = d.get("tasks", []) if isinstance(d, dict) else d
        else:
            raise SystemExit("--candidate-list takes .csv or .json files, not %r" % p)
        for t in rows:
            t = t if isinstance(t, dict) else {"name": t}
            name = t.get("declared_name") or t.get("task_name") or t.get("name") or ""
            out.append({
                "zip_name": (t.get("original_filename") or (name + ".zip")).lower(),
                "task_name": name,
                "sha256": (t.get("sha256") or "").lower(),
                "path": t.get("source_uri") or t.get("package_path") or os.path.basename(p),
                "toml_path": "(from %s)" % os.path.basename(p),
                "mtime": 0,
                "error": "" if name else "no name in the list row",
            })
    return out


def write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Harbor batch deduplication by declared task.toml name.")
    ap.add_argument("--candidates", nargs="*", default=[], help="folders and/or zips of the new batch")
    ap.add_argument("--candidate-list", nargs="*", default=[], dest="candidate_list",
                    help="saved .csv/.json list standing in for the new batch's packages")
    ap.add_argument("--delivered", nargs="*", default=[], help="folders/zips of shipped batches, or saved .csv/.json lists")
    ap.add_argument("--out", default="dedup-report", help="report folder (default ./dedup-report)")
    ap.add_argument("--build-delivered-list", metavar="CSV", help="write a reusable delivered list and exit")
    ap.add_argument("--no-fail", action="store_true", help="exit 0 even when duplicates are found")
    a = ap.parse_args()

    delivered, dproblems = load_delivered(a.delivered)
    if a.build_delivered_list:
        if not delivered:
            print("nothing delivered was found in --delivered", file=sys.stderr)
            return 2
        write_csv(a.build_delivered_list, delivered, ["task_name", "sha256", "source"])
        print("wrote %d delivered entries to %s (%d unreadable packages)" % (len(delivered), a.build_delivered_list, len(dproblems)))
        for p in dproblems[:20]:
            print("   unreadable:", p["path"], "-", p["error"])
        return 0
    if not a.candidates and not a.candidate_list:
        ap.error("--candidates or --candidate-list is required (or use --build-delivered-list)")

    by_full = {}
    by_leaf = {}
    by_sha = {}
    for e in delivered:
        if e.get("task_name"):
            by_full.setdefault(e["task_name"].strip().lower(), e["source"])
            by_leaf.setdefault(leaf(e["task_name"]), e["source"])
        if e.get("sha256"):
            by_sha.setdefault(e["sha256"].lower(), e["source"])

    cands = [read_package(z) for z in find_zips(a.candidates)]
    cands += load_candidate_list(a.candidate_list)
    if not cands:
        print("no candidate packages or list rows were found", file=sys.stderr)
        return 2
    excluded, unread = [], []
    for r in cands:
        if r["error"]:
            r["reason"] = "unreadable: " + r["error"]
            unread.append(r)
        elif r["task_name"].strip().lower() in by_full:
            r["reason"] = "already delivered by name (%s)" % by_full[r["task_name"].strip().lower()]
        elif leaf(r["task_name"]) in by_leaf:
            r["reason"] = "already delivered by name, ignoring namespace (%s)" % by_leaf[leaf(r["task_name"])]
        elif r["sha256"] in by_sha:
            r["reason"] = "same archive bytes already delivered (%s)" % by_sha[r["sha256"]]
        if r.get("reason"):
            excluded.append(r)
    groups = {}
    for r in cands:
        if not r.get("reason"):
            groups.setdefault(leaf(r["task_name"]), []).append(r)
    keep = []
    for g in groups.values():
        g.sort(key=lambda x: (-x["mtime"], x["zip_name"]))   # newest archive first
        keep.append(g[0])
        for other in g[1:]:
            other["reason"] = "duplicate within this batch of %s (kept the newer archive)" % g[0]["zip_name"]
            excluded.append(other)
    for r in keep:
        r["name_differs_from_zip"] = leaf(r["task_name"]) != r["zip_name"].lower()

    os.makedirs(a.out, exist_ok=True)
    cols = ["zip_name", "task_name", "sha256", "path", "toml_path"]
    write_csv(os.path.join(a.out, "keep.csv"), sorted(keep, key=lambda r: leaf(r["task_name"])), cols + ["name_differs_from_zip"])
    write_csv(os.path.join(a.out, "excluded.csv"), sorted(excluded, key=lambda r: r["zip_name"]), cols + ["reason"])
    count = lambda key: sum(1 for r in excluded if r["reason"].startswith(key))  # noqa: E731
    summary = {
        "candidates_read": len(cands),
        "unreadable": len(unread),
        "already_delivered_by_name": count("already delivered by name"),
        "already_delivered_by_bytes": count("same archive bytes"),
        "duplicate_within_batch": count("duplicate within"),
        "unique_new_tasks": len(keep),
        "zip_name_differs_from_task_name": sum(r["name_differs_from_zip"] for r in keep),
        "delivered_reference": {"entries": len(delivered), "names": len(by_full), "unreadable_packages": len(dproblems),
                                "sources": sorted({str(e["source"]) for e in delivered})},
    }
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8"), indent=1)
    for k, v in summary.items():
        if k != "delivered_reference":
            print("%-34s %s" % (k, v))
    print("%-34s %d entries from %d sources" % ("delivered reference", len(delivered), len(summary["delivered_reference"]["sources"])))
    print("reports in", os.path.abspath(a.out))
    bad = len(excluded) > 0
    return 0 if (a.no_fail or not bad) else 1


if __name__ == "__main__":
    sys.exit(main())
