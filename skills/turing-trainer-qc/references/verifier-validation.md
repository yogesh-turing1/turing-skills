# Verifier validation

Use this reference when a task uses model judgment, when correctness depends on
answer/state/trace semantics, or when the user asks whether a verifier itself is
trustworthy. This layer complements A/G/M/H task QC; it does not replace
deterministic checks, Oracle validation, or human final judgment.

## Decompose the verdict

Do not ask one model only “was this correct?” Evaluate each applicable surface
separately:

1. **Answer:** Does the final response contain the required substantive result?
2. **State:** Are mandatory final-state changes present and forbidden changes
   absent?
3. **Trace:** Were required systems, tools and steps genuinely used correctly?
4. **Instruction:** Were task-specific requirements followed?

Switch off inapplicable verifiers instead of running them vacuously. Instruction
verification is criteria-based. Answer, state and trace may use the task,
minimum-requirement criteria and a reference execution as evidence.

Each applicable verdict must be machine-consumable: bounded category, score per
criterion, written justification per criterion, cited evidence, and the earliest
step that broke the criterion when trace evidence exists.

## Reference evidence is not the specification

A golden answer, state or trajectory demonstrates one correct route. It does not
define the complete set of correct routes.

- State the mandatory minimum that must be true.
- Accept valid alternative routes, equivalent phrasing and benign extra work.
- Reject superficial reference matches that hide an actual error.
- Prevent the minimum set from gradually becoming another loose golden state;
  review it against new labeled edge cases.

Use deterministic checks first for exact identifiers, counts, required fields,
types, ranges and recomputable values. Reserve model judgment for contextual
questions that cannot be expressed fairly as exact assertions.

## State and process semantics

- Capture stable before/after state snapshots and normalize irrelevant churn.
- Judge the meaningful final state, not every transient event. Deleted mistakes
  or harmless residue are not automatically failures.
- Ignore ordering, read-status or incidental fields unless the task makes them
  material.
- For read-only/retrieval tasks, disable state-diff comparison rather than
  treating an empty diff as failure.
- If a tool or system is mandatory, encode that requirement in task metadata and
  verify correct use, not mere invocation. Outcome-only grading must not accept a
  plausible answer that skipped required work.
- Use per-task criteria for hard cases; one global prompt is only a baseline.

## Build labeled evaluation sets

Separate refinement from final validation:

- **Working set:** used for prompt refinement and error analysis.
- **Blind holdout:** untouched until final measurement; never tune against it.

Weight both toward the verification boundary. A useful starting balance is
roughly equal thirds:

- valid alternative paths;
- reference-like valid paths;
- genuinely wrong paths.

Include harmless residue, irrelevant diffs, benign versus failure-confessing
extra output, required-tool violations, paraphrases, and near-miss errors. Keep
human ground-truth labels and criterion-level/step-level labels where possible.

## Measure the verifier

Report a confusion matrix and, separately:

- accuracy;
- precision: how often a predicted pass is truly valid;
- recall: how many truly valid runs are accepted;
- false-pass and false-fail counts/rates;
- repeatability across repeated judgments of the same sample;
- results by answer/state/trace/instruction surface and hard-case class.

Set targets before reading holdout results. The referenced verification programme
uses >80% accuracy, precision and recall as a baseline and 90% as a stretch goal;
confirm the current authority before treating those values as release gates.

## Composition and cost

An all-applicable-verifiers-must-pass rule is conservative but compounds false
negatives. Inspect both per-verifier and composed confusion matrices. Under an
independence approximation, combined valid-run recall across `k` all-pass
verifiers is the product of their recalls; real correlations must be measured,
not assumed.

Model judgments are non-deterministic and cost one or more calls per surface.
Start with exact deterministic checks, then cascade only unresolved cases to
model judgment. Test repeated independent predictions or majority vote only when
the measured reliability gain justifies the added cost and latency.

## Step-level critique

Outcome verification says whether a run failed. Training feedback should also
identify where and why:

- wrong output at a step;
- divergence from required plan;
- missing required action;
- guideline violation;
- unreasonable repetition or continuation after a known failure.

Benchmark critique models against human step labels before using their output as
automatic training signal. Until then, treat step critique as advisory evidence.

## Release evidence

A model-based verifier is not release-ready without:

- named answer/state/trace/instruction applicability;
- versioned prompts, criteria, references and model configuration;
- working-set and blind-holdout provenance;
- confusion matrices plus precision/recall/accuracy;
- hard-case slice results and repeated-judgment stability;
- composed-verdict analysis;
- documented cost and fallback path;
- human approval of the verifier and its unresolved limitations.
