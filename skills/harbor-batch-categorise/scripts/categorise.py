#!/usr/bin/env python3
"""The Company Bench label: <harness> · <connector count>.

Implements COMPANY-BENCH-CATEGORIES.md. Two independent parts:

  harness  which environment the task runs in - Aster or Zeta - read from the
           Docker image first, and only then from the connectors it uses.
           Google Drive and Slack exist on both, so they settle nothing and
           the label stays "Company Bench" rather than guessing one.
  count    how many distinct real tools it declares. `harbor` is the test
           runner and tags like read-only are not tools; `slack` and
           `slack-gym` are the same tool named twice.
"""
import re

# a tool is a *-gym, or one of these four written bare
BARE_TOOLS = {"slack", "linear", "github", "notion"}
NOT_TOOLS = {"harbor", "read-only", "quality-review"}
# only Zeta has its own SQL tool
ZETA_ONLY = {"zeta3-sql"}
# these exist only on Aster
# `gws` is what the packages call Google Workspace, which the doc lists as Aster;
# the delivered set labels every gws task aster, so the alias is not a guess
ASTER_ONLY = {"github", "notion", "linear", "outlook", "email-calendar",
              "google-workspace", "gws"}
ZETA_IMAGE = re.compile(r"zeta", re.I)
ASTER_IMAGE = re.compile(r"aster", re.I)
DIGEST = re.compile(r"@sha256:([0-9a-f]{64})", re.I)

# Images whose NAME does not say which harness they are, pinned by digest.
#
# A repository name is not evidence: `company-bench-private` has hosted both a
# zeta-tagged build and digests whose tasks use only Aster tools. So only exact
# digests go here, each with what settled it - never a repo, never a tag prefix.
KNOWN_IMAGES = {
    # connectors-rl-gym/connectors-harness, tagged company-synthetic-*.
    # 57 tasks across these three digests use no Zeta-only tool, and every tool
    # among them with delivered history is Aster-only (email-calendar 29/0,
    # outlook 27/0, gws 24/0, linear 35/0, github 11/0, notion 21/0).
    "b1374cd8a392ea66f9a649e700a1498e8fcb03ee35776362db7cc15dc3049b89": "Aster",
    "9838c0f4d39fc81a11797c4a2d7bf2ccc0b3373d10130aef25bae061575aae24": "Aster",
    "35aa27a1bbdcb7610cf038db4c0f597b21563d9a7aac2063dbd68a250ef1496a": "Aster",
}


def normalise(tool):
    """`slack-gym` and `slack` are one tool; strip the suffix to compare."""
    t = str(tool or "").strip().lower()
    return t[:-4] if t.endswith("-gym") else t


def real_tools(connectors):
    out = set()
    for c in connectors or []:
        t = normalise(c)
        if not t or t in NOT_TOOLS:
            continue
        raw = str(c).strip().lower()
        if raw.endswith("-gym") or t in BARE_TOOLS:
            out.add(t)
    return out


def connector_count(connectors):
    return len(real_tools(connectors))


def harness_of(image, connectors):
    """The image decides it when there is one; the tools are the fallback."""
    img = str(image or "")
    d = DIGEST.search(img)
    if d and d.group(1).lower() in KNOWN_IMAGES:
        return KNOWN_IMAGES[d.group(1).lower()]
    if ASTER_IMAGE.search(img):
        return "Aster"
    if ZETA_IMAGE.search(img):
        return "Zeta"
    tools = real_tools(connectors)
    if tools & ZETA_ONLY:
        return "Zeta"
    if tools & ASTER_ONLY:
        return "Aster"
    return "Company Bench"


def label(image, connectors):
    n = connector_count(connectors)
    if n == 0:
        return "%s · connectors not read" % harness_of(image, connectors)
    return "%s · %s" % (harness_of(image, connectors),
                        "Single connector" if n == 1 else "Multi-connector")


# ----------------------------------------------------------------------- cli
def _read_package(path):
    """name, declared name, image and tools from a package folder or zip."""
    import io
    import os
    import re as _re
    import zipfile

    def pick(names, suffix):
        hits = [n for n in names if n.endswith(suffix)]
        return sorted(hits, key=lambda n: n.count("/"))[0] if hits else None

    toml_text = docker_text = ""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            t = pick([n for n in names if "_app" not in n], "task.toml")
            d = pick(names, "environment/Dockerfile")
            toml_text = z.read(t).decode("utf-8", "replace") if t else ""
            docker_text = z.read(d).decode("utf-8", "replace") if d else ""
        name = os.path.basename(path)[:-4]
    else:
        for root, _dirs, files in os.walk(path):
            if "task.toml" in files and not toml_text:
                toml_text = open(os.path.join(root, "task.toml"), encoding="utf-8",
                                 errors="replace").read()
            if "Dockerfile" in files and root.endswith("environment"):
                docker_text = open(os.path.join(root, "Dockerfile"), encoding="utf-8",
                                   errors="replace").read()
        name = os.path.basename(path.rstrip("/\\"))

    declared, conns = "", []
    m = _re.search(r"\[task\](.*?)(?=^\[|\Z)", toml_text, _re.S | _re.M)
    if m:
        n = _re.search(r"^\s*name\s*=\s*[\"']([^\"']+)[\"']", m.group(1), _re.M)
        declared = n.group(1) if n else ""
    # tools live under mcp_servers_extended; `keywords` on a connector task
    # routinely reads just ["harbor"], which is why it is not consulted
    for block in _re.finditer(r"\[\[metadata\.mcp_servers_extended\]\](.*?)(?=^\[|\Z)",
                              toml_text, _re.S | _re.M):
        n = _re.search(r"^\s*name\s*=\s*[\"']([^\"']+)[\"']", block.group(1), _re.M)
        if n:
            conns.append(n.group(1))
    img = ""
    f = _re.search(r"^\s*FROM\s+(\S+)", docker_text, _re.M | _re.I)
    if f:
        img = f.group(1)
    return {"name": name, "declared_name": declared, "image": img, "connectors": conns}


def main(argv=None):
    import argparse
    import collections
    import csv
    import json
    import os

    ap = argparse.ArgumentParser(description="Label Harbor packages with the Company Bench category.")
    ap.add_argument("--packages", nargs="*", default=[], help="package folders and/or zips")
    ap.add_argument("--collected", help="JSON list of {name, declared_name, image, connectors}")
    ap.add_argument("--out", default="categorise-report")
    a = ap.parse_args(argv)

    rows = []
    if a.collected:
        rows += json.load(open(a.collected, encoding="utf-8"))
    for p in a.packages:
        if os.path.isdir(p) and not any(f == "task.toml" for f in os.listdir(p)):
            for child in sorted(os.listdir(p)):
                full = os.path.join(p, child)
                if os.path.isdir(full) or full.lower().endswith(".zip"):
                    rows.append(_read_package(full))
        else:
            rows.append(_read_package(p))
    if not rows:
        ap.error("give --packages and/or --collected")

    for r in rows:
        r["n_connectors"] = connector_count(r.get("connectors"))
        r["harness"] = harness_of(r.get("image"), r.get("connectors"))
        r["label"] = label(r.get("image"), r.get("connectors"))
        r["tools"] = "|".join(sorted(real_tools(r.get("connectors"))))

    os.makedirs(a.out, exist_ok=True)
    cols = ["name", "declared_name", "label", "harness", "n_connectors", "tools", "image"]
    with open(os.path.join(a.out, "labels.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["label"]))

    lab = collections.Counter(r["label"] for r in rows)
    har = collections.Counter(r["harness"] for r in rows)
    summary = {"tasks": len(rows), "labels": dict(lab), "harness": dict(har),
               "with_image": sum(1 for r in rows if r.get("image")),
               "no_tools_read": sum(1 for r in rows if r["n_connectors"] == 0),
               "unresolved_harness": sum(1 for r in rows
                                         if r["harness"] not in ("Aster", "Zeta"))}
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8"),
              indent=1)

    print("%-40s %6s" % ("label", "tasks"))
    for k, v in sorted(lab.items(), key=lambda x: -x[1]):
        print("%-40s %6d" % (k, v))
    print("%-40s %6d" % ("TOTAL", len(rows)))
    print()
    print("%-18s %7s %7s %7s" % ("harness", "single", "multi", "total"))
    for h in sorted(har):
        s = sum(1 for r in rows if r["harness"] == h and r["n_connectors"] == 1)
        m = sum(1 for r in rows if r["harness"] == h and r["n_connectors"] >= 2)
        print("%-18s %7d %7d %7d" % (h, s, m, s + m))
    print()
    print("with an image      : %d of %d" % (summary["with_image"], len(rows)))
    print("no tools readable  : %d" % summary["no_tools_read"])
    print("harness unresolved : %d" % summary["unresolved_harness"])
    if summary["unresolved_harness"]:
        seen = collections.Counter(r["tools"] for r in rows
                                   if r["harness"] not in ("Aster", "Zeta"))
        for k, v in seen.most_common(10):
            print("    %-44s %4d" % (k or "(none)", v))
    print("\nwritten:", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ----------------------------------------------------------------------- cli
def _read_package(path):
    """name, declared name, image and tools from a package folder or zip."""
    import io
    import os
    import re as _re
    import zipfile

    def pick(names, suffix):
        hits = [n for n in names if n.endswith(suffix)]
        return sorted(hits, key=lambda n: n.count("/"))[0] if hits else None

    toml_text = docker_text = ""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            t = pick([n for n in names if "_app" not in n], "task.toml")
            d = pick(names, "environment/Dockerfile")
            toml_text = z.read(t).decode("utf-8", "replace") if t else ""
            docker_text = z.read(d).decode("utf-8", "replace") if d else ""
        name = os.path.basename(path)[:-4]
    else:
        for root, _dirs, files in os.walk(path):
            if "task.toml" in files and not toml_text:
                toml_text = open(os.path.join(root, "task.toml"), encoding="utf-8",
                                 errors="replace").read()
            if "Dockerfile" in files and root.endswith("environment"):
                docker_text = open(os.path.join(root, "Dockerfile"), encoding="utf-8",
                                   errors="replace").read()
        name = os.path.basename(path.rstrip("/\\"))

    declared, conns = "", []
    m = _re.search(r"\[task\](.*?)(?=^\[|\Z)", toml_text, _re.S | _re.M)
    if m:
        n = _re.search(r"^\s*name\s*=\s*[\"']([^\"']+)[\"']", m.group(1), _re.M)
        declared = n.group(1) if n else ""
    # tools live under mcp_servers_extended; `keywords` on a connector task
    # routinely reads just ["harbor"], which is why it is not consulted
    for block in _re.finditer(r"\[\[metadata\.mcp_servers_extended\]\](.*?)(?=^\[|\Z)",
                              toml_text, _re.S | _re.M):
        n = _re.search(r"^\s*name\s*=\s*[\"']([^\"']+)[\"']", block.group(1), _re.M)
        if n:
            conns.append(n.group(1))
    img = ""
    f = _re.search(r"^\s*FROM\s+(\S+)", docker_text, _re.M | _re.I)
    if f:
        img = f.group(1)
    return {"name": name, "declared_name": declared, "image": img, "connectors": conns}


def main(argv=None):
    import argparse
    import collections
    import csv
    import json
    import os

    ap = argparse.ArgumentParser(description="Label Harbor packages with the Company Bench category.")
    ap.add_argument("--packages", nargs="*", default=[], help="package folders and/or zips")
    ap.add_argument("--collected", help="JSON list of {name, declared_name, image, connectors}")
    ap.add_argument("--out", default="categorise-report")
    a = ap.parse_args(argv)

    rows = []
    if a.collected:
        rows += json.load(open(a.collected, encoding="utf-8"))
    for p in a.packages:
        if os.path.isdir(p) and not any(f == "task.toml" for f in os.listdir(p)):
            for child in sorted(os.listdir(p)):
                full = os.path.join(p, child)
                if os.path.isdir(full) or full.lower().endswith(".zip"):
                    rows.append(_read_package(full))
        else:
            rows.append(_read_package(p))
    if not rows:
        ap.error("give --packages and/or --collected")

    for r in rows:
        r["n_connectors"] = connector_count(r.get("connectors"))
        r["harness"] = harness_of(r.get("image"), r.get("connectors"))
        r["label"] = label(r.get("image"), r.get("connectors"))
        r["tools"] = "|".join(sorted(real_tools(r.get("connectors"))))

    os.makedirs(a.out, exist_ok=True)
    cols = ["name", "declared_name", "label", "harness", "n_connectors", "tools", "image"]
    with open(os.path.join(a.out, "labels.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["label"]))

    lab = collections.Counter(r["label"] for r in rows)
    har = collections.Counter(r["harness"] for r in rows)
    summary = {"tasks": len(rows), "labels": dict(lab), "harness": dict(har),
               "with_image": sum(1 for r in rows if r.get("image")),
               "no_tools_read": sum(1 for r in rows if r["n_connectors"] == 0),
               "unresolved_harness": sum(1 for r in rows
                                         if r["harness"] not in ("Aster", "Zeta"))}
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8"),
              indent=1)

    print("%-40s %6s" % ("label", "tasks"))
    for k, v in sorted(lab.items(), key=lambda x: -x[1]):
        print("%-40s %6d" % (k, v))
    print("%-40s %6d" % ("TOTAL", len(rows)))
    print()
    print("%-18s %7s %7s %7s" % ("harness", "single", "multi", "total"))
    for h in sorted(har):
        s = sum(1 for r in rows if r["harness"] == h and r["n_connectors"] == 1)
        m = sum(1 for r in rows if r["harness"] == h and r["n_connectors"] >= 2)
        print("%-18s %7d %7d %7d" % (h, s, m, s + m))
    print()
    print("with an image      : %d of %d" % (summary["with_image"], len(rows)))
    print("no tools readable  : %d" % summary["no_tools_read"])
    print("harness unresolved : %d" % summary["unresolved_harness"])
    if summary["unresolved_harness"]:
        seen = collections.Counter(r["tools"] for r in rows
                                   if r["harness"] not in ("Aster", "Zeta"))
        for k, v in seen.most_common(10):
            print("    %-44s %4d" % (k or "(none)", v))
    print("\nwritten:", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
