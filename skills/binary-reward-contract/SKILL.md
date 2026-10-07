---
name: binary-reward-contract
description: Convert a Harbor task package's reward files to the binary 0/1 contract - detect which of the five scoring families it uses, rewrite the reward writes, convert recorded evaluation runs, and preserve the graded value in reward_raw.txt. Use when preparing packages for delivery, when a reward comparison shows every task changing, or when asked about reward.txt, reward.json, reward_raw.txt or the harbor-binary-reward marker.
---

# Binary reward contract

`reward.txt` and `reward.json` carry **1** when every check passed and **0** otherwise. Nothing in
between. The pass condition itself is unchanged — only the value written below 1.0 changed, from the
weighted share of checks passed to a flat 0.

A run scores 1 only when all three hold: nothing failed or errored, the graded reward is exactly
1.0, and the trial is score-eligible.

Per-check detail is never touched: `verifier_summary.json`, `reward_detail.json` and `ctrf.json`
keep the full payload. Every file edited under this contract carries the marker
`harbor-binary-reward v1`.

**Where the marker goes.** In verifier code, as a comment. In a recorded run's `reward.json`, as the
`"_marker": "harbor-binary-reward v1"` key (the shape infra's Final QC checks). Never in a `reward.json`
the live verifier writes - Harbor rejects a `reward.json` with any non-numeric value - and never in
`reward.txt`, which must parse as a bare number.

**Harbor's read order.** Harbor (0.21/0.22) reads `reward.json` FIRST; every value in it must be a
number. It falls back to `reward.txt` only when there is no `reward.json`. So a writer that binarizes
`reward.txt` but still writes a fractional `reward.json` is not compliant - change both, and keep them
agreeing.

---

## The two places it applies

**The scoring code**, so future runs write 0/1 — the reward writes inside the package's verifier.

**The recorded runs already in the package**, under `evaluations/`: `verifier/reward.txt`,
`verifier/reward.json` and `result.json` (`verifier_result.rewards`) all carry 0/1 only. The graded
value of every rewritten run is kept beside it in **`verifier/reward_raw.txt`** — it is evidence, not
noise, and discarding it destroys the only record of how close a failing run was.

Converting recorded runs is required, not optional, and it is not tampering: the verdict does not
change and the native value is kept. Rounding up (`0.999` to `1`) or converting the evidence while the
code still writes fractions is tampering.

**Touch only runs that need converting.** A run already at exactly 0 or 1 stays byte-for-byte as it
was - above all `evaluations/solvability/r1`, whose `result.json` bytes are hashed into the stability
repeats' Oracle replay binding; re-serialising it breaks that binding.

**Downstream checks see a conversion, not a score change.** `result.json`, `reward.json` and
`reward.txt` agree after conversion, so the reward-conflict checks stay quiet, and the `_marker` key in
a recorded `reward.json` is ignored by every packaged-run reader. One known exception: infra's shipping
gate (`harbor_gce/validate_tasks.py` `run_reward`) also reads `verifier_summary.json` as a reward source.
When that summary keeps the fractional total without a boolean `reward.pass`, it reports the run's reward
artifact as holding "no number". That is this conversion showing, not a defect; report it as such.

---

## Detect the family before editing anything

Five scoring families, identified by which file does the reward write. Check in this order and stop
at the first match — several packages contain more than one of these paths and the ordering is what
keeps the classification stable.

| Family | Identified by | What changes |
|---|---|---|
| **connector engine** | `tests/test_outputs.py` (+ its `environment/_app/tests` mirror) | Both scoring paths write `_binary_reward(reward)` — the engine's own pass verdict — instead of `reward["total"]`. Helper goes after `LOG_DIR`. Two reward.txt + two reward.json writes per file, and the mirror must match |
| **generation-2 runner** | `tests/run_verifier.py` | `binary_reward(payload)` replaces the graded value in the reward.txt / reward.json writes |
| **runner-writer** | `tests/rl_world_verifiers/runner.py` → `write_outputs` | Flat binary `reward.json` + `reward.txt`; the full graded payload moves to `reward_detail.json` |
| **hand-written** | `tests/test.sh`, `score.py`, `score_outputs.py`, `reward_from_pytest.py`, `test_outputs.py` | Replace the line computing the fraction with its all-checks-passed form. Note the edited line at the top of the file |
| **already binary** | pytest gate / CTRF all-pass, or hand-written 0/1 writes | Nothing. Roughly 40% of a typical corpus is already compliant |

**Do not classify by the first matching filename alone.** A package can ship
`tests/test_outputs.py` as a helper while its real scoring lives in `run_verifier.py`; checking the
connector-engine signature first, then falling through, is what keeps the label honest. A
misclassified family writes a correct-looking `MODIFICATIONS` record describing an edit that never
happened.

---

## Editing the archive

Surgical ZIP rewrite, as everywhere else: stream entries, edit only the targets, copy every other
entry's bytes and `ZipInfo` verbatim, then assert the set of CRC-changed entries equals exactly the
intended set and abort on any surprise. The `reward_raw.txt` files are additions, not modifications —
assert them separately.

Record per package: the family, how many recorded runs were converted, how many were already binary,
and which files were edited.

---

## Which edits make recorded runs stale

Harbor binds each run to a content hash of `task.toml`, `instruction.md`, `README.md`, `environment/`,
`tests/`, `solution/` and `steps/`. **The scoring-code edit (under `tests/`, and its `_app/tests`
mirror) changes that hash, so every recorded run and QC report for that package goes stale.** Converting
the recorded runs under `evaluations/` does not. Any edit at all breaks an embedded `qc_report.html`
certificate.

After converting, run `delivery-harbor-task-repair/scripts/stale_runs.py BEFORE AFTER` (directories or
zips). Do not re-run QC or batteries automatically: tell the user which tasks went stale and which
files moved the hash, and ask how to proceed.

---

## The trap this creates downstream

**Any before/after reward comparison must be against the 0/1 values.** Compare a converted package
against its pre-conversion graded rewards and every task looks like it changed, because the scale
moved rather than the result. This bites hardest when validating a new verifier script: the script
is innocent and the diff is an artefact of the contract.

The pass/fail verdict is identical either way. If a task's band moves, the cause is not this
conversion — recompute from `reward_raw.txt` and find out what actually happened.

---

## Expected shape of a corpus

From a 180-package conversion, as a sanity check on your own run:

```
already binary (pytest gate / CTRF all-pass)   72
generation-2 runner                            54
hand-written                                   26
connector engine                               25
already binary (hand-written 0/1 writes)        3
                                    packages  180   files edited  133
```

Per package, 14–19 recorded runs is normal. A package reporting zero runs converted and zero already
binary has no recorded evaluations — that is a battery problem, not a reward problem, and belongs in
the difficulty checks instead.
