---
name: task-packaging
description: Package existing benchmark or Harbor task archives from local folders, Google Drive, GCS, or dashboard inventories into difficulty and category folders with a verified JSON manifest. Use when organizing task deliveries or preparing a selected batch of task ZIPs.
---

# Task packaging

Produce a local delivery directory containing original task ZIPs and a manifest that ties every copy to its source and evidence. This is an archive organization workflow, not task authoring or a new QC verdict.

## Establish the batch

- Use the source, destination, selection, difficulty rules, and approvals supplied in the current conversation. Ask only for information that blocks progress; do not ask again for authorization already given.
- Accept a local folder, Drive folder URL, GCS prefix, inventory JSON/CSV, or local HTML dashboard. Decode `file:///` links as local paths. Use available authenticated connectors or installed storage clients for remote sources.
- If no destination is specified, create a new `task-delivery-YYYYMMDD-HHMMSS` directory in the current workspace, using IST. Do not overwrite an existing delivery.
- If the user requests only a proposal or inventory, return that without copying archives. Otherwise complete local packaging and verification, rather than stopping after a plan.
- If no task count or selection is supplied, package all eligible unique tasks. Do not impose a 50-task limit or a 10/40 difficulty quota. Honor an explicit task list; report excluded requested tasks individually.
- For a count-only request, prefer candidates without recorded screening flags, then domain and connector coverage and varied submitters. Use stable task-name ordering to break ties. Record the selection rationale. Never silently substitute tasks to satisfy an explicit list or quota.
- Never fabricate tasks, trial scores, QC results, attribution, or provenance. If the eligible source is too small, report the shortfall; do not duplicate tasks or synthesize replacements.

## Read the actual inventory

- Enumerate all pages of listings within the requested scope. A scan limit is not proof of completeness. A previous three/four-level inspection limit is not a packaging limit unless the user carries it forward.
- Prefer machine-readable inventory over scraping rendered table text. For Harbor dashboard HTML, parse the JSON inside `script#report-data` without executing page scripts. Relevant fields include `taskrows`, `archive_uris`, `versions`, `bucket`, `buckets`, `connectors`, `category`, `possible_owners`, `matrix_statuses`, `exact_groups`, and `similar`.
- Distinguish task names from archive versions. Recalculate all counts; never reuse numbers from another batch.
- Record the source snapshot. Do not merge an older Drive delivery and newer GCS inventory by matching names alone. Use the exact archive version identified by the selected evidence; preserve a GCS generation suffix or other available version identifier when retrieving it.
- Existing folder labels are hints. Classify the selected archive using its associated trial evidence. Inventory-only evidence may be used when tied to that exact version; identify the evidence basis and verification limits in the manifest.

## Classify

Default difficulty rule, unless the user overrides it:

| Completed scored trials | Folder |
| --- | --- |
| Exactly 3 successes out of 4 | `easier` |
| 0, 1, 2, or 4 successes out of 4 | `harder` |
| Missing, incomplete, errored, or a different trial count | Hold for evidence or an explicit alternative rule |

For Harbor GLM evidence, success means full reward `1.0`, not process exit status. Do not count errored trials as valid failures. A valid 0/4 is difficulty evidence, not automatically a defective task. Preserve the original score alongside the binary difficulty.

A version-dependent name can still have a stable difficulty: versions at 0/4 and 2/4 are both harder. This does not resolve which archive to deliver. If versions span easier and harder, classification also awaits archive selection.

- A declared connector routes to `connector`; absence established from task metadata routes to `non-connector`. Missing metadata does not prove absence.
- Split connector folders into `connector-real` and `connector-synthetic` only when requested or matching the supplied layout and provenance is verified. A `*-gym` service name alone does not establish real/synthetic provenance. Preserve existing synthetic-source tasks if in scope; do not generate synthetic data.
- Default non-connector category mapping: Code -> `engineering`, Finance -> `finance`, Health -> `health`, Law -> `legal`, General -> `other`. Preserve the original category in the manifest. Other or unknown domains go to `other` with the uncertainty recorded; retain meaningful source categories when the user asks for them.

## Resolve archives and recorded flags

- Deliver one archive per unique task. Use an explicit user selection or authoritative canonical-version evidence. Do not select the latest timestamp silently when multiple accepted versions remain unresolved.
- Exclude unresolved archive choices, contradictory QC/runtime evidence, unreadable ZIPs, and missing required classification evidence from the ready package. Put the source references and precise reasons in `review-needed.json`; continue with independent eligible tasks.
- For a dashboard with screening flags, exclude unresolved attribution conflicts and exact/near instruction matches from the default candidate selection. They are review leads, not proof that whole bundles are duplicates. A documented resolution or explicit user selection may override a screening exclusion; record it.
- Byte-identical archives can be deduplicated by verified SHA-256 while preserving aliases and source references. Identical instructions alone do not establish identical bundles. Do not silently collapse distinct task names or variants.
- Do not invent a `_missing_review_csv` folder from unrelated screening flags. Preserve that label only when its source meaning is established.
- Report existing QC evidence accurately. Missing independent review is not automatically a new packaging gate unless the delivery requirements say so. Packaging does not assign SHIP approval, run paid evaluations, or repair source tasks.

## Assemble

Default output, creating only folders that contain selected tasks:

```text
delivery/
  manifest.json
  finalization_qc_accepted_zipped/
    easier/
      connector/
      non-connector/{engineering,finance,health,legal,other}/
    harder/
      connector/
      non-connector/{engineering,finance,health,legal,other}/
```

`delivery` is the chosen destination; category braces above describe alternatives, not a literal folder. The historical `finalization_qc_accepted_zipped` name is a layout convention, not a QC assertion; use a neutral `tasks` directory for sources without accepted status.

- Copy original ZIP bytes unchanged. Preserve filenames when safe. Resolve unsafe names or collisions using a safe task slug and verified hash suffix; record the original filename. Validate every destination path stays under the resolved delivery directory, including on Windows. Never overwrite a collision.
- Inspect ZIPs with Python stdlib `zipfile`; avoid extracting them just to organize them. Never execute bundled scripts. If extraction is needed, first reject traversal, absolute paths, and escaping link targets, and impose resource bounds.
- Prefer existing repository helpers, installed storage clients, and stdlib (`pathlib`, `json`, `hashlib`, `shutil`, `zipfile`). No new packaging framework is needed.
- Include an existing report only if it refers to the selected source snapshot; clearly identify an inventory-wide report as broader than a selected subset. Do not fabricate a report PDF.
- An outer ZIP is optional: create it when requested, without recompressing already-compressed ZIPs unnecessarily. Do not upload, share, or submit unless requested; carry out those steps when already authorized.

## Manifest and completion checks

Write UTF-8 `manifest.json` with relative paths using `/`. Include:

- Batch: `schema_version`, `created_at` (ISO 8601 with `+05:30`), `sources`, source snapshot(s), selection rule, requested count/quotas when supplied, difficulty rule, actual packaged/review-needed counts, and counts by difficulty/category/connector.
- Each packaged task: stable `task_id` when available, `task_name`, original filename, `package_path`, `difficulty`, original trial score/model/count, normalized and original category, connector services and known provenance, exact `source_uri`, source version/generation when available, computed `sha256`, `size_bytes`, QC status and evidence references, and any screening resolution.
- Separate reported QC status from checks performed during packaging. Keep unknown optional metadata as `null`, not invented values. Attribution means submitted-by unless original authorship is established.
- When anything is excluded, write `review-needed.json` containing task/source references, observed scores if available, and actionable reasons. Do not count these as delivered.

Before reporting completion:

1. Verify every copied ZIP is readable and passes `ZipFile.testzip()` CRC checks. Report unsupported/encrypted/unreadable archives as unverified rather than passed. Check source and copied-file SHA-256 match and compute actual byte sizes.
2. Re-read the manifest and reconcile its paths, hashes, sizes, unique tasks, classifications, and counts with the actual output. Ensure no unlisted ZIPs or extra versions entered the package. Check requested counts and quotas explicitly.
3. If writing reusable packaging logic, leave one runnable check for meaningful invariants such as classification, collision handling, or source/copy integrity. Use real artifacts for integration checks; never add fabricated task data to a delivery.
4. Report the output link, actual easier/harder totals, exclusions or shortfalls, and verification limits. Describe a subset as partial if it misses the requested target. Do not call a report-only manifest a completed archive package.
