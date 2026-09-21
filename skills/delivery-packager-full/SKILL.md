---
name: delivery-packager-full
description: Fuller variant of `delivery-packager`: packages by execution type and keeps the twelve mechanical checks inline (the same G01-G12 in `repackaging-qc-gate`). End-to-end Harbor/Shannon task delivery — select a batch from the accepted GCS source, audit it against the fourteen QC factors, remediate and sanitise what is genuinely wrong, package by execution type and difficulty with a reconciled manifest, and emit the client dataset report. Covers running the pass over a whole batch in parallel. Use when asked to prepare, package, remediate, sanitise, re-organise or ship a batch of Harbor task archives, or to produce a dataset/delivery report for one. Runs end to end without further input.
---

# Harbor delivery packager

> Two packager skills exist. This one packages by **execution type** and carries the twelve mechanical checks inline. `delivery-packager` packages by **difficulty/category** and covers running a whole batch in parallel.

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
| 1 | <VM_IP> | 7 | <VM_IP> |
| 2 | <VM_IP> | 8 | <VM_IP> |
| 3 | <VM_IP> | 9 | <VM_IP> |
| 4 | <VM_IP> | 10 | <VM_IP> |
| 5 | <VM_IP> | | (node 6 does not exist) |

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_gcp_taskmining -N "" -C "harbor-delivery"
cat >> ~/.ssh/config <<'EOF'
Host task-mining-5
    HostName <VM_IP>
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

1. **Family adjudication.** Group by declared `task.name`, then strip variant suffixes (e.g. output-format or
   version suffixes). Canonical member: prefer a descriptive name over an opaque pipeline id, then shortest.
2. **Exclude** 4-pass tasks and any task without four recorded rewards.
3. **Split.** Connector supply is usually the binding constraint. If the requested connector share is not
   achievable from the source, deliver the achievable split and report the shortfall — never pad with old
   versions, format variants or invented tasks.
4. **Balance domains** with largest-remainder capped by supply, preferring 2-pass then 1-pass then 3-pass
   tasks within each domain.
5. **Freeze**: write `manifest/selection_manifest.csv`, compute and record its SHA-256. If you regenerate the
   selection, **version the file** — never overwrite. Overwriting destroys the only record of what was
   previously selected, and it cannot be reconstructed afterwards.

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

When a check turns out to be wrong, fix the check and re-run — do not hand-wave the flag away.

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

### The twelve mechanical checks

The classes below are principles. Their concrete detection rules, severities and do-not-flag lists
live in **`REPACKAGING-QC-GATE.md`** as checks **G01–G12**, with `qc_gates.py` beside it as a
read-only detector (`--gate` / `--csv` / `--json` / `--warn-only`, exit 1 on any BLOCK). Run the
gate twice: before this phase to produce the work list, after it to prove every class went to zero.

| Gate | Class below |
|---|---|
| G01 mutable image reference | Mutable dependency identity |
| G02 internal infrastructure address | Sensitive or environment-specific data |
| G03 authoring-machine path | Sensitive or environment-specific data |
| G04 undeclared connector data provenance | Undeclared provenance |
| G05 package identity mismatch | Identity mismatch |
| G06 documentation contradicts evidence | Documentation that contradicts evidence |
| G07 missing package documentation | Missing documentation |
| G08 non-task artefact | Non-task artefacts |
| G09 verifier documentation mismatch | Documentation that contradicts evidence |
| G10–G12 battery, band, manifest | Phase 6 completion checks |

The gate's corpus evidence is why this phase exists: **89 of 120 packages needed at least one fix
after passing upstream QC.** Two known defects in the checker itself — it compares Windows
backslash paths against forward-slash manifest paths, so G12 fires on every package; and its macOS
and Windows home-path patterns skip the service-account allow-list the Linux one applies, so G03
fires on the neutral placeholder you just wrote. Confirm both against the package before acting.

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

### Running it over a whole batch

Three things run against every package, in this order, and they are not independent:

1. **Gate detection** (`qc_gates.py`) — produces the work list.
2. **Content pass, one per archive** — G01, G02, G03, G04, G06, G07, G09 plus the binary reward
   conversion, all in a single surgical rewrite so the CRC assertion covers everything at once.
3. **Identity rename** (G05) — after content, because renaming moves every path.
4. **Re-verify** — the gate again, plus the battery and band checks.
5. **Artefact sweep** (G08) — dead last.

**Budget about 18 s per package alone, 40 s under 20 concurrent workers.** Two-thirds of that is the
gate's two runs. On a 232-package batch with 20 workers the whole pass lands in roughly eight minutes.
Cache image-digest lookups across tasks: the cost is per distinct image, not per package.

Give each task its own output directory holding the backup, the rewritten archive and its
`MODIFICATIONS.json`, then delete the gate's scratch copies as each task finishes — four copies of every
archive on disk at once will fill a shared VM faster than you expect.

**Four ways a batch run fails silently.** Every one of these cost real time:

| Trap | What happens | Do instead |
|---|---|---|
| Nested `nohup` + `xargs bash -c` quoting | Collapses, writes no logs, leaves no processes — indistinguishable from "still starting" | Put the driver in a real `.sh` file and launch it with `setsid nohup ./run.sh` |
| `gcloud storage cp -I` with any stale URI | Aborts on the first missing object; you get one file and no error you'd notice | Use per-file `xargs -P` when misses are possible |
| A URI list written on Windows | CRLF puts `\r` on every line, so every URI but the last 404s | `tr -d '\r'` before use |
| A waiter in the agent session | Dies when the session ends; the run itself survives | `setsid` the run, re-arm the waiter, never assume dead waiter means dead job |

Launch detached. A run that survives the session is worth more than one you can watch.

### Then re-verify to zero

Re-run the audit and the sensitive-data sweep over the edited archives. Every class you acted on must return
zero. Refresh hashes and sizes in every manifest. If a class does not go to zero, your fix was incomplete —
find out why before moving on.

---

## Phase 6 — Package

Destination `task-delivery-YYYYMMDD-HHMMSS` (**IST**), never overwriting an existing one.

**Execution type is the parent, difficulty sits under it, domain only under Non-Connector.** Name the
root folder for the batch, not `finalization_qc_accepted_zipped` — that name says nothing about which
delivery it is.

```
delivery/
  manifest.json
  verify_delivery.py
  <batch-name>/
    Connector/          Easier/ | Harder/          connectors that declare no dataset
    Real Connector/     Easier/ | Harder/          dataset = real
    Synthetic/          Easier/ | Harder/          dataset = synthetic
    Non-Connector/      Easier/ | Harder/ {Engineering,Finance,Health,Legal,Other}/
```

Category map: `code` → Engineering, `fin` → Finance, `health` → Health, `law` → Legal, `gen` → Other.

The three connector parents hold archives directly — a connector task carries no domain prefix in its
declared name, so there is nothing to split on. Do not invent a filler level to make the depth uniform.

**A connector with no declared dataset goes in `Connector/`, never into real or synthetic.** Guessing
which corpus it ran against is the one thing Phase 5's provenance rule forbids, and the folder is where
that uncertainty stays visible to the recipient.

Record the scheme in the manifest as a `layout` block — root name, the parent list, and a line saying
what `Connector/` means. The folder names alone do not carry that, and the delivery outlives the
conversation that produced it.

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

---

## Phase 7 — Client dataset report

**HTML only.** No PDF unless asked; no edit toolbar; one file.

Render with headless Chrome if a PDF is ever wanted:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --no-pdf-header-footer --virtual-time-budget=12000 --print-to-pdf=OUT.pdf "file://IN.html"
```

### Typography

Bricolage Grotesque ExtraBold titles, Source Serif 4 body, IBM Plex Mono labels. **Google Fonts'
`/download?family=` endpoint returns HTML, not a ZIP** — fetch from
`raw.githubusercontent.com/google/fonts/main/ofl/<family>/…` and instantiate static cuts from the variable
fonts with `fontTools.varLib.instancer`. Embed as base64 so the file is self-contained.

Set `font-variant-ligatures:none`, or "verifier" is stored as "veriﬁer" and the output is un-searchable for
it. When validating extracted text, normalise ligatures and compare a whitespace-stripped variant too —
letter-spaced labels extract as `T A S K S`. Those are extraction artefacts, not document defects.

### Structure

Sections numbered **contiguously**. If you drop one, renumber the rest and fix every cross-reference:

```
01 Where it stands        READ THIS FIRST     lede plus verbatim pull-quote
02 Score distribution     N TASKS             full vs lighter cards, two-bar chart
03 Topical breakdown      BY DOMAIN           domain chart; caption uses the bar values
04 Category pass rate     THE FOURTEEN QC CATEGORIES   per-factor rate with (pass/den)
05 Realistic output files FROM THIS TREE      card plus extension chart of matches only; name table if ≤20
06 Named reference list   CANONICAL TASK IDS  present / not in batch / connector among present
07 Everything else        NOT IN 05 OR 06     remainder by domain; remainder plus covered equals N
```

Hard locks: title is exactly `<N> Tasks, Delivered Clean`. Hero is `N`, `100%`, `0`, `H`. The pull-quote is
verbatim. One N everywhere. Every chart caption uses that chart's own numbers.

**Register:** flat and declarative, like an engineer stating results. Not an audit memo — no hedging, no
"we", no tooling names, host paths, bucket URIs, image digests or internal addresses. Scan the rendered text
for those before shipping.

**Scope is the requester's call.** Itemizing finalization fixes is legitimate and reads as rigor; omitting
that section is equally legitimate, since a report need not narrate internal process. What is **not**
acceptable is asserting the opposite — that nothing was found, or that packages are untouched as authored,
when archives were modified. Omission is fine; a false claim is not. Keep the provenance record either way;
it is what makes the corrections defensible if anyone diffs against source.

**Never ship** alongside the delivery: the changelog, modification record, TODO, hygiene report, internal
verification report, audit CSV, or any backup directory. Send the delivery directory and the report, nothing
else.

---

## Where the runbook is wrong

`harbor-60-task-delivery-runbook.md` will send you the wrong way on all of these:

| Runbook says | Reality |
|---|---|
| An even connector / non-connector split, hard gate | Connector supply is far smaller than the non-connector side. Deliver the achievable split; do not pad |
| Blocked pending more connector supply | The non-connector side is fine. Report the shortfall and continue |
| Oracle in E2B **and** Modal | E2B rejects these tasks (`400: Timeout cannot be greater than 1 hours` against a much longer `agent.timeout_sec`), and no Modal token is provisioned. Docker is the only workable environment |
| Run a full multi-unit audit per task | Tasks already carry a client harbor check verdict from the same profile. Re-running repurchases it |
| Include tasks at the bottom difficulty band | Verify the band exists in the source before planning around it |
| A domain has fewer usable tasks than it does | Usually the folder-name classification bug. Re-derive from declared names |
| A stricter default difficulty policy | Overridden by the delivery policy. Preserve the raw result and record the reconciliation |
| Two-engineer manifest lock with dual acknowledgement | Single operator. Freeze and hash the manifest, skip the ceremony |

---

## Environment gotchas

- **`rsync` is not installed on the VMs.** Use `ssh <host> 'cd DIR && tar cf - SUB' | tar xf -`. Expect
  roughly 10 MB/min on a large tree; run it backgrounded.
- **`pkill -f <pattern>` matches its own SSH command** and kills the shell. Use a self-excluding pattern such
  as `"job-name-abc[1]"`.
- **`docker.service` can be restarted by systemd** (unattended upgrades), SIGKILLing every container without
  a restart policy — `exit=137, oom=false`, all within milliseconds. If foreign containers die, check
  `journalctl -u docker` before assuming you caused it, and tell the owners.
- **openpyxl destroys pivot tables and charts** on save. For XLSX edits, rewrite only the target
  `xl/worksheets/sheetN.xml` inside the zip, copy every other part byte-for-byte, and write cells as
  `t="inlineStr"` so `sharedStrings.xml` is never touched.
- The sandbox may block writes outside the project directory and block handling credentials. Write to the
  scratchpad and `cp` into place; for secrets, hand the user a one-liner that pipes the value without
  echoing it.

---

## Deliverable checklist

- [ ] GCS never written to
- [ ] Backups exist for every destructive step, and their paths were stated
- [ ] `unnamed` domain count equals the connector count (proves declared-name classification)
- [ ] Difficulty recomputed from raw rewards matches every folder; a pass is exactly 1.0
- [ ] Every audit FLAG opened and confirmed against the package before being reported
- [ ] Every modification recorded with its basis and any counter-evidence
- [ ] Surgical rewrites asserted: only the intended entries changed CRC
- [ ] Remediation and sanitisation re-verified to zero in the same pass
- [ ] Manifest and disk agree in both directions; hashes and sizes recomputed
- [ ] OS artefacts swept last, immediately before handover
- [ ] Report: one HTML, contiguous section numbers, no internal references, no false claims
- [ ] Internal records excluded from the client bundle
