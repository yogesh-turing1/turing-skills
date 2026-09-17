# Workflow Ledger

Read and update this record at every gate. JSON is preferred so resumed sessions can validate state mechanically.

## Minimum fields

```json
{
  "schema_version": 1,
  "task_id": "",
  "task_root": "",
  "source_archive": "",
  "baseline_sha256": "",
  "frozen_sha256": "",
  "package_version": "",
  "decision_rule": "",
  "state": "intake",
  "change_log": [],
  "cold_review": {"status": "pending", "a1_a6": {}},
  "tests": {"deterministic": [], "mutations": [], "equivalence": []},
  "freeze": {"included_files": [], "secret_scan": "pending", "artifact_paths": []},
  "aws": {
    "job_name": "",
    "ssm_command_ids": [],
    "s3_locations": [],
    "package_sha256": "",
    "oracle": {},
    "attempts": []
  },
  "classifications": [],
  "qc": {},
  "human_decision": "pending",
  "handoff": {"approved": false, "urls": [], "readback_verified": false}
}
```

## State transitions

Only move forward when the current gate passes:

`intake -> cold_review -> audit -> frozen -> oracle_passed -> evidence_complete -> qc_complete -> awaiting_human -> handed_off`

A package edit after `frozen` moves state back to `audit`, clears the frozen hash and all evidence tied to it, and requires a new unique version and job name. An infrastructure, packaging, grading, or missing-artifact issue moves the evidence run to `invalid`; it does not count toward the model pass-rate decision.

## Resume check

On resume, verify the current task tree hash, frozen package hash, S3 evidence identity, and last completed gate before taking action. If they disagree with the ledger, stop and reconcile rather than attaching stale evidence.
