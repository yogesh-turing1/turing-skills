---
name: harbor-gce
description: Connect to Yogesh's Harbor GCE worker VMs for task checks or analysis while keeping obi-rl-gym mining data untouched.
---

# Harbor GCE

Connect with system SSH as `root` on port `2222`. Never store, print, or embed VM passwords in files or commands; let SSH prompt interactively. Reuse an open SSH session during the current turn.

## VM Map

| Node | Host | IP | Mining users |
|---|---|---|---|
| 1 | `task-mining-node-1-pw` | `<VM_IP>` | `<OWNER>` |
| 2 | `task-mining-node-2-pw` | `<VM_IP>` | `<OWNER>` |
| 3 | `task-mining-node-3-pw` | `<VM_IP>` | `<OWNER>` |
| 4 | `task-mining-node-4-pw` | `<VM_IP>` | `<OWNER>` |
| 5 | `task-mining-node-5-pw` | `<VM_IP>` | `<OWNER>` |
| 7 | `task-mining-node-7-pw` | `<VM_IP>` | `<OWNER>` |
| 8 | `task-mining-node-8-pw` | `<VM_IP>` | `<OWNER>` |
| 9 | `task-mining-node-9-pw` | `<VM_IP>` | `<OWNER>` |
| 10 | `task-mining-node-10-pw` | `<VM_IP>` | `<OWNER>` |

Node 6 does not exist. Host aliases might not resolve locally, so use the mapped IP directly:

```text
ssh -p 2222 root@IP
```

## Connection Workflow

1. If the user names a node, connect to that node. Otherwise ask which node; do not silently choose a teammate's active VM.
2. Open an interactive TTY SSH session and wait for the password prompt. Never include the password in a generated command, script, skill, log, or report.
3. After login, check `hostname`, `who`, `uptime`, `free -h`, and `df -h /` before starting resource-heavy work.
4. Check `claude auth status`, `gcloud auth list --filter=status:ACTIVE`, `hr --help`, and Docker only when the requested work needs them. Report account mismatches; never log out or switch accounts without explicit approval.
5. Keep the SSH session open and execute subsequent commands through it.

## Data Boundary

Treat `/root/mining`, `/root/TT/obi-rl-gym`, and existing mining outputs as read-only. Never edit, delete, move, clean, reset, or install into those directories.

For Harbor modifications, use a separate clone or workspace under `/root/harbor_gce/<purpose>`. Preserve other teammates' work and use a distinct directory per person or run.

The shared accepted-task source is:

```text
gs://<TASK_BUCKET>/tasks/finalisation_client_qc_accepted_iteration_2/
```

Listing and reading are safe diagnostics. Do not upload, overwrite, or delete GCS objects unless the user explicitly requests that exact mutation.

Before a paid multi-task Harbor run, report task count, model, concurrency, estimated cost, output path, and whether another run is active. Require explicit approval for material model spend.

