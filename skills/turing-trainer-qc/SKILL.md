---
name: turing-trainer-qc
description: "Use for Company Bench / Harbor trainer work and internal QC: task-package inspection, portfolio failure triage, prompt/verifier repair, deterministic and mutation grading checks, Oracle and five-run evaluation, semantic hardening, unified QC, version/evidence reconciliation, and submission readiness. Treat the Trainer/QC Bible as the quality authority whenever a task needs configuration, iteration, measurement, packaging, or trainer/QC judgment."
---

# Turing Trainer QC

Use this skill as the operational front door for Company Bench / Harbor trainer
work. It distills the knowledge base at
`C:\cpio\_db\Turing\Turing-Obsidian-Knowledge-Base`.

## Non-negotiable rules

- Keep the human reviewer as the final quality judge.
- Read the prompt cold before the design doc, gold answer, or trajectory.
- Require a realistic, fair, runnable task whose failures are model-owned.
- Do not count crashes, missing files, ambiguity, broken grading, or infrastructure faults as difficulty.
- Never expose or package API keys.
- Fix the wrong layer directly: prompt, environment, verifier, gold, trajectory, or infrastructure.
- Preserve the downloaded archive as an immutable baseline and record its hash.
- Repair grading before adding difficulty. A verifier that accepts a known-bad mutation is not valid measurement.
- Treat any model-based verifier as a model under evaluation: calibrate it on a blind labeled set and report precision and recall, not only agreement or accuracy.
- Tie every reported score to the exact frozen package that produced it.

## Route the work

1. Setup/configuration: read [trainer-runbook.md](references/trainer-runbook.md).
2. Task review/QC: read [authority-and-qc.md](references/authority-and-qc.md), then [defects-and-diagnostics.md](references/defects-and-diagnostics.md).
3. Iteration/evidence: read [trainer-runbook.md](references/trainer-runbook.md) and follow the evidence sequence below.
4. Checklist/record: read [templates.md](references/templates.md).
5. Internal portfolio audit, failure distribution, prioritization, or acceptance-readiness analysis: read [internal-qc-operations.md](references/internal-qc-operations.md).
6. Model-judged answer/state/trace/instruction verification, verifier benchmarking, or blind-set calibration: read [verifier-validation.md](references/verifier-validation.md).
7. Prior mistakes, packaging, uploads, or tracker handoff: use `$turing-trainer-lessons`; read [latest-lessons.md](references/latest-lessons.md) for the concise bridge.
8. Detailed source context: consult the Obsidian vault, then its `Sources` folder.

## Core sequence

### 1. Inspect and baseline

- Keep the original ZIP untouched and hash it.
- Extract into a separate working directory.
- Inspect `instruction.md`, `tests/manifest.json` or `tests/verifier.json`, `solution/`, inputs, and `task.toml`.
- Check package completeness, answer leakage, and configuration before editing.

### 2. Audit the ask

Check A1-A6: realistic ask, one defensible answer, no leakage, all decisions
specified, useful client outcome, and every dependency present.

### 3. Audit and repair grading

Check G1-G7: primary goal covered, every ask checked, nothing unasked graded,
artifact/state graded, equivalent routes accepted, every verifier discriminates,
and judgment used only when deterministic checks cannot work.

For structured outputs, mutation-test:

- missing, duplicate, extra, reordered, and corrupted rows;
- every required column/key and wrong native types;
- inconsistent summaries and cross-artifact disagreement;
- generic or incomplete notes;
- equivalent wording and ordering that should pass.

Prefer deterministic recomputation from supplied inputs over sampled regexes or
golden-prose matching.

When correctness also depends on open-ended answer quality, state changes,
required tool use, or execution trace, decompose the verdict and validate the
model-based verifier using [verifier-validation.md](references/verifier-validation.md).

### 4. Run evidence

1. Run Oracle; require exactly 1.0 with no exception.
2. After any consequential prompt/input/policy/verifier/gold change, rerun Oracle.
3. Run five valid model attempts only after Oracle passes.
4. Count a full pass only at reward 1.0.
5. Inspect every failure's assertions, trajectory, verifier profile, and exception evidence.
6. Apply the current team/user pass-rate rule. Record explicit overrides; do not generalize them.
7. If too easy, add fair paired controls and rule interactions, not ambiguity or arbitrary traps.
8. If 0/5, prove at least one solvable trajectory and diagnose ambiguity, grading, and infrastructure.

### 5. QC, package, and hand off

- Run official unified QC and review every finding manually.
- Preserve a reward-1 final-version golden trajectory.
- Compare original baseline with frozen submission by relative path and hash.
- Distinguish the final net diff from reverted iteration history.
- Exclude `.pytest_cache`, `__pycache__`, scratch extracts, credentials, and loose generated outputs.
- Package task, QC, and golden evidence separately when the tracker has separate fields.
- Upload to requested Drive folders, use returned URLs, and verify folder readback.
- Read tracker validation and formatting before writing; verify links, dropdowns, dates, notes, and pass rate afterward.
- Write a session handoff and organize artifacts before starting the next task.

## Diagnostic shortcuts

- Oracle below 1.0: identify whether gold, trajectory, verifier, package, or replay environment is wrong.
- Missing deliverables locally: generate Oracle outputs in an isolated workspace before judging integration tests.
- Exception or empty results: treat as infrastructure until disproven.
- High pass rate: inspect loose checks, free points, prompt leakage, and genuine difficulty.
- Bimodal rewards: inspect ambiguity forks and unstable judging.
- Stable mean with changing verifier profile: inspect profile drift.
- Suspiciously high score: calculate the effective floor.
- Notes-only failures: check requirement completeness and synonym/Markdown tolerance separately.
- Windows/WSL replay failure: validate mount paths before interpreting missing-file assertions.
- FQC "0 binary rollouts" / "0 stability records" (FQC-RUN-001, EVD-002, EVD-003):
  check for a UTF-8 BOM, verify `evaluations/` sits INSIDE the task folder in the
  final-qc ZIP, AND check rewards are integers (`0`/`1`) not floats (`1.0`) with
  model attribution (`agent_info.model_info.name` / `config.agent.model_name`
  containing `glm-5.2`). All three are packaging defects, not model difficulty;
  Harbor's native `result.json` uses float rewards, so rewrite them to int before
  packaging. Stability repeats also need the full Harbor schema + per-check
  `criterion_outcomes`, else the tool skips them.
- FQC-DOC-006 "effective verifier_configs=0": expected when grading is delegated to
  pytest (`[verifier] collect = []`); document it in the README rather than wiring
  verifier names into `collect` (which breaks Harbor task loading).

## Internal-QC decision rule

For a portfolio or audit workbook, never rank tasks from a single pass marker.
First establish outcome provenance, then classify A/G/M/H and runtime defects,
preserve clean sub-gates, and order repairs by causal dependency. A lead-QC,
trainer-QC, completion, upload, or mixed-model result is not client acceptance.
Do not estimate client-acceptance probability without explicit historical client
verdicts tied to the submitted package version. Use
[internal-qc-operations.md](references/internal-qc-operations.md) for the complete
procedure and output contract.

## Source authority

1. Trainer/QC Bible — quality and human-review authority.
2. OBI Task Quality Standard — A/G/M/H definitions.
3. Trainer Guidelines — workflow and definition of done.
4. Company/Computer Bench onboarding — environment context.

Surface conflicts instead of silently choosing stale guidance.

## References

- [authority-and-qc.md](references/authority-and-qc.md)
- [trainer-runbook.md](references/trainer-runbook.md)
- [defects-and-diagnostics.md](references/defects-and-diagnostics.md)
- [templates.md](references/templates.md)
- [latest-lessons.md](references/latest-lessons.md)
- [internal-qc-operations.md](references/internal-qc-operations.md)
- [verifier-validation.md](references/verifier-validation.md)
