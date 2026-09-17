---
name: turing-aws-harbor-runner
description: Run Company Bench/Turing Harbor Oracle and five-attempt GLM evidence batches through the persistent AWS EC2 runner instead of local Docker. Use whenever Codex is asked to run, rerun, measure, benchmark, accelerate, or collect Harbor evidence for a Turing task; submit a frozen task package; inspect an AWS Harbor run; retrieve its artifacts; diagnose runner, SSM, S3, Docker, credential, quota, or model exceptions; or resize/manage the existing Turing AWS runner. Pair with turing-trainer-qc for trainer judgment and evidence interpretation.
---

# Turing AWS Harbor Runner

Use the established AWS runner for Turing evidence runs. Do not recreate the
infrastructure or default to local Docker while this runner is healthy.

## Required companion workflow

Use `turing-trainer-qc` for task quality, freezing, Oracle requirements, model
failure classification, and submission readiness. This skill owns only remote
execution and evidence retrieval.

## Canonical files

Resolve the workspace root, then use:

- `Turing-Master-2/90-Shared-Resources/aws-harbor-runner/submit-task.ps1`
- `Turing-Master-2/90-Shared-Resources/aws-harbor-runner/README.md`
- `Turing-Master-2/90-Shared-Resources/aws-harbor-runner/resize-runner.ps1`

Read the submitter and README before a run if either has changed since the last
inspection. Read [references/deployment.md](references/deployment.md) when
diagnosing AWS state, cost controls, authentication, or evidence locations.

## Run workflow

1. Confirm the task directory is the exact frozen version intended for evidence.
   Record its package hash/checksum according to `turing-trainer-qc`.
2. Choose a unique job name that includes task identity and version. Never reuse
   a job name for a changed package.
3. Determine requested artifact paths from the task. Use the submitter defaults
   only for the standard cron task outputs; otherwise pass `-Artifacts` as a
   comma-separated list of absolute `/app/...` paths.
4. Submit from PowerShell:

   ```powershell
   & 'Turing-Master-2\90-Shared-Resources\aws-harbor-runner\submit-task.ps1' `
     -TaskPath 'ABSOLUTE_OR_WORKSPACE_RELATIVE_TASK_PATH' `
     -JobName 'UNIQUE_FROZEN_VERSION' `
     -Artifacts '/app/output-a,/app/output-b'
   ```

5. Capture the returned SSM command ID and S3 evidence destination. The command
   is asynchronous; monitor it with `aws ssm get-command-invocation` rather than
   submitting again.
6. Require remote Oracle reward exactly `1.0` with zero exceptions. The runner
   automatically aborts the model batch if Oracle fails.
7. After completion, inspect the S3 Oracle and GLM `result.json`, every trial's
   reward, exception, verifier output, trajectory, and requested artifacts.
   Never treat an infrastructure exception as model-owned difficulty.
8. Confirm all five model trials completed and all requested artifacts were
   captured. Tie the result to the frozen task checksum.
9. Allow the runner to stop after 45 idle minutes, or stop it immediately after
   all inspection requiring the live host is complete.

## Operating rules

- Preserve five-wide concurrency; the deployed 8-vCPU/32-GiB runner completed a
  full Oracle-plus-five acceptance batch in 6m43s without memory pressure.
- Reuse the Oracle-built Docker image for GLM attempts. Do not force-build every
  trial.
- Never place API keys in task packages, scripts, user data, logs, or evidence.
  Credentials belong in encrypted Parameter Store.
- Do not open inbound ports or create SSH keys. Administer through SSM.
- Do not stop unrelated EC2 instances to free quota.
- Use `resize-runner.ps1` only after it confirms quota and live vCPU capacity.
  Resizing is optional while the current runner meets the time target.
- If a Dockerfile uses private Google Artifact Registry and submission reports
  expired auth, run `gcloud auth login` locally and resubmit. Do not export a
  long-lived Google credential.
- Treat failed task packaging, SSM commands, registry login, missing artifacts,
  OOM, Docker failures, and API authentication errors as invalid evidence.

## Fast diagnostics

- Submission fails before an SSM ID: inspect local AWS/gcloud auth and packaging.
- SSM command fails immediately: retrieve `StandardErrorContent`, then inspect
  `/opt/turing-harbor/jobs/JOB-console.log` through a separate SSM command.
- Oracle fails: stop; inspect its verifier evidence before any GLM run.
- Five trials show exceptions: exclude the batch and repair infrastructure or
  credentials before rerunning.
- Runner unavailable: read its ID from `/turing/harbor/instance-id`, start it,
  wait for EC2 running and SSM `Online`, then retry the same frozen version with
  a new evidence job name.

