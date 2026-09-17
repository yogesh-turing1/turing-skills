---
name: harbor-next-batch-selection
description: Select another Harbor finalisation batch while excluding a prior delivery by canonical identity and exact source versions, with explicit distribution and evidence limits.
---

# Select the next Harbor batch

Use for batch selection, not for running the full audit pipeline.

- Read the user's delivery manifest from the specified source. Preserve a snapshot and checksum. A folder named 60 is not proof of 60 distinct tasks.
- Refresh the accepted GCS prefix read-only. Count only immediate task-directory ZIPs, not nested archives. Preserve object generation as a string. The default source is gs://<TASK_BUCKET>/tasks/finalisation_client_qc_accepted_iteration_2/.
- Exclude prior canonical families, their recorded source-folder aliases and known equivalent variants across all versions. Resolve task.toml identities in candidate packages before freezing. Do not equate a ZIP rename with a new task or classify every hash-named task as a connector.
- Choose the newest acceptance-backed package per family, joining the exact digest to its handoff. Upload time alone is not acceptance chronology. Label handoff PASS as reported until the referenced evidence is verified.
- Keep historical metadata separate from the selected version. Compute difficulty from four eligible saved rewards using reward exactly 1.0; do not trust a bucket without knowing whether it counts successes or failures. Never run new trials to fill metadata gaps.
- Only X tasks are connectors under this user's convention. Read README/instruction and explicit runtime dataset configuration for R/S, record exact paths and contradictions, and leave unknowns unknown. Do not edit dataset fields to manufacture provenance. Trainer/submitting-account attribution is reported, not verified authorship.
- Prefer 1/4 and 2/4 while retaining available 0/4 and 3/4 and reducing trainer concentration. Show feasible connector, domain, R/S and difficulty supply. Do not claim an unavailable 30/30 mix or silently override it; label a feasible alternative provisional pending approval.
- Emit one shortlist and one exclusion/snapshot evidence set. Before execution require exactly the approved count, unique resolved families, zero excluded-family overlap, current source hashes and generation bindings, and one manifest checksum shared by both engineers.
- Reuse existing selection code when correct. Never invent candidates, hide shortfalls, substitute versions in place, or start paid checks as a side effect of selection.
