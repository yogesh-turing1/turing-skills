---
name: harbor-batch-dedup
description: Make sure a new Harbor/Shannon batch contains no task that was already delivered, and no task twice. Use before packaging or shipping a batch, when asked to "check for duplicates", "make sure none of these were shipped before", or to compare a candidate batch against earlier deliveries. Identity is the declared task.toml [task] name, never the bucket folder or the zip file name. Self-contained: one standard-library Python script, no other repo or tool needed.
---

# Harbor batch deduplication

Stops batch N+1 from re-delivering batch N. Everything needed is in this folder:
`scripts/dedup_check.py` (Python 3.8+, standard library only).

## Rules

- **Identity is the declared `task.toml` name.** The script reads `[task] name` from
  the package's own top-level `task.toml` (the shallowest one, never one under
  `environment/` or `evaluations/`). Never trust the bucket folder or the zip name:
  about 20% of source folders are malformed and roughly a quarter disagree with
  their declared name.
- **Namespaces are ignored for matching.** `obi/gen-g63-...` and `gen-g63-...` are the
  same task.
- **Same bytes are the same task.** An archive whose sha256 was already delivered is
  excluded even if its name changed.
- **Unreadable is not new.** A package whose `task.toml` cannot be read is held out
  and listed, never assumed to be a fresh task.
- **Read-only.** The script never writes to, moves or deletes any input. If the
  packages sit in a GCS bucket, download them first; never write to the bucket.
- **The check is only as good as the delivered reference.** If a shipped batch is
  left out of `--delivered`, its tasks will pass as new. Always list which batches
  the reference covered.

## Steps

**1. Gather the delivered reference.** Every batch already shipped, as any mix of:
folders of the shipped zips, single zips, or saved lists (`.csv` with a `task_name`
column and optional `sha256`; or a `.json` manifest with `tasks[].task_name`).

Optionally save it once as a reusable list, so later checks don't need the zips:

```bash
python3 scripts/dedup_check.py --build-delivered-list delivered.csv --delivered ./batch-1 ./batch-2 ./batch-3
```

**2. Run the check on the candidate batch.**

```bash
python3 scripts/dedup_check.py --candidates ./new-batch --delivered delivered.csv ./batch-4 --out ./dedup-report
```

When the candidate batch exists only as a manifest — the usual case before
anything is packaged — give it as a list instead, in the same `.csv` / `.json`
shapes `--delivered` takes. Both can be given together.

```bash
python3 scripts/dedup_check.py --candidate-list candidates.json --delivered delivered.csv --out ./dedup-report
```

A list row's `declared_name` wins over its `name`. **Supply it.** A pipeline
manifest's `name` is the folder key, and the folder is not the identity: on the
275-task batch of 6 Oct 2026, 18 of 275 declared a different name, and two
packages with different folder names — `…-linear` and `…-outlook` — declared the
*same* name. A list carrying only folder names cannot see either, and this check
is then worth very little.

**3. Read the result.** The script prints a summary and writes three files to
`--out`:

| File | Contents |
|---|---|
| `summary.json` | counts below, plus which sources the delivered reference came from |
| `keep.csv` | the unique, never-delivered tasks to put in the batch |
| `excluded.csv` | every excluded package and why |

Exclusion reasons: already delivered by name, already delivered by name ignoring
namespace, same archive bytes already delivered, duplicate within this batch (the
newest archive is kept), unreadable.

**A clash inside the candidate batch is not automatically a redelivery.** The
script keeps the newer archive and excludes the other, which is right when they
are the same task packaged twice and wrong when two different tasks declare one
name. Before dropping anything from `excluded.csv` with a `duplicate within this
batch` reason, compare the two packages' connector tools: if they differ, rename
one and ship both.

Exit code 0 = clean, 1 = something was excluded (the batch is not clean as given),
2 = bad arguments. Add `--no-fail` to always exit 0.

**4. Build the batch from `keep.csv` only.** `name_differs_from_zip` marks packages
whose zip name is not their declared name; consider renaming those zips to the
declared name before delivery.

**5. After the batch ships, add it to the delivered reference** (re-run step 1 with
the new batch included), so the next batch is checked against it.

## Report

State, with counts: candidates read, unreadable, already delivered (by name, by
bytes), duplicated within the batch, unique new tasks, and the batches the delivered
reference covered.
