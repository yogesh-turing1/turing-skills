# Internal QC operations

Use this reference for cross-task audits, trainer/EM portfolios, shortlist
selection, failure distributions, and acceptance-readiness reporting. It extends
the single-task A/G/M/H review without replacing human judgment.

## Evidence boundary

- Preserve raw packages, workbooks, exports, and downloaded artifacts unchanged;
  hash them before analysis.
- Keep original and trainer-modified task versions separate by stable task ID.
- Record source workbook/tab/row, retrieval time in IST, and package hash.
- Treat missing client runner outputs, trajectories, verifier profiles, or verdicts
  as unavailable. Never infer them from internal status fields.
- For Google Sheets task links, read `CellData` fields `formattedValue`,
  `effectiveValue`, `userEnteredValue`, `hyperlink`, and `chipRuns`. Extract URLs
  in this order: `hyperlink`; `chipRuns[].chip.richLinkProperties.uri`;
  `HYPERLINK()` formula; otherwise `NOT AVAILABLE`.
- External Drive/tracker writes and final Keep/Fixable/Reject verdicts require
  explicit human approval.

## Outcome-field test

Before calculating rates, name the endpoint and prove what it means. Internal
trainer QC, lead QC, completion, CSV upload, automatic flags, or model pass rate
are not client acceptance. If no explicit client verdict exists:

1. label the substitute `internal proxy` everywhere;
2. report coverage and unknown labels;
3. do not call proxy rates acceptance probabilities;
4. do not train or present a predictive acceptance model.

A real client-probability analysis requires stable task ID, Accepted/Rejected,
verdict timestamp, submitted package hash/version, and rejection reason.

## Gate-ordered audit

Audit in causal order. Stop interpreting difficulty when an upstream gate fails.

1. **H — provenance/package:** mirrors, answer isolation, grading engine,
   package/evidence hash binding.
2. **A — ask:** realism, single defensible answer, no leakage, no ambiguity,
   client value, dependencies present.
3. **G — grading:** every ask covered, nothing unasked graded, artifacts/state
   checked, equivalent routes accepted, no free points, judgment only when needed.
4. **M1 — Oracle:** exactly 1.0, reproducible, exception-free.
5. **Runtime/evidence validity:** exclude crashes, missing outputs, timeouts, judge
   errors, and malformed records; rerun them.
6. **M2-M6 — difficulty:** only now interpret five same-model full-pass attempts,
   spread, model attribution, profile stability, and effective score floor.

The dependency chain is:

`H/A/G valid → Oracle 1.0 → runtime valid → five comparable runs → difficulty judgment`

## Grading challenge set

Before measurement, demonstrate discrimination rather than merely reading tests.

- Known-good Oracle artifact passes at 1.0.
- Missing, duplicated, extra, corrupted, and wrong-type structured data fail the
  affected requirements.
- Wrong conclusions, wrong rationales, cross-artifact disagreement, and bare
  keyword/ID lists fail.
- Equivalent correct prose, ordering, and valid alternate routes pass.
- Remove all-or-nothing lexical gates, golden-prose matching, artifact-presence
  points, and sampled checks where complete deterministic recomputation is
  feasible.

If a known-bad mutation passes, G is failed and pass-rate evidence is invalid
until repaired and rerun.

## Portfolio distribution

Use the exact scoped task count as denominator. Report both:

- per-category count and percentage for A, G, M, H, runtime, and ownership;
- overlap distribution: number of tasks failing 0, 1, 2, 3, 4, or 5 core areas.

Categories are multi-label; percentages can exceed 100% in total. State this.
Also report unknown/N/A separately and never convert unknown to clean.

For each task, preserve the reverse view: list clean sub-gates and working
controls. These are strengths to retain during repair, not reasons to waive a
blocker. Do not multiply correlated marginal rates or interpret small cohorts as
causal effects.

## Repair and shortlist lanes

Assign a workflow recommendation, not a final verdict:

- **Rerun first:** upstream gates clean; only protocol/version evidence missing or
  conflicting.
- **Promote after repair:** one or two localized, demonstrably repairable blockers.
- **Reserve:** usable foundations but more work or excessive ease remains.
- **Hold:** upstream package/ask/grading/Oracle/runtime defects invalidate evidence.
- **Conditional discard:** combined defects, unproven solvability, or repair cost
  is disproportionate; human approval is required to discard.

Prioritize the smallest causal repair: ownership/provenance → H → A → G → Oracle
→ runtime → official five-run batch → fair hardening. Never harden an invalid
verifier or treat infrastructure failures as useful difficulty.

## Minimum output contract

For every audited task report:

- stable task ID; trainer and EM with source/conflict notes;
- original and modified artifact availability and hashes;
- A/G/M/H/runtime status: Failed, Not Failed, or Unknown;
- exact evidence for each blocker and each preserved strength;
- whether existing measurement is valid and why;
- minimum causal action and one runnable validation check;
- recommendation lane, effort band, and human-approval status.

Portfolio reports must include source lineage, denominator/coverage, integrity
failures, category and overlap distributions, proxy limitations, prioritized
action plan, and links/hashes for reproducibility.

## Evidence-backed lessons from the 2026-09-01 audits

- Later audit failures frequently coexisted with earlier lead-QC passes; therefore
  lead QC cannot be used as a client-acceptance label or a reliable gate.
- Clean deliverables, runtime, H, A, and valid difficulty were the strongest
  descriptive internal-proxy signals; preserve them during repair, but do not
  claim causality.
- Oracle and LLM-judge failures had paradoxically high proxy-pass rates, showing
  that historical proxy status predates or omits later audit findings.
- Verifier defects were dominated by lexical/golden-prose checks, bare-ID or
  keyword acceptance, hidden constraints, free points, and all-or-nothing grading.
- Yogesh’s audited portfolio showed highly overlapping defects: 18 of 23 tasks
  failed at least four of A/H/G/M/runtime. Treat this as a workflow-control issue,
  not 18 independent polishing tasks.
- Cross-sheet operations contained duplicate task IDs, ownership conflicts,
  missing links, workflow contradictions, and lead-QC-without-trainer-QC rows.
  Reconcile identity and ownership before attributing trainer performance.
