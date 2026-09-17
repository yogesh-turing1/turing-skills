# Trainer Runbook

## One-time setup

Prerequisites:

- Docker Desktop on Windows/macOS, or Docker Engine plus Compose on Linux.
- About 64 GB free disk for the shared base image.
- Google account with delivery-g-obi access.
- gcloud CLI.
- Python 3.12+.
- Harbor CLI.
- Personal GLM key and approved LiteLLM proxy endpoint.

Typical setup sequence:

    gcloud auth login
    gcloud auth configure-docker us-central1-docker.pkg.dev
    gcloud config set project delivery-g-obi
    docker pull us-central1-docker.pkg.dev/delivery-g-obi/data-obi-rl-gym/benchmark-base:latest
    uv tool install harbor
    harbor --version

Never commit keys or place them inside task packages. Keep secrets in the approved external environment/config file. Do not run destructive Docker cleanup that removes benchmark-base.

## Per-task workflow

1. Claim the task in the tracker.
2. Download and extract the task package.
3. Set TASK to its absolute path.
4. Inspect instruction.md, tests/manifest.json, and solution/.
5. Check core/secondary verifier policy according to current team instructions.
6. Run Oracle and inspect reward.txt plus test-stdout.txt.
7. Repair the correct layer and repeat until Oracle is 1.00.
8. Run five GLM-5.2 attempts.
9. Inspect reward.txt, verifier_summary.json, trajectory.json, and exception.txt.
10. Count full passes and inspect failure causes.
11. Run the unified QC tool.
12. Re-run evidence after changes and submit only when definition of done is satisfied.
13. For a `5.Completed` task with a 1/5 or 2/5 pass rate not yet human-reviewed:
    mark it `2.In Progress` in the tracker, then run it through the hosted
    Shannon QC Control / Final QC platform (`<QC_PLATFORM_URL>`,
    one task per ZIP, sign in with `@<ORG_DOMAIN>`, paste the GLM-5.2 key).
14. Package the FQC evidence correctly before upload (see FQC package rules below);
    record the advisory report card, your Accept/Fix/Reject verdict, and the
    report link back into the tracker.

## FQC package rules (hosted Shannon QC Control / Final QC)

- Build the final-qc ZIP with the task folder as the top level containing
  `task.toml`, `instruction.md`, `tests/`, `solution/`, `environment/`, and
  `evaluations/` INSIDE that task folder (not as a sibling).
- Write every JSON artifact BOM-free (PowerShell 5.1 `Set-Content -Encoding utf8`
  adds a BOM that the tool cannot parse; use Python `json.dumps` or
  `UTF8Encoding($false)`). A BOM'd `result.json` shows as
  "0 binary GLM-5.2 rollouts" / "0 stability records" (FQC-RUN-001, EVD-002, EVD-003).
- Provide canonical files: `solution/golden_trajectory.json` (ATIF trajectory),
  `solution/final_answer.md`, and in `evaluations/`:
  `glm-5.2/<trial>/result.json` (with a top-level integer `reward`),
  `rollouts.json` (trial -> 0/1 plus `accuracy_at_4` = passes/4),
  `glm/result.json` (batch summary), `oracle/`, and
  `stability/repeat-1..5/` each with `result.json` + `verifier-stdout.txt`
  plus a `stability/provenance.json` stating judge = none (deterministic).
- Rewards MUST be integers (`1`/`0`), not floats (`1.0`). The FQC classifier
  only counts a record as a binary target-model rollout when it can read an
  integer reward AND attribute it to the model (`agent_info.model_info.name` or
  `config.agent.model_name`). Harbor's native `result.json` uses floats, so
  rewrite `verifier_result.rewards.reward` to int in every `glm/<trial>/result.json`,
  `oracle/.../result.json`, and `solution/golden_trajectory/result.json`; keep ONE
  canonical trial set per model (avoid duplicate `glm-5.2/` AND `glm/` dirs).
- Stability repeat records need the FULL Harbor schema (id, task_name, trial_name,
  task_id, config, agent_info, verifier_result int reward, started_at/finished_at,
  exception_info) plus `criterion_outcomes` per check and integer `passed`/`failed`
  that sum to the manifest count; minimal `{reward, passed}` records are skipped
  by FQC-EVD-003.
- Keep `[verifier] collect = []` in task.toml: it is a compose-service snapshot
  list, NOT verifier names. Populating it breaks Harbor task loading. Runtime
  verifier selection is `tests/manifest.json` + `test.sh`/`test_outputs.py`.
- README must match task.toml exactly: `source_task_id` (normalize `code-`/`gen-`/`obi-`
  prefixes to the bare id), verifier count, and category breakdown must agree
  with `tests/manifest.json`.
- `environment/_app/` must mirror root `tests/` (full tree), `task.toml`, and
  `instruction.md` byte-for-byte.

## Config guardrails

- Use the approved custom GLM provider configuration for glm/glm-5.2 when the proxy requires it.
- Set the judge model to openai/glm-5.2 when judged verifiers are used, and pass the key plus proxy URL to the agent and verifier environments.
- On Windows set PYTHONUTF8=1 when non-ASCII task files may be processed.
- Match concurrency to available RAM; containers need roughly 4 GB each. Lower concurrency when runs starve or crash.
- Use placeholders such as TASK_PATH, GLM_API_KEY, and OPENAI_BASE_URL in notes and examples. Never invent or reveal secrets.

## Evidence files

- reward.txt — overall reward.
- test-stdout.txt — per-assertion detail.
- verifier_summary.json — verifier outcomes and motivations.
- trajectory.json — tool-call path.
- exception.txt — crash evidence.

## Debug order

1. exception.txt?
2. Did a trajectory or oracle record exist?
3. Read test-stdout.txt.
4. Identify the failing verifier.
5. Classify the fault.
6. Repair and re-run.

