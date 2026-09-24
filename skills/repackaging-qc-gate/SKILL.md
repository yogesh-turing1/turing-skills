---
name: repackaging-qc-gate
description: The twelve checks (G01-G12) that run at the repackaging stage before client delivery - mutable image references, internal addresses, authoring paths, connector provenance, package identity, documentation that contradicts its own evidence, missing README, non-task artefacts, verifier doc mismatch, difficulty battery, band and manifest reconciliation. Use when repackaging or sanitising Harbor task archives, when deciding whether a finding is real, or when running qc_gates.py over a delivery.
---

# Repackaging QC gate

Twelve checks for the final stage before client delivery: the pass that takes accepted task
archives out of the source bucket and turns them into a shipped package.

Every check here exists because the same defect was found and fixed by hand across a
120-package corpus. This document is the specification for making that pass a gate.

---

## Scope

This is not task QC. Upstream acceptance has already run and every package in the corpus
carried a passing verdict before this stage began. These checks catch what survives that
verdict and only becomes visible when the archive is prepared for a client:

- configuration that cannot be reproduced later
- internal infrastructure and authoring detail that should not leave the building
- documents inside the package that disagree with the evidence packaged beside them
- identity and completeness of the package itself

**Before** below means the archive as pulled from the accepted source bucket. **After** means
the same archive in the final delivered package. Both states come from the pass's own records.

---

## What the corpus shows

120 packages, all already carrying an upstream pass.

| | |
|---|---|
| Packages needing at least one fix | **89 of 120 — 74.2%** |
| Check failures before | **142** |
| Check failures after | **0** |

Three of every four packages required manual intervention *after* passing upstream QC. That is
the case for the gate.

| Check | | Packages before | Rate | Occurrences before | After |
|---|---|---:|---:|---:|---:|
| C2 | Internal infrastructure address | 45 | 37.5% | 1,402 | 0 |
| C1 | Mutable image reference | 32 | 26.7% | — | 0 |
| C4 | Undeclared connector data provenance | 18 | 15.0% | — | 0 |
| C5 | Package identity mismatch | 16 | 13.3% | — | 0 |
| C6 | Documentation contradicts packaged evidence | 13 | 10.8% | — | 0 |
| C3 | Authoring-machine path | 9 | 7.5% | 66 | 0 |
| C7 | Missing package documentation | 7 | 5.8% | — | 0 |
| C8 | Non-task artefact | 1 | 0.8% | 32 | 0 |
| C9 | Verifier documentation mismatch | 1 | 0.8% | — | 0 |
| C10 | Incomplete difficulty battery | 0 | 0.0% | — | 0 |
| C11 | Difficulty band mismatch | 0 | 0.0% | — | 0 |
| C12 | Manifest does not reconcile | 0 | 0.0% | — | 0 |

Occurrence counts are given only where every source in the corpus recorded them; a dash means
the record counts affected packages but not individual hits, and a partial total would
understate it.

C10 to C12 never fired. They are structural invariants — the delivery cannot be correct if they
fail — and they cost nothing to keep armed.

Per-package detail is in `package-findings.csv`, one row per package per check with the
recorded evidence.

---

## The checks

`BLOCK` fails the gate. `WARN` reports and passes. `Auto` says whether remediation is
mechanical or needs a human.

### C1 · Mutable image reference · BLOCK · auto

**Detect.** In `environment/Dockerfile`, `task.toml` and `environment/_app/task.toml`: a `FROM`
line or an `image =` value with no `@sha256:` digest.

**Why.** A tag can be repointed at a different build. Once it moves the package no longer
describes an environment anyone can reconstruct, and a regrade runs against different software
than the recorded battery did. One common base tag was pinned to **eight different digests**
across this corpus — direct evidence the tag had already moved while the set was being built.

**Remediate.** Resolve the tag to its digest and pin all three locations. Record where the
digest came from, when, and what it does not establish: a digest resolved today constrains
future builds, it does not retroactively describe the historical runs.

**Resolving the digest — the trap that makes this check silently do nothing.** A reference is on
a private registry only when it has a `/` *and* its first path segment looks like a host. Deciding
that on a bare `:` instead treats the **tag separator** as a registry port, so `python:3.12-slim-bookworm`
is misread as private, returns unresolvable, and is skipped:

```python
# wrong - every Docker Hub image is skipped, and the run still reports success
if "." in ref.split("/")[0] or ":" in ref.split("/")[0]:
    return None
# right - only a first segment that is actually a host
if "/" in ref:
    host = ref.split("/")[0]
    if "." in host or ":" in host:
        return None
```

This fails quietly: the gate reports "unresolvable, recorded", the run completes, and the
packages ship unpinned. C1 is the second most common finding in this corpus at **26.7%**, and
nearly all of it is Docker Hub, so the whole class disappears. Prove the resolver works on one
known reference before trusting a batch — resolve a tag you have already pinned by hand and
compare the digest. Cache resolutions across tasks: the cost is per distinct image, not per package.

Where a reference genuinely cannot be resolved (a private registry the runner has no scope for),
record it as unresolved and leave the reference alone. Never invent a digest.

**Do not flag / do not touch.** Image references under `evaluations/`, `client_qc/`,
`qc_report.html` or `review.csv`. Those are run evidence, not configuration.

### C13 · Image reference carries two digests · BLOCK · auto

**Detect.** In the same three files C1 covers: a `FROM` line or `image =` value where
`@sha256:` appears more than once.

```
FROM python:3.12-slim-bookworm@sha256:782412e8...2254@sha256:a116514e...8134
FROM python@sha256:a116514e...78134m@sha256:a116514e...78134
```

**Why.** Two digests on one reference is not a parseable OCI image reference. Modal rejects
it at pull. That surfaces as `ImageBuildError` -> `Sandbox not found` -> an oracle that never
ran, so the package reads as a grading failure rather than the packaging defect it is. One
batch of 232 had 169 of them; a second batch of 500 had 52 more.

**This is C1's remediation going wrong, not a separate authoring mistake.** C1 says to pin the
tag to a digest. Where that was applied as an append rather than a replace, the original
reference survived alongside the new one. The second shape above is the same bug with an
off-by-one: the replacement consumed the tag `:3.12-slim-bookworm` *minus its last character*,
stranding the `m`. The stray character is always the tag's final one - `bookwor`**m**,
`2026091`**7** - which is how you can tell the two apart at a glance.

**Why C1 does not catch it.** A doubled reference contains `@sha256:`, so any check asking
only whether a digest is present reads it as correctly pinned. The mechanical image check used
`.+@sha256:[0-9a-f]{64}$`, anchored at the tail, and passed all 169 while every one of them was
unbuildable. C13 is checked *before* the already-pinned skip for exactly this reason.

**Remediate.** Keep the **last** digest and drop everything between the image name and it,
including any stranded character. Evidence that the last one is authoritative: `client_qc/
access-receipt.json` names the second digest and never the first, and the first is the same
constant value in 168 of 169 cases - a template, not a resolution. A digest alone is a complete
reference; the tag is not needed once pinned.

Verify the rewritten reference actually parses rather than trusting the substitution. A repair
regex that expects the two digests to be *adjacent* silently does nothing to the stranded-character
shape, and reports success.

### C2 · Internal infrastructure address · BLOCK · auto

**Detect.** A routable IPv4 in a **host position**: after a URL scheme, after `@`, after a
`host` / `hostname` / `server` / `endpoint` / `base_url` / `proxy` / `gateway` key, or carrying
a `:port`.

**Why.** Internal service endpoints do not belong in a delivered artifact. The largest single
class in this corpus by both packages affected and raw occurrences: one internal gateway,
1,402 occurrences, spread across trial configs, result files and QC records.

**Remediate.** Replace with a neutral placeholder. Grading never resolves these, so behaviour
is unchanged.

**Do not flag.** A bare dotted quad. Task corpora and agent reasoning contain digit-group
notation — a card mask described as `4.4.4.4` — and version-like strings that match a naive
IPv4 pattern by chance. Ignore private, loopback, link-local, multicast and RFC 5737
documentation ranges.

### C3 · Authoring-machine path · BLOCK · auto

**Detect.** All three home-directory conventions, every time:

| Convention | Pattern |
|---|---|
| macOS | `/Users/<name>` |
| Windows | `C:\Users\<name>` |
| Linux | `/home/<name>/` |

Classify by an **allow-list** of service and container accounts — `rlgymagent`, `harbor`,
`runner`, `node`, `user`, `app`, `ubuntu`, `root` — and treat every other name as personal.

**The allow-list is the requirement, not a convenience.** A deny-list of OS conventions misses
whichever platform the author happened to be on, and the packages that leak are exactly the
ones written somewhere the pattern did not anticipate. Adding a new service account is a
one-line edit; discovering a missed convention means a package has already shipped with
someone's name in it.

**Why.** Local paths name individuals and expose the authoring environment.

**Remediate.** Replace with a neutral placeholder.

**Do not flag.** Container and service account paths — `/home/rlgymagent`, `/home/harbor`,
`runner`, `node`. They are generic infrastructure, not personal data, and rewriting them
changes meaning.

### C4 · Undeclared connector data provenance · BLOCK · partial

**Detect.** A task with MCP servers, no `dataset` on any declared server, and exactly one
distinct `GYM_DATASET` value stated anywhere under `environment/`.

**Why.** Whether a connector runs against a real or synthetic corpus changes what the task
proves.

**Remediate.** Declare the value the package already states, and record the basis. Rank the
signals: a value the package states about itself in its own runtime configuration is stronger
than a value inferred from a dependency's name, and the record should say which one each
declaration rests on.

**Do not flag, and do not resolve.** Where the package states both values, or states none,
leave it undeclared and record why — that is an observation about the source, not a defect to
close by guessing. Never overwrite a value the author declared explicitly, even when the
runtime disagrees with it: record the disagreement and leave the declaration standing. This is
the one check that must stay silent rather than push anyone toward inventing a value.

### C5 · Package identity mismatch · BLOCK · auto

**Detect.** Archive filename, internal root directory and the leaf of `task.name` in
`task.toml` do not all agree.

**Why.** Usually the folder is an opaque pipeline id while `task.toml` carries the real name,
so the recipient gets a hash as a filename.

**Remediate.** Rename paths only. Every entry keeps its bytes, CRC, timestamp and mode; prove
it by comparing the full CRC map before and after with the prefix stripped.

**Do not touch.** The old path where it appears under `evaluations/`. Those references describe
where the runs executed at the time. Record them as a known residual.

### C6 · Documentation contradicts packaged evidence · BLOCK · auto

**Detect.** Compare against the count of difficulty rewards equal to exactly `1.0`. Three rules,
all of them load-bearing:

1. **Scan all three documents that can carry a claim** — `review.csv`, `README.md` and
   `qc_report.html`. Reconciling only the reviewer file leaves the other two contradicting it.
2. **Match `pass\s*rate` case-insensitively**, so `passRate` is caught alongside `pass rate`.
   Also match `N/4 passes`. A pattern written against one spelling will walk straight past the
   other, and both spellings occur.
3. **Check every occurrence in the file, not the first.** A document can state the rate more
   than once, and fixing one instance while leaving another is worse than fixing neither —
   the package then disagrees with itself in two directions.

**Why.** The packaged rewards are authoritative and drive difficulty banding. A document
claiming a different rate makes the package argue with itself. This class is also the one most
likely to escape a hand-written sweep, because the claim wording varies while the number does
not.

**Remediate.** Reconcile the document to the evidence, never the reverse.

**Do not flag.** A completion count is not a pass rate — "completed 4/4 executions" and "4/4
runs" say how many trials ran, and rewriting them corrupts a true statement. Do not touch a
bare `N/4` with no claim wording around it; prose contains incidental figures.

### C7 · Missing package documentation · WARN · auto

**Detect.** No `README.md` at the package root.

**Why.** Every other package in the set carries one. The gap is visible the moment a reviewer
opens two archives side by side.

**Remediate.** Generate strictly from in-package evidence: `task.toml`, the verifier set,
`evaluations/`. State in the file that it was generated rather than authored.

**Do not.** Assert anything that cannot be read out of the package.

### C8 · Non-task artefact · BLOCK · auto

**Detect.** `:Zone.Identifier`, `.DS_Store`, `._*`, `__MACOSX`, `.swp`, `.swo`, `.orig`,
`.rej`, `Thumbs.db`, `desktop.ini`, editor backups.

**Why.** Not part of the task. Download markers additionally record how the file reached the
author — in this corpus a `:Zone.Identifier` set also carried a Windows user path.

**Remediate.** Remove them. **Sweep last**, immediately before handover: several are recreated
every time a file browser opens the folder, so a sweep run before packaging looks clean and
ships dirty.

**Never.** Remove a file the task uses.

### C9 · Verifier documentation mismatch · WARN · auto

**Detect.** A verifier `how_justification` naming `<stem>.<extA>` where that verifier's
`source` reads `<stem>.<extB>`.

**Why.** The human-readable field and the machine-readable check disagree about which file is
being verified. Grading is unaffected; a reviewer reading the justification is told the wrong
thing.

**Remediate.** Correct the description string only.

**Never.** Touch the source, assertion, path or weight. Grading behaviour must not change.

### C10 · Incomplete difficulty battery · BLOCK · manual

**Detect.** Not exactly four recorded rewards under `evaluations/difficulty/r1..r4`.

**Why.** Difficulty banding is computed from the four-run battery. Without all four the band is
not derivable and the package cannot be placed.

**Remediate.** Do not ship it. Route to review with the count actually found. Never infer a
missing reward from any other file.

### C11 · Difficulty band mismatch · BLOCK · manual

**Detect.** The band recomputed from the raw rewards differs from the folder the archive sits
in, or from the manifest. **A pass is a reward of exactly 1.0** — not 0.9999999999999988, not
"exit code 0". 3 of 4 is the lighter band, 0 to 2 is full difficulty, 4 of 4 is out of band.

**Why.** Recomputing from the reward files is the only check that cannot inherit an upstream
mistake.

**Never.** Take the band from an upstream field without recomputing it. Store passes, not
failures: a column named `1/4` that secretly means one *failure* is how a task ends up in the
wrong band.

### C12 · Manifest does not reconcile · BLOCK · manual

**Detect.** Manifest and disk disagree in either direction, or a hash, size, id or name is
wrong or duplicated.

**Why.** The manifest is what the recipient verifies against. If it disagrees with the tree,
nothing else in it can be trusted.

**Never.** Carry a hash forward from an earlier stage. Recompute from the delivered bytes.

---

## What is deliberately not flagged

A gate that cries wolf gets switched off. Each of these was observed in the corpus and
classified as **not a defect** after tracing it to its containing field.

| Pattern | Observed | Verdict |
|---|---:|---|
| Anthropic / AWS / Google API keys | 0 | Clear throughout the corpus. |
| GitHub-token-shaped string | 1 | False positive — a substring of an encrypted reasoning blob. Trace every credential-shaped match to its containing field before classifying it. |
| Slack-token-shaped string | 18 | A literal placeholder bound to the gym proxy acting account at image build. It is configuration, not a credential; replacing it changes runtime behaviour. |
| Stale paths under `evaluations/` after a rename | — | Historical run evidence describing where the runs executed. Correct as-is. |
| Author's dated note in a package README | — | The package's own history, not a packaging stamp. |
| A pattern firing on nearly every package | — | A corpus-wide authoring convention is a design choice, not a per-package defect. Investigate once; do not gate on it. |

**The general rule.** When a check fires on nearly every package, the check is wrong — you have
matched a token that appears everywhere, or a schema key that is optional. Open the package and
confirm a finding before acting on it, and when the check turns out to be wrong, fix the check
and re-run rather than waving the finding away. Fixing a false positive frequently exposes a
real defect underneath: C9 exists only because narrowing a file-name match to what the verifier
actually reads revealed that the prose beside it was wrong.

---

## Order of operations

The checks are not independent and the sequence matters.

1. **Content fixes first** — C1, C2, C3, C4, C6, C7, C9. Do them in a **single pass** over each
   archive. Splitting correctness from sanitisation means running the whole verification cycle
   twice and publishing a report that describes a state you have already moved past.
2. **Identity renames after content** — C5. Renaming changes every path, so any content edit
   keyed on the old path must already be done.
3. **Re-verify to zero.** Re-run every check that was acted on. Any class that does not return
   zero means the fix was incomplete; find out why before continuing.
4. **Recompute the manifest** — C10, C11, C12 — from the delivered bytes, never from an
   earlier stage.
5. **Sweep artefacts last** — C8, immediately before handover.

**How to edit an archive.** Stream entries, edit only the targets, copy every other entry's
bytes and metadata verbatim, then **assert that the set of CRC-changed entries equals exactly
the intended set** and abort on any surprise. Never unpack and repack wholesale: it perturbs
timestamps, permissions and ordering, and you lose the ability to prove nothing else moved.

**Record every change** in a modification record grouped by class, with a per-package map. For
any fix resting on inference rather than recovered fact, record the basis, what it does *not*
establish, and any evidence pointing the other way. That record is what makes the corrections
defensible if anyone diffs the delivery against the source.

---

## Two defects in `qc_gates.py` itself

The checker is a reference implementation, not an oracle. Two of its own bugs will send you chasing
findings that do not exist. Both were confirmed by opening the packages.

**G12 fires on every package when run on Windows.** Line ~371 builds the on-disk set with
`str(p.relative_to(root))`, which yields backslashes, and compares it against the manifest's
forward-slash `package_path`. The two sets never intersect, so every archive is reported both
unlisted and missing. The fix is `.as_posix()`. Until then, reconcile the manifest yourself and
ignore G12's output entirely — a finding count equal to twice the package count is the tell.

**G03 re-flags the placeholder you just wrote.** `SERVICE_ACCOUNTS` is applied to `HOME_PATH`
(the Linux pattern) but not to `MAC_PATH` or `WIN_PATH`. So `/Users/user` — the allow-listed neutral
value the remediation writes — still matches, and the check never returns zero no matter how many
times you fix it. Confirm G03 by applying the allow-list to all three conventions yourself; if the
only survivors are allow-listed accounts, the class is clean.

The general rule from the do-not-flag section applies to the tooling as much as the packages: a check
that cannot be driven to zero by a correct fix is a broken check. Prove which it is before you either
act on it or dismiss it.

---

## Files

| File | What it is |
|---|---|
| `REPACKAGING-QC-GATE.md` | This document. |
| `qc-gate-checks.json` | Machine-readable catalogue: id, severity, auto-remediable, detection rule, rationale, remediation, do-not-flag, and the corpus evidence per check. |
| `evidence-summary.csv` | One row per check: packages and occurrences before and after, severity, and whether remediation is mechanical. |
| `package-findings.csv` | One row per package per check: state before, state after, recorded evidence. |
| `qc_gates.py` | Reference implementation of the detection half. Standard library only, read-only, `--csv` / `--json` / `--gate` / `--warn-only`. Detects; does not remediate. |
