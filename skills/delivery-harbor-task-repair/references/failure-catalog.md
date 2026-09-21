# Failure catalog — observed baseline

Recorded from a full five-layer client QC run over 5 randomly sampled batch-5 packages
(57 findings, 0 of 5 clean) plus a programmatic run over all 232. These are the actual
failure shapes, with the evidence that identified each.

## 1. Doubled digest — 169 of 232 packages

```
FROM python:3.12-slim-bookworm@sha256:782412e8…2254@sha256:a116514e…8134
```

Split: 27 identical pairs, 142 differing pairs.

Reviewer's own words:

> "two digests concatenated on one reference, which is not parseable as an OCI image
> reference. Modal rejected it."

**Cascade.** One defect produced findings in four areas: `layer4_environment_files`
(`ImageBuildError` → `Sandbox not found`), `layer1_package_consistency`
(`image_reference_immutability`, `manifest_environment_consistency`), `layer3_oracle`
(`e2b: pass=False, modal: pass=False`), `layer5_cross_trial_calibration`
(score-eligible denominator 0 of 3).

**Which digest is authoritative.** Three independent lines of evidence:
- `client_qc/access-receipt.json` names the second digest, never the first
- digest #1 is the identical value `782412e8…` in 168 of 169 cases
- digest #2 values match what packages that build successfully pin alone

**The programmatic checker scores these as correctly pinned.** Its regex
`.+@sha256:[0-9a-f]{64}$` anchors only the tail. All 169 pass Layer 1's mechanical
image check while being unbuildable.

## 2. Fractional final reward

The recorded artifacts were already binary — every `reward.txt` under `evaluations/`
read 0 or 1, with `reward_raw.txt` beside the rewritten ones. **Only the verifier code
was missed.** An earlier sweep fixed evidence and not source.

Writers found:

| Shape | Example |
|---|---|
| direct fraction | `(out/'reward.txt').write_text(str(r['reward']))` |
| gated fraction | `gated = round(raw * CORE_GATE_FACTOR, 6) if failed_core else round(raw, 6)` |
| composite total | `(LOG_DIR / "reward.txt").write_text(f"{reward['total']}\n")` |

Contract, verbatim from the rubric:

> "PASS only when the final reward range is exactly {0, 1}. FAIL when partial,
> weighted, averaged, or other fractional final values in (0, 1) are possible.
> Continuous criterion-level scores are acceptable only when the final task reward is
> deterministically binarized."

Correct reference shape, from the one package that passed: `tests/test.sh` doing
`echo 1` / `echo 0` directly, and no `reward_raw.txt` because nothing needed rewriting.

**Side effect worth knowing.** Binarization also closed
`layer5_verifier_fairness_static__scoring_proportionality` — once any failed check
zeroes the score, a missing deliverable can no longer be masked by partial credit. Two
findings that looked like hand-authoring work closed for free.

## 3. Solvability evidence from the Oracle

`evaluations/solvability/r1` with `agent=oracle`, `agent/oracle.txt` present, no
trajectory.

> "no complete terminal reward-1.0 non-Oracle model result/trajectory pair with exact
> agent/model provenance and executed verifier"

In every observed case the required evidence already existed in
`evaluations/difficulty/` — a run at reward 1.0, `agent=opencode`,
`model=glm/glm-5.2`, trajectory present. 14 of 14 recoverable.

The framework prescribes the fix itself:

> "Attach a reward-1.0 non-oracle model trajectory/result pair with exact provenance
> under task_folder/evaluations/solvability/."

## 4. Stability frozen from the Oracle

All 22 observed stability failures shared one cause: `frozen_source: "Frozen Oracle
replay and materialized artifacts."` — **zero** were frozen from a model trajectory.

An oracle replay runs `solution/solve.sh`; there is no agent session, so no
`agent/trajectory.json` is written and the declared `frozen_trajectory_sha256` is a
digest of the run rather than of any file. Nothing in the package can ever match it.
This is why "hash mismatch" cases match nothing anywhere.

Split by recoverability: 14 had a passing model run to re-freeze from; 8 were 0/4 with
no model pass in existence.

**Artifacts are not retained.** `artifacts/manifest.json` reads
`[{"source": "/logs/artifacts", "status": "empty"}]`, so the graded deliverables must
be rebuilt by replaying the trajectory's own tool calls. Trajectories record full
arguments (`bash` commands, `write` content, `edit` old/new strings), which makes this
possible.

**The uid trap.** A replay that reports `rebuilt workspace scores <empty>` is almost
always this, not a real mismatch:

```
$ docker exec $CID mkdir -p /logs/verifier
mkdir: cannot create directory '/logs': Permission denied
```

Dockerfile ends `USER taskuser`; `/` is root-owned; `test.sh` always `exit 0`s so
nothing surfaces the failure. Re-run with `-u 0`: `4 passed`, `reward.txt → 1`.

## 5. Duplicate evaluation battery — 19 of 232 packages

Two batteries present, e.g. `evaluations/difficulty/` (later) and
`evaluations/glm-5.2/` (earlier, superseded, different `task_checksum`, result-only).

**Only the AI reviewer sees this.** `audit_evaluations.py` builds the difficulty axis
from `evaluations/difficulty` alone and reported `pass` with 4 records both before and
after removal. There is no programmatic fail→pass transition to demonstrate.

The trap in reverse: the package's docs cited the *orphaned* battery as the difficulty
evidence, so removing it requires repointing `README.md` and `review.csv` at the
surviving one.

## Infrastructure artifacts — never count these as package defects

Observed when model endpoints were missing:

| Finding | Actual cause |
|---|---|
| `environment_interaction__agent_tool_schema_compatibility` | codex speaks OpenAI Responses API over websocket; endpoint returned `400 Bad Request` + `"You must provide a model parameter"` |
| `environment_interaction` (opencode lane) | `401 'The API key you provided is invalid.'` from Fireworks |
| `artifact_integrity`, `content_format_validity` | zero agent turns → no deliverables to grade |
| `connector_interaction` | gym seeded and 14 tools ready; agent's only MCP call was `tools/list` before the 401 |

Every one of these reports the environment itself as healthy — *"the modal sandbox,
image build and codex install themselves worked"*, *"gym seeded and 14 tools ready"*.

**One genuine finding survives working credentials:**
`environment_interaction__failure_phase_classification` — an infra failure is scored
identically to a genuine bad attempt (`"eligible": true`, reward 0.0). Pre-existing,
not caused by binarization.

## Controlled test of this skill — 2026-09-19

One task (`code-c723`, a fractional reward writer with three declarations describing
it), two arms, identical starting trees, single variable: whether the agent read this
skill. Digest defect pre-fixed in both so it could not compete for attention.

| | Control (no skill) | Treatment (skill) |
|---|---|---|
| Code fix correct | yes | yes |
| Verification depth | 7 branches + 864-shape sweep | 7 controls + synthetic payloads |
| Declarations reconciled | yes — README ×2, docstring, header | yes — README, docstring, header |
| `evaluations/` files modified | **70** | **0** |
| QC documents modified | **2** | **0** |
| Flagged for audit-trail tampering | **yes** | no |

**Declaration reconciliation did NOT distinguish the arms.** The control updated every
stale declaration unprompted. On this evidence that guidance is redundant — a capable
agent does it anyway. It is retained because it has failed twice in the field, not
because this test justified it.

**The prohibition is what earned its place.** The control rewrote `reward.txt`,
`reward.json`, `reward_detail.json` and `result.json` across all 14 evaluation runs,
then edited `review.csv` and `finalization_review_reconcile.json`. Its reasoning was
careful — re-derived from each run's own recorded verdicts, no verdict changed,
calibration confirmed unchanged at 2/4 — and it was still rewriting the record of what
happened, reproducing the exact defect that put this batch in QC: evidence binarized to
look right while the contract lives in the code.

The treatment hit the same anomaly and refused it: *"If the client wants packaged
evidence regenerated under the fixed code, that needs re-running the trials, not editing
the artifacts."*

**Lesson for this skill's shape:** the value is in the prohibitions, not the procedures.
A capable agent finds the write site, verifies in a container and updates the docs on its
own. What it will not do unprompted is refuse the tempting fix.

## Counting

Compare **raw finding counts**, per task and per area. Comparing sets of
`(area_id, criterion)` pairs dedupes repeated findings and will not reconcile with
totals — six `environment_interaction` findings sharing one criterion collapse to one.

Report tasks with no after-report separately. A blocked pipeline is unmeasured, not clean.
