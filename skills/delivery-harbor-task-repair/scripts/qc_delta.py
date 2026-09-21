import json, glob, collections
import sys
if len(sys.argv) < 3:
    raise SystemExit("usage: qc_delta.py BEFORE_TASKS_DIR AFTER_TASKS_DIR")
BEFORE, AFTER = sys.argv[1], sys.argv[2]
def load(root):
    return {json.load(open(p))["task"]["name"]: json.load(open(p)) for p in sorted(glob.glob(root+"/*/report.json"))}
b, a = load(BEFORE), load(AFTER)
print("tasks with a BEFORE report:", len(b), "| with an AFTER report:", len(a))
print("no after-report:", sorted(set(b)-set(a)))
print()
tb=ta=0
for name in sorted(a):
    bf=[f for f in b[name]["findings"] if f["outcome"]=="fail"]
    af=[f for f in a[name]["findings"] if f["outcome"]=="fail"]
    tb+=len(bf); ta+=len(af)
    bc=collections.Counter(f["area_id"] for f in bf)
    ac=collections.Counter(f["area_id"] for f in af)
    print(f"### {name}   {len(bf)} -> {len(af)} fails")
    for area in sorted(set(bc)|set(ac)):
        d=ac[area]-bc[area]
        mark = "  (unchanged)" if d==0 else (f"  ({d:+d})")
        print(f"     {area:34s} {bc[area]:2d} -> {ac[area]:2d}{mark}")
both = len(set(a) & set(b))
print(f"\nRAW TOTALS over the {both} task(s) with BOTH reports: {tb} -> {ta}  (net {ta-tb:+d})")
missing = sorted(set(b) - set(a))
if missing:
    print(f"NO AFTER-REPORT ({len(missing)}) - unmeasured, not passing: {missing}")
