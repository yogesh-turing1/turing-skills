---
name: harbor-batch-categorise
description: Put the Company Bench label - <harness> · <connector count>, e.g. "Zeta · Multi-connector" - on Harbor task packages, and split a batch by it. Use when asked to categorise a batch, to say which tasks are Aster or Zeta, to count single vs multi-connector, to check a Drive folder's "NC/RC/S" or Company Bench counts against what is actually inside, or to tell Company Bench from Computer Bench. Reads the package, never the folder title. Self-contained: standard-library Python, no other repo needed.
---

# Company Bench categorisation

Every Company Bench task carries a two-part label:

    <harness> · <connector count>        e.g.  Zeta · Multi-connector

The **harness** is which environment it runs in, Aster or Zeta. The **count** is
how many connector tools it declares, one or two-and-more.

`scripts/categorise.py` is the whole implementation; `reference/COMPANY-BENCH-CATEGORIES.md`
is the rule it encodes.

## Where each half comes from

| | Source, in order |
|---|---|
| **harness** | the base image in `environment/Dockerfile` — `aster` in the name → Aster, `zeta` → Zeta. No image, or a neutral one: the tools it uses. `zeta3-sql-gym` is Zeta's alone. GitHub, Notion, Linear, Outlook, Email & Calendar and Google Workspace (`gws-gym`) are Aster's. |
| **count** | the distinct real tools in `task.toml`. |

**Google Drive and Slack settle nothing** — both harnesses have them. A task whose
only tools are those keeps the bare label `Company Bench · …`. Do not guess a
harness from them; an unresolved label is the honest answer and the count is still
correct.

### Images whose name does not say

Some images carry neither word. `KNOWN_IMAGES` in `scripts/categorise.py` pins
those **by exact digest**, and a digest goes in only with the evidence that
settled it.

**A repository name is not evidence.** `kuzphi/company-bench-private` has hosted a
zeta-tagged build *and* a digest whose tasks use only Aster tools. A tag prefix is
not evidence either: the three `connectors-harness` digests are tagged
`company-synthetic-*`, which names neither harness.

What does settle it: the tools the digest's own tasks use. If none is Zeta-only
and the ones with delivered history are Aster-only, it is Aster. If that test is
ambiguous, leave the digest out — an unresolved label costs nothing, and a wrong
one silently moves tasks between harnesses.

## Counting tools

- A tool is a name ending `-gym`, or one of `slack` `linear` `github` `notion`
  written bare.
- `harbor` is the test runner, not a tool. Tags like `read-only` and
  `quality-review` are not tools.
- `slack` and `slack-gym` are the same tool; it counts once.
- 1 → `Single connector` · 2+ → `Multi-connector` · 0 → `connectors not read`.

## The trap

**Connector tools are usually not in `keywords`.** A connector task's `task.toml`
often reads `keywords = ["harbor"]` and names its tools under
`[[metadata.mcp_servers_extended]]`. Reading `keywords` alone labels a whole batch
`connectors not read`.

## Use

```bash
python3 scripts/categorise.py --packages ./batch            # folders or zips
python3 scripts/categorise.py --collected out.json --out report-dir
```

`--packages` reads the packages. `--collected` takes a JSON list of
`{name, declared_name, image, connectors}` when something else already read them —
cheaper when the packages sit unzipped in a bucket and only three small files per
task are needed.

Writes `labels.csv` (one row per task) and `summary.json` (the counts), and prints
the split as a table.

## Checking a stated count

A Drive folder title claims a total, and ComputerBench folders claim `NC x RC y S z`.
**Those are claims.** Run this over the folder's contents and compare. Two
CompanyBench folders were renamed downward on 3 Oct 2026 — Drive keeps the old
title in the folder's `description`, so the delta is recoverable and is evidence of
a dedup, not of loss.

## Report

State: tasks labelled, the split by label, the split by harness × count, how many
carried an image, how many had no readable tools, and every label that came out
`Company Bench · …` with the tools that left it unresolved.
