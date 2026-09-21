---
name: delivery-packager
description: End-to-end Harbor/Shannon task delivery — select a batch from the accepted GCS source, audit it against the fourteen QC factors, remediate and sanitise what is genuinely wrong, package into difficulty/category folders with a reconciled manifest, and emit the client dataset report. Use when asked to prepare, package, remediate, sanitise, or ship a batch of Harbor task archives, or to produce a dataset/delivery report for one. Runs end to end without further input.
---

# Harbor delivery packager

Take N accepted task archives from GCS, prove they are sound, fix what is genuinely wrong, and ship a
package plus a client report. Runs unattended: every decision below is already made.

**This supersedes `harbor-60-task-delivery-runbook.md`.** That runbook is stale in ways that will actively
mislead you — see [Where the runbook is wrong](#where-the-runbook-is-wrong). Follow this file.

---

## Operating rules (non-negotiable)

1. **GCS is read-only, always.** `gcloud storage ls` and `cp` down. Never `cp` up, never `rm`, never
   overwrite an accepted object. All work happens locally or in your own VM workspace.
2. **The VM is shared.** Other people's containers, home directories and processes are off-limits. Never
   `docker stop/rm/prune`, never `systemctl restart docker`, never touch mining trees, prior delivery
   directories, or any `/home/<person>/`.
3. **Work in one isolated directory**, `/root/harbor_gce/delivery-<n>-<YYYYMMDD>-<you>/`. Nothing outside it.
4. **Back up before every destructive step.** Copy the tree, then edit. State where the backup is.
5. **Verify, don't assert.** Every count, hash and claim is checked by re-reading the artifact. Never report
   a number you did not just compute.
6. **Never fabricate.** No invented tasks, scores, provenance or attribution. If supply is short, report the
   shortfall rather than padding.

---

## Phase 0 — Connect

VM map (port **2222**, user **root** — port 22 is firewalled and hangs, which reads as a dead host):

| Node | IP | Node | IP |
|---|---|---|---|
| 1 | <VM_IP_NODE_1> | 7 | <VM_IP_NODE_7> |
| 2 | <VM_IP_NODE_2> | 8 | <VM_IP_NODE_8> |
| 3 | <VM_IP_NODE_3> | 9 | <VM_IP_NODE_9> |
| 4 | <VM_IP_NODE_4> | 10 | <VM_IP_NODE_10> |
| 5 | <VM_IP_NODE_5> | | (node 6 does not exist) |

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_gcp_taskmining -N "" -C "harbor-delivery"
cat >> ~/.ssh/config <<'EOF'
Host task-mining-5
    HostName <VM_IP_NODE_5>
    User root
    Port 2222
    IdentityFile ~/.ssh/id_ed25519_gcp_taskmining
    ServerAliveInterval 60
    ServerAliveCountMax 5
EOF
# the password prompt is interactive - hand this one to the user:
#   ssh-copy-id -i ~/.ssh/id_ed25519_gcp_taskmining.pub task-mining-5
```

Pick the node on evidence: `harbor --version`, `nproc`, `free -g`, `df -h /`, `who`, `docker ps`, plus any
running `harbor` processes. Prefer headroom and least foreign activity. Record what is already running so you
never disturb it.

Shared credentials live in `/root/.config/harbor/env`. **Do not edit that file** — put anything you add in
`<workspace>/.env` with `umask 077`. Never echo a secret; validate with an HTTP status code only.

---

## Phase 1 — Inventory and identity

Source: `gs://<TASK_BUCKET>/tasks/finalisation_client_qc_accepted_iteration_2/`
Per task: `<task-name>/<sha256>.zip` plus `<task-name>/review_handoff/<sha256>.json`.

```bash
gcloud storage ls -r "$BUCKET/**" > intermediate/bucket-listing.txt
grep -E "^gs://.*\.zip$" intermediate/bucket-listing.txt | grep -v "/review_handoff/" > intermediate/task-zips.txt
```

- **Exclude `review_handoff/` when counting zips.** Its zips match a naive `<hex>.zip` regex and roughly
  double the count.
- Task **names** are not archive **versions**. Some names carry several archives; canonical is the newest
  `generated_at` in the handoff JSON.
- Pull all handoff JSONs first — they are small and carry `automated_harbor_check.decision`, the profile that
  produced it, `batch_id` and `external_review.status`. Read metadata before downloading any archive.

**Tasks in this source already carry a client harbor check verdict** (typically `PASS`, run with
`claude-code / anthropic/claude-opus-5 / medium`). Re-running `harbor check` repurchases a result that
already exists. Do not propose it as a default.

### Download and validate

For each canonical archive: SHA-256 **must equal the GCS object name**; safe-extraction checks (no absolute
paths, no `..`, no links or specials, single root dir, `testzip()` clean, bounded expansion); `task.toml`
present. Then run the kit's `check_format.py` over the extracted tree.

Remove your own staging directories before `check_format.py` — a leftover scratch dir counts as a task and
inflates `task_count` by one.

---

## Phase 2 — Classify (get this wrong and everything downstream is wrong)

### Connector vs non-connector

Decided **only** by structure:

```python
is_connector = bool(toml['environment'].get('mcp_servers') or toml['metadata'].get('mcp_servers_extended'))
```

Never grep for the substring `mcp` — it appears in every package and classifies the whole set as connectors.
Connector tasks also use a `harbor/` name prefix; non-connectors use `obi/` with `non-connector`/`offline`
keywords.

### Domain — read the DECLARED name, never the folder

```python
declared = toml['task']['name'].split('/')[-1]      # NOT the folder name
m = re.match(r'^(code|gen|fin|health|law)-', declared)
```

**The highest-impact bug in this pipeline.** Some tasks sit in folders named from an opaque pipeline id with
no domain prefix. Reading the folder buckets them all as `unnamed`, understating the real domains and then
corrupting any domain-balanced selection built on top.

The check that proves you got it right: **`unnamed` must equal exactly the connector count.** Connector tasks
genuinely have descriptive names; every non-connector carries a domain prefix. If `unnamed` exceeds the
connector count, you are reading folders.

### Difficulty — count passes, and say which

Four vendor GLM-5.2 runs at `evaluations/difficulty/r{1..4}/verifier/reward.txt`.
**A pass is a reward of exactly 1.0** — not 0.9999999999999988, not "exit code 0".

| Passes of 4 | Band | Folder |
|---|---|---|
| 3 | Lighter, accepted | `easier` |
| 0, 1, 2 | Full difficulty | `harder` |
| 4 | Out of band | **excluded from selection** |

**Store passes, never failures.** A column named `"1/4"` that secretly means *one failure* is how "1/4 maps
to easier" gets read as one pass. Name the field `successes` and keep the four raw rewards beside it.

---

## Phase 3 — Select

1. **Exclude what earlier batches already took**, by folder name **and** by declared name. Different opaque
   folders can declare the same task; matching on the folder alone ships that task twice across batches.
2. **Family adjudication.** Group by declared `task.name`, then strip variant suffixes (e.g. output-format or
   version suffixes). Canonical member: prefer a descriptive name over an opaque pipeline id, then shortest.
   Opaque ids are not only hex — a `<prefix>-single-task-<random token>` wrapper is opaque too, and a
   hex-only test picks it as canonical over the real name.
3. **Exclude** 4-pass tasks and any task without four recorded rewards.
4. **Split.** Connector supply is usually the binding constraint. If the requested connector share is not
   achievable from the source, deliver the achievable split and report the shortfall — never pad with old
   versions, format variants or invented tasks.
5. **Balance domains** with largest-remainder capped by supply, preferring 2-pass then 1-pass then 0-pass
   within each domain — but **quota the easier band separately**. Ranking purely by preference starves
   whichever band the residual pool is poorest in, and the delivered mix collapses onto one bucket. Match the
   band split an earlier accepted batch used, and check the result spans every bucket the source can offer.
6. **Freeze**: write `manifest/selection_manifest.csv`, compute and record its SHA-256. If you regenerate the
   selection, **version the file** — never overwrite. Overwriting destroys the only record of what was
   previously selected, and it cannot be reconstructed afterwards.
7. **Emit an availability pool** alongside it: every canonical archive in the source with a status of
   `batch-N` / `candidate` / `excluded` and the reason. This is what lets a second operator pick a
   non-overlapping batch without re-deriving the whole inventory. State plainly what the remaining pool
   cannot supply — a domain or an execution type that earlier batches have exhausted is a supply fact the
   next operator must plan around, not a detail to leave them to discover.

---

## Phase 4 — Audit the fourteen factors

One row per task and factor into `review/audit-14-factor-findings.csv`, columns `task,factor,status,detail`.
Status is `PASS`, `FLAG` (real defect), `INFO` (systemic or documented), or `NA` (does not apply).

**Use these factor names and scope verbatim** — the report and the client's QC script both key on them:

| Factor | What we check |
|---|---|
| Package consistency | Required files, duplicate tasks, archive identity, and mirrored-file consistency |
| Clarity and scope | Instructions are complete, consistent, and understandable |
| Realism and leakage | Realistic task; answers aren't exposed to the agent |
| Difficulty | Correct four-run battery and pass rate; preserve your 0–3/4 mix |
| Solvability | A legitimate non-oracle run demonstrates completion |
| Stability | Regrading identical outputs produces consistent results |
| Oracle | Recorded reward, correct task version, and valid execution route |
| Environment and files | Runtime configuration, permissions, dependencies, and image identity |
| Connectors | Intended access, configuration, and real/synthetic provenance |
| Deliverables | Requested files and content are actually checked |
| Verifier fairness | No undisclosed wording, ordering, or formatting requirements |
| LLM judge consistency | Judge configuration and consistency, where applicable |
| Reward hacking | Scoring loopholes, answer access, and unintended shortcuts |
| Cross-trial calibration | README/review claims match the actual runs and failure patterns |

Denominators: Connectors is scored against connector tasks only; LLM judge consistency against the judged
subset; everything else against all N.

### Verify every flag before reporting it

Expect **most first-pass flags to be bugs in your checker, not defects in the tasks.** Before a flag is
reported, open the package and confirm it. These failure shapes recur — recognise them by their smell:

| Smell | Why the naive check is wrong | What to do instead |
|---|---|---|
| A check fires on nearly every task | You matched a token that appears in every package, or a schema key that is optional | Detect by structure, not substring |
| "Not referenced by any verifier" | Verifiers can delegate to a custom module, so the filename never appears in the verifier config | Search the whole `tests/` tree, not one file |
| A schema field crashes your parser | Config fields often accept several shapes (a string *or* a mapping) | Normalise every accepted shape before use |
| "Required file is undisclosed" | The file is an input the task provides, a marker the harness itself creates, or the requirement is disclosed by key name rather than filename | Exclude inputs, exclude harness-created files, accept key-name disclosure |
| A capability looks misconfigured | Its config may live in a different file than you expect, and a config block that exists may derive zero actual criteria | Read every location; count real criteria, and return `NA` when there are none |
| "Solution is exposed to the agent" | Build contexts commonly mirror the whole task, including the solution | Only a leak if the image build actually copies it in |
| A pattern fires across the whole batch | Batch-wide authoring conventions are design choices, not per-task defects | `INFO`, not `FLAG` |
| A credential-shaped string | Opaque encrypted blobs contain substrings matching key patterns by chance | Trace each match to its containing field before classifying |
| A "personal" path | Service and container accounts look like home directories | Match real user home paths only |
| A claim disagrees with evidence | Prose contains incidental figures; a completion count is not a pass rate | Match the specific claim wording, never a bare number |
| "Undocumented modification" | Your provenance lookup missed a change group | Union across all groups in the modification record |
| A requirement appears undisclosed | Config carries human-readable justification prose beside the machine-readable check. Prose names files the check never reads | Read the field that actually drives the check, never the serialised blob around it |

When a check turns out to be wrong, fix the check and re-run — do not hand-wave the flag away. Fixing a
false positive often exposes a **real** finding underneath it: prose that disagrees with the check it
describes is itself a defect, just a smaller and different one than the check first claimed.

**The row count is the canary.** The audit emits exactly `tasks × factors` rows. If that total drops, some
task exited the factor loop early — an `if` that should skip one factor's verdict skipped the rest of them
too. Assert the product before reading any percentage off the result.

---

## Phase 5 — Remediate and sanitise

One pass. Do the correctness fixes and the sensitive-data scrub together; splitting them means running the
whole verification cycle twice and shipping a report that describes a state you have already moved past.

### How to edit an archive

**Surgical ZIP rewrite, always.** Stream entries, edit only the targets, copy every other entry's bytes and
`ZipInfo` verbatim, then **assert that the set of CRC-changed entries equals exactly the intended set** and
abort on any surprise. Never unpack and repack wholesale — it perturbs timestamps, permissions and ordering,
and you lose the ability to prove nothing else moved.

Record every change in `MODIFICATIONS.json`, grouped by change class with a `per_task` map, and regenerate a
human-readable changelog from it.

### What to fix

Fix what is **wrong or unsafe**. Leave what is merely *different*.

| Class | Principle |
|---|---|
| **Non-task artefacts** | Editor, OS and download-marker files are not part of the task. Remove them; never remove a file the task uses |
| **Mutable dependency identity** | Anything pinned by a moving tag cannot be reproduced later. Resolve to an immutable digest and record where the digest came from |
| **Undeclared provenance** | If a field the schema expects is absent and the answer is determinable from evidence, declare it — and record the basis *and* the counter-evidence |
| **Identity mismatch** | Folder, archive name and declared name should agree. Rename paths only; never touch file content |
| **Missing documentation** | Generate it strictly from in-package evidence. Assert nothing you cannot read out of the package |
| **Documentation that contradicts evidence** | The packaged evidence is authoritative. Reconcile the document to it, never the reverse |
| **Sensitive or environment-specific data** | Internal addresses, hostnames and authoring-machine paths do not belong in a delivery. Replace with a neutral placeholder |

### What to leave alone

- **Historical run evidence.** Trial logs, trajectories and result files describe what happened at run time.
  Renaming a package leaves stale path references inside them — that is correct and should be recorded as a
  known residual, not rewritten.
- **Placeholders that are functionally load-bearing.** A dummy token in task configuration is config;
  replacing it changes runtime behaviour.
- **Generic infrastructure identifiers.** Service and container account paths are not personal data.
- **Anything you cannot justify from evidence.** Uncertainty is recorded, not resolved by guessing.

### Provenance discipline

When a fix rests on inference rather than recovered fact, say so in the record: what you resolved, when,
from where, what it does *not* establish, and any evidence pointing the other way. If a value was recovered
today it constrains future behaviour — it does not retroactively describe historical runs, and claiming
otherwise is a fabricated fact.

**Rank your signals, and prefer the package's own words.** A value the package states about itself — a
runtime environment variable, an explicit config key — beats a value inferred from a dependency's name.
Record which tasks rest on the strong signal and which on the weak one; they are not the same claim.

**Declare only where the package decides it.** Where the evidence points both ways, or gives nothing at all,
leave the field absent and record why. An undeclared field that the package genuinely does not determine is
an observation about the source, not a defect to close — and a checker that cannot tell those apart will
push you into inventing a value. Where a schema default already covers omission, silence is also an answer.

**Never overwrite an author's explicit declaration to resolve a contradiction you found.** If the author
declared one thing and the runtime says another, record the disagreement and leave the declaration standing.
Deciding which is right is not a packaging call.

### Then re-verify to zero

Re-run the audit and the sensitive-data sweep over the edited archives. Every class you acted on must return
zero. Refresh hashes and sizes in every manifest. If a class does not go to zero, your fix was incomplete —
find out why before moving on.

---

## Phase 6 — Package

Destination `task-delivery-YYYYMMDD-HHMMSS` (**IST**), never overwriting an existing one.

```
delivery/
  manifest.json
  finalization_qc_accepted_zipped/
    easier/  connector/ | non-connector/{engineering,finance,health,legal,other}/
    harder/  connector/ | non-connector/{...}/
```

Category map: `code` → engineering, `fin` → finance, `health` → health, `law` → legal, `gen` → other.
Split `connector-real` / `connector-synthetic` **only** when the layout asks for it and provenance is
verified.

Copy ZIP bytes unchanged; inspect with `zipfile` and never extract to organise. Validate every destination
path resolves inside the delivery root. Never overwrite on collision.

`manifest.json` per task: `task_id`, `task_name`, original filename, `package_path`, `difficulty`, trial
evidence (model, four rewards, **successes**, success definition), normalized **and** original category,
connector services with provenance and its basis, `source_uri`, `source_version`, `sha256`, `size_bytes`,
and the reported QC verdict kept **separate** from the checks you performed. Unknowns are `null`, never
invented. Excluded tasks go to `review-needed.json` with actionable reasons and are not counted as delivered.

**Do not emit a separate checksum file** — the manifest already carries every hash. A second copy is
redundant and reads as ops residue.

### Completion checks — all must pass before reporting done

1. Every copied ZIP readable, `testzip()` clean; recomputed SHA-256 and byte size match the manifest.
2. Manifest and disk agree exactly in both directions; no unlisted ZIPs; unique names; unique hashes.
3. Difficulty **recomputed independently from the raw rewards** matches the folder each task sits in.
4. Counts reconcile with the manifest's own summary; the requested count is met.
5. Leave the verifier as a runnable script that exits non-zero on failure.

Sweep OS artefacts (`.DS_Store`, `__MACOSX`, `._*`) **last** — macOS recreates them every time Finder opens
the folder.