---
name: turing-false-positive-audit
description: Reconcile disputed Company Bench/Turing QC flags across task packages, runtime evidence and review spreadsheets; identify false alarms with explicit evidence-based confidence. Use for requested false-positive audits, not ordinary sheet editing or automatic task acceptance.
---

# Turing false-positive audit

Use the existing `turing-workflow-orchestrator` and its QC authority for Turing work; delegate primary workflow to `turing_workflow_operator` when available. This skill adds claim-level reconciliation and a plain-language outcome, not a replacement acceptance policy.

## Scope and safety

- Record the supplied sources, requested tasks, retrieval times in IST, and approved output destination. Reuse existing acquisition and snapshot helpers when their input contracts fit.
- Read source sheets and buckets without changing them. Keep original packages immutable. No inferred permission for uploads, sheet repairs, final verdict changes, new credentials or paid model runs.
- Preserve named persistent VM/tmux sessions and other workloads. Start with four static readers; increase only after resource inspection. Serialize writes. Do not launch one container per task.
- Do not execute downloaded task code on a shared host. Replays require an authorized isolated environment; official Oracle/model evidence follows the runner skill.
- Use real supplied inputs and recorded outputs. Missing evidence stays missing; do not invent dummy data or synthetic probes without explicit approval.

## Establish identity before judging a claim

1. Snapshot raw values plus formulas/hyperlinks for relevant cells. Match by exact task identity, not row number, display title similarity or numeric family alone.
2. Bind a claim to its source cell, task/check identifier, package URI/generation/SHA256, and trial/model/harness/configuration when available. An instruction match is weaker than a whole-package match. Keep authoring trials separate from client runtime trials.
3. Detect formulas that reference a different task and reviews containing another task's subject matter. Do not reuse their verdicts. Preserve both the original claim and corrected provenance.
4. Record the dated acceptance and eligibility rules. Disputed pass-rate thresholds, runtime token budgets and continuation policies are dependencies, not facts settled by reviewer votes.

## Decide one concrete claim at a time

Treat pod, client and historical reviews as evidence leads, not ground truth. Read the exact instruction and legitimate inputs before verifier/gold when making a fresh semantic judgment; use an isolated cold reviewer where required by the orchestrator.

Separate these outcomes:

- `reporting_false_alarm`: the exact report flag or displayed attribution is demonstrably inconsistent with its own correctly identified source. This says nothing about underlying task quality.
- `task_check_false_positive`: an identified task-quality allegation is refuted on the applicable package/trial, with valid controls.
- `real_issue`: the alleged defect has supporting primary evidence; distinguish task, grader, runtime, evidence and ownership issues.
- `possible_false_alarm`: some primary evidence supports a rebuttal, but reproduction or version binding is incomplete.
- `already_fixed`: a later version repairs the issue; do not rewrite the original finding as false.
- `unresolved`: missing evidence, policy ambiguity, competing valid interpretations or unmatched versions prevent a decision.

For task checks, reproduce the disputed observation using existing real records. Where authorized and available, require a valid positive control, a materially wrong negative control, and a valid-equivalent output. Document exactly what was run, the hash and outputs. A source-code reading is not a replay. Independent review should receive the skill, claim and raw artifacts without the proposed conclusion; agreement without evidence is not validation.

Specific cautions:

- Missing output is not automatically an export bug or automatically model-owned. Inspect stop reason, configured budget, action trace and capture path.
- `artifacts=[]` describes configuration, not whether an agent wrote files.
- A client trial absent from an authoring ZIP is unavailable evidence, not a disproved event.
- A known-good Oracle can miss a broken alternative-valid implementation.
- A historical false-positive label may reverse only one supporting fact. Other blockers remain.
- Mixed-model screening counts are not a same-model battery. An ownership dispute does not erase a real defect.

## Confidence

Confidence is an evidence tier, not a calibrated probability; do not invent percentages.

- **High:** exact claim identity and applicable version are established, direct reproducible evidence refutes/supports it, required controls behave correctly, no material policy/runtime gap remains, and independent review confirms the bounded conclusion. For spreadsheet-only claims, direct cell/formula readback and a task-keyed independent check are sufficient controls.
- **Medium:** primary evidence supports the conclusion, but raw trial/version binding, full reproduction or independent validation is incomplete. Say which.
- **Unresolved:** evidence is report-only, mismatched, missing or policy-dependent. A reviewer label alone never earns High confidence.

If a requirement for a tier fails, lower the tier. Keep classification and confidence separate; a high-confidence wrong spreadsheet link is not high-confidence task acceptance.

## Run and report

`scripts/audit_snapshot.py` checks the existing Harbor audit snapshot contract: `feedback.json`, `new-sheet-index-snapshot.json`, optional raw `new-sheet-header-cell-evidence.json` (required to check header formulas), optional `header-reference-audit.json` (a cross-check, not the raw authority), and optional `pod-reconciliation/` snapshots. It mechanically detects Index AI-failure flags whose same-task detailed AI results contain positive PASS evidence and no FAIL/ERROR, and preserves other flags. It does not execute verifiers or adjudicate task quality. Read its validation errors rather than adapting unknown columns by position.

Run it with `--input-dir <snapshot-directory> --output-dir <new-run-directory>`. Output generation is local only. Feed the mechanical candidates and exact raw artifacts to an independent reviewer before publishing High confidence; save their review separately. Source-level findings require the primary workflow above and are kept in a separate evidence record.

Lead with a short explanation a nontechnical user can understand:

1. What was checked and what was not.
2. Confirmed false alarms, possible false alarms, and real/unresolved issues, with confidence and a one-sentence reason.
3. What the user should do next.

Keep detailed evidence in a separate table: task, trainer where verified, claim/check, source/version, verdict, confidence, plain explanation, proof, remaining blockers and next check. Include coverage and unknowns. Never imply all tasks were rerun when only reports or sources were inspected. Do not change human verdicts automatically.
