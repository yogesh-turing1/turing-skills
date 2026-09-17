---
name: turing-workflow-orchestrator
description: Orchestrate Company Bench/Turing trainer tasks from isolated cold review through verifier repair and calibration, immutable packaging, AWS Harbor Oracle and five-run evidence, unified QC, and approved handoff. Use whenever a Turing task is created, hardened, measured, resumed, reconciled, or prepared for submission.
---

# Turing Workflow Orchestrator

Run one resumable, evidence-bound workflow. Compose these skills in this order and read each selected `SKILL.md` completely before acting:

1. `turing-trainer-qc` is the quality authority.
2. `turing-trainer-lessons` supplies failure-prevention memory.
3. `turing-aws-harbor-runner` owns Oracle and GLM execution on AWS.

Do not invoke unrelated installed skills. Use Drive skills only after the user explicitly requests a Drive or tracker handoff.

Read [workflow-ledger.md](references/workflow-ledger.md) before starting or resuming work.

## Operating rules

- Lead one task through the state machine below; do not skip gates.
- Keep the ledger outside the submitted task directory. Default to `<workspace>/.turing-workflow/<task-id>/ledger.json`.
- Preserve and hash the original baseline before edits. Every consequential change invalidates older evidence.
- Keep writes serialized. Use subagents only for bounded read-only audits or the required cold review.
- The human reviewer owns the final Keep/Fixable/Reject verdict and any external handoff approval.
- Treat infrastructure, packaging, or verifier failures as invalid evidence, never as model failures.
- When model judgment affects a verdict, require the answer/state/trace/instruction applicability and blind-set calibration defined by `turing-trainer-qc`; deterministic-only tasks do not invent model verifiers.
- Never expose credentials, add public ingress, place secrets in packages, or silently fall back to local Harbor.

## State machine

### 1. Intake and baseline

- Resolve exactly one task identity and one task root.
- Create or resume the ledger and record the task path, source archive, baseline SHA-256, request, and applicable decision rule.
- Refuse evidence work while identity, baseline, task root, or requested artifact paths are ambiguous.

### 2. Isolated cold review

- Spawn a fresh read-only subagent before exposing gold, verifier, solution, trajectories, or prior evidence.
- Provide only `instruction.md` and legitimate client-facing inputs.
- Record the A1-A6 ambiguity findings required by `turing-trainer-qc` in the ledger.
- Do not let the cold reviewer edit files.

### 3. Deep audit and repair

- Inspect the environment, verifier, gold/reference outputs, mirrors, package boundaries, and previous evidence.
- Run deterministic positive, negative, mutation, and equivalence tests.
- Repair grading defects before changing task difficulty.
- Decompose contextual verification into applicable answer, state, trace, and instruction surfaces. Disable inapplicable surfaces rather than running them vacuously.
- For every model-based verifier, record its versioned prompt/model/criteria and require labeled working-set plus untouched blind-holdout evidence with precision, recall, accuracy, repeatability, and composed-verdict risk. Stop if this evidence is unavailable; do not substitute anecdotal examples.
- Record each material change and why it was needed. Return to this stage when a later gate reveals a semantic defect.

### 4. Freeze gate

- Build an explicit inclusion list. Exclude caches, scratch files, `.git`, prior evidence, local ledgers, and credentials.
- Require exactly one task root and fail a secret scan closed.
- Derive artifact paths from the task contract; validate them as safe absolute `/app/...` paths.
- Compute the frozen package SHA-256 and immutable version identifier. Bind both to the ledger and job name.
- Do not run evidence until package, hashes, tests, and requested artifacts all agree.

### 5. AWS evidence

- Follow `turing-aws-harbor-runner`; submit through `submit-task.ps1`, never ad hoc local Docker.
- Use a unique shell-safe job name derived from task, version, and short package hash. Never reuse a prior evidence identity.
- Prevent overlapping submissions to the persistent runner. Do not resubmit merely because an asynchronous command is still active.
- Run Oracle first. Require exactly one trial, reward `1.0`, zero exceptions, and every expected artifact.
- Only after Oracle passes, run exactly five GLM attempts at the runner-safe concurrency.
- Preserve SSM command IDs, S3 locations, runner/script identity, logs, and all requested artifacts.

### 6. Forensic inspection

- Inspect all five rewards, exceptions, verifier results, trajectories, and captured artifacts.
- Compare outputs to gold at byte, parsed-structure, and semantic levels where applicable.
- Classify each failure as model-owned, grading, ambiguity, package, or infrastructure.
- Inspect answer/state/trace/instruction outcomes separately, including criterion justification and earliest failing step. Review benign residue, irrelevant state churn, required-tool use, and extra output contextually.
- Invalidate the batch if grading, packaging, or infrastructure affected the outcome.

### 7. Decision and repair loop

- Apply the task's recorded decision rule; do not inherit a stale target from another task.
- Produce an evidence-backed Keep, Fixable, or Reject recommendation using the QC authority's A/G/M/H framework.
- If a consequential repair is made, repeat freeze, Oracle, and five-run evidence on the new hash.
- Request an independent extra batch when verifier-profile stability remains uncertain.
- Stop before external submission so the human reviewer can make the final decision.

### 8. Unified QC and reconciliation

- Run official unified QC against the exact frozen package.
- Compare baseline and final relative-path hashes and explain every changed file.
- Prove that evidence package hash equals submission package hash.
- Preserve a reward-1 golden trajectory and keep task, QC, and golden artifacts separate.
- For a `5.Completed` task with a 1/5 or 2/5 pass rate not yet human-reviewed,
  run it through the hosted Shannon QC Control / Final QC platform
  (`<QC_PLATFORM_URL>`), one task per trainer.
  Build the final-qc ZIP per the FQC package rules (see below); the tool is
  advisory, and the human records the final Accept/Fix/Reject verdict in the
  tracker.

### 8b. FQC package rules (hosted Shannon QC Control / Final QC)

- Final-qc ZIP top level is the task folder, containing `task.toml`,
  `instruction.md`, `tests/`, `solution/`, `environment/`, and `evaluations/`
  INSIDE that task folder.
- Write all JSON BOM-free (PowerShell 5.1 `Set-Content -Encoding utf8` adds a
  BOM the tool cannot parse -> reports "0 binary rollouts" / "0 stability
  records" via FQC-RUN-001, EVD-002, EVD-003).
- Ship `solution/golden_trajectory.json` + `solution/final_answer.md`, and under
  `evaluations/`: `glm-5.2/<trial>/result.json` (top-level integer `reward`),
  `rollouts.json` (with `accuracy_at_4` = passes/4), `glm/result.json`,
  `oracle/`, and `stability/repeat-1..5/` + `provenance.json` (judge = none).
- Rewards MUST be integers (`1`/`0`), not floats (`1.0`). The tool only counts a
  record as a binary target-model rollout when the reward is an integer AND the
  record carries model attribution (`agent_info.model_info.name` /
  `config.agent.model_name` containing `glm-5.2`). Harbor's native `result.json`
  uses floats -> rewrite `verifier_result.rewards.reward` to int in every
  `glm/<trial>/result.json`, `oracle/.../result.json`, and
  `solution/golden_trajectory/result.json`; keep ONE canonical trial set per model.
  Stability repeat records need the full Harbor schema + per-check
  `criterion_outcomes` and integer `passed`/`failed` summing to the manifest
  count, else FQC-EVD-003 skips them.
- Keep `[verifier] collect = []` (compose-service snapshot list, not verifier
  names; populating it breaks Harbor). README `source_task_id` / verifier count /
  category breakdown must match task.toml and `tests/manifest.json`.
- `environment/_app/` mirrors root `tests/` (full tree) + `task.toml` +
  `instruction.md` byte-for-byte.

### 9. Approved handoff

- Ask for explicit approval before Drive uploads, tracker writes, or other external mutations.
- After approval, perform the handoff with the relevant Drive skills and read back URLs and tracker display values.
- Update the ledger with human verdict, handoff status, and a concise resumable session note.
- Stop the AWS runner when the workflow is idle unless another authorized run is imminent.

## Runner guardrails

Until the runner itself enforces them, independently validate job names and artifact paths, serialize submissions, hash the package and remote execution script, and retrieve SSM console logs when S3 evidence is incomplete. Reject unsafe identifiers, multiple task roots, missing artifacts, leaked secrets, and any Oracle result with an exception.
