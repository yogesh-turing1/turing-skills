---
name: harbor-deliver-batch
description: Run a Harbor/Shannon delivery end to end — cut a batch from the accepted GCS prefix, classify it, audit the fourteen factors, remediate, package, and stage it for shipping. Use when asked to prepare, cut, package or ship a batch of Harbor task archives, or when someone asks "what can we deliver next".
---

# Deliver a Harbor batch

Runs the delivery. Recording it afterwards is `harbor-record-delivery` — that is a
separate step and it is not optional.

## Before anything

Read `work/tooling/repackaging-qc-gate/SKILL-delivery-packager.md`. It is the
full seven-phase procedure and it is FULLER than the public copy in `turing-skills`
(which is redacted and drops Phase 7, the deliverable checklist and the
environment gotchas). This skill is the operating wrapper, not a replacement.

Read `harbor-deliveries/METHODOLOGY.md` for the states and the definition of done.

## Non-negotiable

- **GCS accepted prefix is read-only.** Never `cp` up, never `rm`, never overwrite.
- **Join on the declared `task.toml` name**, never the bucket folder. 20% of source
  folders are malformed and 155 of 546 disagree with their declared name. Joining
  on the folder has already produced phantom re-delivery alarms once.
- **Work in one owned directory.** Not `/home/<someone-else>/`.
- **Linux only.** `upload_auto_batch.py` shells out to `gcloud`; on Windows that is
  `gcloud.cmd` and it fails with `FileNotFoundError`, which the script misreports
  as an auth failure. Windows long-path extraction also silently drops files and
  produces false validation passes.

## Steps

**1. Establish the candidate pool.**
Every accepted-prefix folder not already delivered. `harbor-deliveries/pool/delivered.csv`
is the exclusion list. Run `tools/build_pool.py` first — it exits non-zero if any
folder already appears in two batches.

**2. Classify — metadata first, archives second.**
`harbor-deliveries/tools/classify_candidates.py` reads `task.toml` and
`evaluations/difficulty/r*/verifier/reward.json` straight out of each zip without
extracting, one archive on disk at a time. Yields declared name, connector flag,
four rewards, pass count, difficulty band.

Difficulty rules, derived from delivered batch-01, not assumed:
- success = reward **exactly 1.0** (a 0.625 is a failure)
- 3 successes → easier · 1-2 → harder · 0 or 4 → excluded
- fewer than four recorded rewards → excluded

**3. Select.** Family-adjudicate by declared name. Balance domains and connector
share; quota the easier band separately or the mix collapses onto one bucket.
Freeze `selection_manifest.csv` and record its SHA-256 — version it, never overwrite.
Emit the availability pool so the next operator can cut a non-overlapping batch.

**4. Audit the fourteen factors.** Real denominators. `Connectors` scores against
connector tasks only; `LLM judge consistency` against the judged subset. Verify
every flag before reporting it.

**5. Remediate only what is genuinely wrong.** Frozen baseline first: copy to
`baseline/`, hash everything, `chmod -R a-w`. Never rewrite a declared hash to make
a check pass. See the `delivery-harbor-task-repair` skill for the five common fixes.

**6. Package and verify.** Difficulty/category folders, reconciled manifest, ZIP
bytes copied unchanged. All completion checks must pass: archives readable,
recomputed SHA-256 and sizes matching, manifest and disk agreeing both ways,
difficulty recomputed independently from raw rewards.

**7. Stage.** Copy to `gs://yogesh-harbor-deliveries/ready-for-delivery/<batch>/`.
Staging is deletable by design; nothing there is a record.

**8. Ship** (only on explicit go): copy to `gs://yogesh-harbor-delivered/<batch>/`,
verify the copy, THEN remove from staging. Never move first and verify after.
That bucket has 90-day retention — a mistaken upload is stuck for 90 days.

## Then

Invoke `harbor-record-delivery`. A batch that ships without being recorded is
exactly batch-04.1: 232 tasks with no internal record of what was checked or changed.
