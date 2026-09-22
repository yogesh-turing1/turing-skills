---
name: harbor-record-delivery
description: File a completed Harbor delivery into the delivery record repo so it can be audited later — normalise the manifest, collect the four generator inputs, build both report editions, record the client/internal delta and known issues, and validate until the checker passes. Use after a batch has been delivered, or when asked to record, audit-trail, or reconstruct what was sent in a delivery.
---

# Record a Harbor delivery

Shipping is not the finish line. `recorded` is. This skill takes a delivered batch
and makes it reconstructable.

Repo: `github.com/yogesh-turing1/harbor-deliveries`
Read `METHODOLOGY.md` there first.

## The test

```bash
python tools/check_delivery.py deliveries/<batch>
```

Exit zero means recorded. Anything else is the to-do list. Do not hand-wave past it
and do not fabricate inputs to make it green — an honest gap beats a check bought
with invented data.

## Steps

**1. Create the folder and normalise.**

```bash
mkdir -p deliveries/<batch>/{inputs/source,selection,reports/client,reports/internal,issues}
cp <source-manifest>.json deliveries/<batch>/inputs/source/
python tools/normalise.py --in deliveries/<batch>/inputs/source/<src>.json \
       --delivery-id <batch> --batch-label <N> --out deliveries/<batch>/inputs/manifest.json
```

Normalisation is lossless — unmapped source fields are kept under `extra`, and the
verbatim original stays in `inputs/source/`. Every prior batch used a different
schema; only `source_uri` and `task_name` were common to all five.

**2. Collect the four generator inputs** into `inputs/`:
`manifest.json`, `delivery_manifest.csv`, `audit-14-factor-findings.csv`,
`MODIFICATIONS.json` (+ optional `hygiene.json`). These four are the completeness
test — with them the internal report rebuilds from scratch; without them it cannot
be rebuilt at all, ever.

**3. Build both report editions.**

```bash
python work/tooling/internal-delivery-report-share/build_internal_report.py \
  --mods MODIFICATIONS.json --manifest <..>/manifest.json \
  --inventory delivery_manifest.csv --audit audit-14-factor-findings.csv \
  --out Harbor-Delivery-Report-INTERNAL --pdf
```

Always pass `--hygiene` when a sweep deliberately left something in place —
derived mode can only report what the modification record accounts for, so a
correctly-unredacted placeholder silently vanishes otherwise.

**4. Write `reports/DELTA.md`.** Client editions print all-pass. A `0 not applicable`
across fourteen factors overstates coverage — `Connectors` cannot apply to
non-connector tasks. Record the real denominators and any headline disagreement as
a **note, not a correction**. The delivered figure stands as sent.

**5. Write `issues/known-issues.md`.** Every `INFO` and every accepted `FLAG` that
shipped anyway, with the reason. This is where "green for the client, honest
internally" actually lives.

**6. Update the derived files.**

```bash
python tools/build_pool.py    # must report 0 cross-batch duplicates
python tools/build_index.py   # INDEX.md is derived; never hand-edit
python tools/check_delivery.py deliveries/<batch>
```

**7. Commit.** The delivery folder is append-only from here. Corrections go in
`DELTA.md`, never by editing a shipped manifest.
