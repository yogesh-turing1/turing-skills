---
name: turing-trainer-lessons
description: Use for Company Bench/Harbor trainer retrospectives, repeated-failure diagnosis, verifier repair, evidence/version reconciliation, package cleanup, Drive upload and tracker handoff, or when starting a new Turing task and needing lessons from prior iterations. Applies concrete mistakes and prevention checks from completed trainer sessions without replacing the authoritative turing-trainer-qc workflow.
---

# Turing Trainer Lessons

Use this skill as the operational memory layer for trainer work. Use
`$turing-trainer-qc` for the authoritative review and evidence workflow, then
use this skill to avoid repeating observed process mistakes.

## Start-of-task check

1. Preserve the downloaded archive as an immutable baseline and record its hash.
2. Work in a separate extracted directory.
3. Read the prompt cold, then inspect the verifier and gold.
4. Repair grading before adding difficulty.
5. Create a version/evidence ledger before the first Oracle or model batch.

## Iteration discipline

- Treat a mutation that earns full reward as proof of verifier weakness.
- Validate complete artifacts, exact key sets, native types, and cross-artifact consistency.
- Prefer semantic concepts near a key over exact prose or narrow synonyms.
- Treat a reference run as one valid example, not the full correctness set; define mandatory minimums and test alternative-valid paths.
- When model judgment is used, keep refinement and blind validation sets separate, report precision and recall, and inspect answer/state/trace/instruction errors independently.
- Verify required tool use from the trace, normalize irrelevant final-state churn, and identify the exact failing step rather than returning only an opaque verdict.
- Run Oracle after every consequential package change.
- Run a fresh five-attempt batch only after Oracle returns exactly 1.0.
- Count only reward 1.0 as a full pass and inspect every failure trajectory.
- Do not count missing deliverables, crashes, bad mounts, or grading faults as difficulty.
- Tie every reported score to the exact measured package version.

## Closeout discipline

1. Compare the immutable baseline with the frozen submission by content hash.
2. Report the net diff separately from the chronological worklog; reverted edits are not net changes.
3. Exclude caches and temporary files from submission archives.
4. Package the task, QC report, and golden trajectory separately when the tracker has separate columns.
5. Upload to the requested Drive folders and use only returned, verified URLs.
6. Read tracker validation and formatting before writing; verify dates, dropdowns, notes, and links after writing.
7. Create a session handoff note and organize evidence before starting the next task.

## Detailed lessons

Read [lessons-from-gen-g22.md](references/lessons-from-gen-g22.md) when a task
involves deterministic CSV/JSON reconciliation, semantic notes checks, waiver
interactions, Windows/WSL replay, packaging, Drive upload, or tracker updates.
