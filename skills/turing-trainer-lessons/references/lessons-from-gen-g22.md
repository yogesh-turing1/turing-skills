# Lessons from gen-g22-localisation-qa

## What went wrong and what fixed it

| Mistake or risk | Learning and prevention |
|---|---|
| Sampled regex grading gave full reward to missing or corrupted work. | Recompute every expected row and summary from source inputs. Reject missing, duplicate, extra, or corrupted keys while accepting harmless row reordering. |
| Difficulty was considered before grading integrity was proven. | Repair and mutation-test grading first. Harden only after the corrected task is measured. |
| Notes checks became brittle around synonyms and Markdown structure. | Check objective concepts near each required key. Forward-test equivalent phrasing observed in real trajectories. |
| Generic notes could pass while required accepted controls were omitted. | Enumerate every computed failing key and explicit accepted controls such as DNT, reordered named placeholders, exact-budget passes, and active exceptions. |
| Correct CSV/JSON output hid a missing `save.notice` explanation. | Inspect each failing trajectory and individual verifier result; do not infer the failure from headline reward. |
| A local integration run failed because submission files were intentionally absent. | Run mutation tests independently, then generate Oracle deliverables in an isolated workspace before integration assertions. |
| A Windows-to-WSL path assumption prevented the Oracle script from running. | Confirm mounts before replaying shell scripts, or run the embedded deterministic logic with explicit Windows paths. Never count the resulting missing files as task failures. |
| Modification times alone could not prove which ZIP was original or latest. | Record sizes and SHA-256 hashes. Compare extracted relative paths and content hashes. |
| Numerous edits and reversions made the change story unclear. | Maintain both a chronological change log and a final baseline-to-submission net diff. Label them explicitly. |
| QC and golden evidence initially existed only inside a combined final archive. | Create separate upload artifacts when the tracker has separate QC and golden-trajectory fields. |
| A date serial displayed as a number in the tracker. | Inspect live cell formatting, write the serial value, apply the expected date number format, and read back the displayed value. |
| Pass rate looked like text but was stored as a validated date-formatted serial. | Preserve a correct validated value when already present; verify the displayed dropdown label rather than normalizing storage casually. |
| Temporary caches and comparison extracts entered packaging. | Build from an explicit inclusion list or exclude `.pytest_cache`, `__pycache__`, and scratch directories before hashing the final archive. |
| Cleanup commands can be blocked even for safe temporary directories. | Use a predeclared scratch root and perform narrow, verified cleanup operations. If cleanup is blocked, categorize the directory as scratch rather than hiding it. |

## Successful approach

1. Replaced sampled grading with deterministic full-artifact reconciliation.
2. Added mutation coverage for row/key/schema/type/summary/notes failures.
3. Normalized unintended French encoding before measuring character budgets.
4. Added paired waiver and non-waiver controls only after the repaired task measured 5/5.
5. Added active, expired, future, renewed, and inclusive-date exception cases.
6. Repaired semantic note equivalence gaps seen in actual attempts.
7. Achieved Oracle 1.0, 25 mutation passes, five valid runs at 3/5, and unified QC `Keep`.

## Boundary on the 3/5 result

The 3/5 result was accepted by explicit user direction for this task. Do not
treat it as a universal threshold. Follow the current team/user acceptance rule
for the next task and record any explicit override.

---

## Lessons from code-c176-floorplan-dimension-audit and the FQC round

These lessons come from getting five tasks through the hosted Shannon QC
Control / Final QC (FQC 1.1.0) platform. Several "FAIL" reports traced to
package-format defects, not task difficulty.

### FQC evidence format (the platform is strict about machine-readable files)

| Mistake or risk | Learning and prevention |
|---|---|
| PowerShell 5.1 `Set-Content -Encoding utf8` writes a UTF-8 BOM into JSON files. | The FQC tool rejects BOM'd JSON as unparseable, so per-trial `result.json` and stability files counted as "0 binary GLM-5.2 rollouts" and "0 stability records" even though the data was present. Write all evidence JSON with Python (`json.dumps(...).write_text(..., encoding="utf-8")`) or `[IO.File]::WriteAllText(path, text, New-Object System.Text.UTF8Encoding($false))`. Verify by parsing every `.json` inside the final zip before submitting. |
| `evaluations/` must live INSIDE the task folder in the final-qc zip. | FQC extracts to `<root>/<task-folder>/` and looks for `evaluations/` under that task root. A sibling `evaluations/` at the zip top level is invisible to it. |
| FQC greps for canonical filenames, not Harbor layout. | `solution/golden_trajectory.json` (ATIF trajectory) and `solution/final_answer.md` are what FQC-EVD-001 looks for. A `solution/golden_trajectory/` folder alone is not enough. |
| FQC wants per-trial binary rewards it can parse. | Provide `evaluations/glm-5.2/<trial>/result.json` with a top-level integer `reward` (plus the nested `verifier_result.rewards.reward`), `evaluations/rollouts.json` (trial->0/1 + accuracy@4), and `evaluations/glm/result.json` batch summary. Report `passes/4`, not a README fraction. |
| The reward MUST be an integer `0`/`1`, not a float `1.0`. | The FQC classifier only counts a record as a "binary GLM-5.2 rollout" when it can read an integer reward AND attribute it to the target model (`agent_info.model_info.name` or `config.agent.model_name` containing `glm-5.2`). Harbor's real `result.json` files carry float `reward: 1.0`, which the tool silently skips -> persistent `FQC-EVD-002 "0 binary rollouts"` even after the BOM fix. Fix: rewrite `verifier_result.rewards.reward` to `1`/`0` (int) in every `glm/<trial>/result.json`, `oracle/.../result.json`, and `solution/golden_trajectory/result.json`. Avoid duplicate per-model dirs (`glm-5.2/` AND `glm/`) that double-count trials; keep ONE canonical set (use the full Harbor `glm/` tree). |
| Stability records must be full-schema, not minimal. | FQC-EVD-003 requires "five matching, readable evaluation records". Minimal `{reward, passed}` records are skipped. Ship each `evaluations/stability/repeat-<n>/result.json` with the full Harbor schema (id, task_name, trial_name, task_id, config, agent_info, verifier_result with int reward, started_at/finished_at, exception_info) PLUS `criterion_outcomes` (per-check passed/errors) and integer `passed`/`failed` that sum to the manifest count. |
| FQC wants five-repeat stability records. | Score the same frozen gold answer five times in fresh verifier workspaces and archive `evaluations/stability/repeat-<n>/result.json` + `verifier-stdout.txt` + a `provenance.json` stating "judge: none; deterministic recomputation". |
| `[verifier] collect` in task.toml is NOT a list of verifier names. | Harbor's `VerifierConfig.collect` is a list of compose-service snapshot command objects (`[[verifier.collect]]`). Populating it with verifier-name strings breaks task loading (`ValueError: Either datasets or tasks must be provided`). Leave `collect = []`; runtime verifier selection is `tests/manifest.json` + `test.sh`/`test_outputs.py`. FQC-DOC-006 ("effective verifier_configs=0") is a false positive for pytest-delegated tasks; document it in the README. |
| README provenance must match task.toml exactly. | FQC-DOC-003 compares the README heading / `source_task_id` against `task.toml` `source_task_id`, normalizing category prefixes (`code-`, `gen-`, `obi-`). Set both to the same bare id (e.g. `c176-floorplan-dimension-audit`) and keep the README verifier-count and category breakdown in exact agreement with `tests/manifest.json` (FQC-DOC-006 / FQC-SEM-GLM-02). |
| Keep `environment/_app/` a byte-identical mirror of root `tests/`. | FQC-PKG-002/007 check the Docker-effective tree. Mirror the whole `tests/` tree (including `test_mutations.py`) and `task.toml`/`instruction.md` into `environment/_app/`. |

### Platform workflow notes

- The QC platform URL is `<QC_PLATFORM_URL>` (was
  `<OLD_QC_HOST>`). Sign in with `@<ORG_DOMAIN>`, paste the GLM-5.2
  key, run Unified QC or Final QC one task per ZIP.
- One task at a time per trainer; only status `5.Completed` tasks with a 1/5 or
  2/5 pass rate that have NOT been human-reviewed go to the QC tool; mark them
  `2.In Progress` in the tracker first.
- The QC tool is advisory; the human reviewer makes the final Accept/Fix/Reject
  call and records the verdict + QC output (report.html etc.) back in the sheet.
- Difficulty target: 1/5, 2/5, or 3/5 full passes is the acceptable band; a task
  that measures 5/5 (e.g. obi-gen-g101) is Reject for difficulty, not an FQC failure.

### What went right

1. Curated a small graded surface (25-40 named checks) so the per-verifier
   report stays readable while the full check map remains for local mutation QC.
2. Reused valid AWS evidence when the graded surface and model-facing inputs were
   byte-identical (c51/g101/g22), avoiding needless re-measurement.
3. Ran parallel FQC-prep subagents (one per task) for the mechanical structural
   fixes (manifest, `_app` mirror, README, oracle asset, evaluations), and a
   shared Python fixer for the evidence layout.
4. Isolated the BOM root cause by replaying the report's exact finding
   (FQC-RUN-001 "Unexpected UTF-8 BOM") against the actual JSON files.


