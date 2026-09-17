# Latest trainer lessons

Detailed operational memory:

- `gen-g22-localisation-qa`: `../../turing-trainer-lessons/references/lessons-from-gen-g22.md`
- `code-c176-floorplan-dimension-audit` + FQC round:
  same file, section "Lessons from code-c176-floorplan-dimension-audit and the FQC round".

## Apply these rules without loading the full case study unless needed

- preserve and hash an immutable baseline;
- mutation-test grading before hardening;
- recompute structured outputs deterministically and completely;
- make semantic notes checks tolerant of equivalent phrasing but complete over required keys and controls;
- run Oracle after every consequential change;
- separate model failures from missing outputs, mount errors, and grader faults;
- freeze the package before final five-run and QC evidence;
- report net diff separately from reverted iteration history;
- exclude caches and scratch files from submission;
- verify Drive destinations and tracker display values after writing.

## FQC / Shannon QC Control (new hosted platform)

- Platform: `<QC_PLATFORM_URL>`. One task per
  trainer at a time; only `5.Completed` tasks with 1/5 or 2/5 pass rate that are
  not yet human-reviewed go to QC; set them `2.In Progress` first.
- The tool is advisory; the human reviewer records the final
  Accept/Fix/Reject verdict and the QC output in the sheet.
- **Write all evidence JSON BOM-free** (Python `json.dumps` or
  `UTF8Encoding($false)`). A PowerShell UTF-8 BOM makes `result.json`
  unparseable, which the tool reports as "0 binary rollouts" / "0 stability
  records" (FQC-RUN-001 / EVD-002 / EVD-003).
- FQC requires canonical files: `solution/golden_trajectory.json`,
  `solution/final_answer.md`, and `evaluations/` INSIDE the task folder with
  `glm-5.2/<trial>/result.json` (top-level integer `reward`), `rollouts.json`,
  `evaluations/glm/result.json`, and `evaluations/stability/repeat-1..5/` +
  `provenance.json`.
- **Rewards must be INTEGER `0`/`1`, not float `1.0`.** The tool only classifies
  a record as a binary target-model rollout when it reads an integer reward AND
  model attribution (`agent_info.model_info.name` / `config.agent.model_name`
  containing `glm-5.2`). Harbor's native `result.json` uses floats, so rewrite
  `verifier_result.rewards.reward` to int in every `glm/<trial>/result.json`,
  `oracle/.../result.json`, and `solution/golden_trajectory/result.json`, and keep
  ONE canonical trial set per model (duplicate `glm-5.2/` + `glm/` dirs
  double-count). Stability repeat records need the full Harbor schema + per-check
  `criterion_outcomes` and integer `passed`/`failed` summing to the manifest count.
- `[verifier] collect` must stay `[]` (it is a compose-service snapshot list,
  not verifier names). README `source_task_id`, verifier count, and category
  breakdown must exactly match `task.toml` and `tests/manifest.json`.
- `environment/_app/` must mirror root `tests/` (full tree) + `task.toml` +
  `instruction.md` byte-for-byte.

The 3/5 result in the localisation case was accepted by explicit user direction
and is not a general replacement for the current team acceptance rule.
