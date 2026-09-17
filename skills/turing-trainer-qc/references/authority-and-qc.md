# Authority and QC

## North star

A high-quality task is realistic, non-trivial, accurate, relevant, runnable, and fair. The model must have the information and tools it needs; failures should come from model reasoning or process limitations.

Human reviewers are the final judges. LLMs may help parse prompts, enumerate requirements, summarize trajectories, or suggest checks, but their verdict is advisory.

## Three gates

### A — The Ask

A1 realistic ask. A2 one defensible answer. A3 no answer leakage. A4 all decisions specified and no ambiguity fork. A5 useful client value. A6 every named dependency exists and contains the promised information.

### G — The Grading

G1 primary goal verified. G2 every stated requirement checked. G3 nothing unstated graded. G4 artifact or resulting state graded, not the model's account. G5 equivalent correct routes accepted. G6 each verifier discriminates and free points are understood. G7 model judgment used only where deterministic checks are not possible.

### M — The Measurement

M1 Oracle exactly 1.00 and reproducible. M2 full-pass rate in [0.0, 0.5). M3 five-run spread is not a bimodal coin flip. M4 failures are attributable to the model. M5 verifier profile is stable across independent batches. M6 score is not inflated by free points.

### H — Hygiene

H1 root prompt/verifier mirrors match environment/_app. H2 solution content is not reachable by the model. H3 the package can grade itself. H4 the reported number belongs to the submitted package version.

## Review posture

Read instruction.md cold before the design doc, gold, or trajectory. If the run crashed, the verifier could not evaluate, or the task was ambiguous, do not call that a model failure.

A run is a full pass only at reward 1.0. The trainer acceptance bar is full-pass rate at or below 50% across five model runs; do not substitute the mean verifier reward for this count.

## Repair principle

Ask which layer is wrong: prompt, environment, verifier, gold, trajectory, or infrastructure. If a fix could change the reported number, re-run the affected evidence. If it cannot, fix the defect and keep the score only when the task remains valid.

