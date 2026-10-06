# How Company Bench tasks are categorised

Every Company Bench task on the dashboard gets a two-part label:

```
<harness> · <connector count>
```

For example **Zeta · Multi-connector** or **Aster · Single connector**.

- The **harness** says *which* Company Bench environment the task runs in: Aster or Zeta.
- The **connector count** says *how many* tools (connectors) the task uses: one, or two and more.

---

## 1. Is it Company Bench at all?

A delivered task counts as Company Bench when the Drive files it as Company Bench: in a
`CompanyBench …` batch folder, or in a `Batch N - CompanyBench …` share folder.

One check overrides the folder: the image the task runs on, when its manifest records one.
In CompanyBench 3, 9 tasks were labelled "computer bench synthetic". They run on a Zeta
image, so they count as Company Bench · Zeta.

Everything else is Computer Bench.

---

## 2. Aster or Zeta (the harness)

The harness comes from the **Docker image** the task runs on: the base image in its
`environment/Dockerfile`, or the image its delivery manifest records.

| The image… | Harness |
|---|---|
| has `aster` in its name | **Aster** |
| has `zeta` in its name, or is one of the known Zeta images (V1 to V4) | **Zeta** |

Some manifests record no image. The dashboard then looks at the connectors the task uses:

| The task uses… | Harness |
|---|---|
| Zeta's own SQL tool, `zeta3-sql-gym` (only Zeta has it) | **Zeta** |
| GitHub, Notion, Linear, Outlook, Email & Calendar or Google Workspace | **Aster** |

If none of these say which, the label starts with **Company Bench** instead of a harness.

> **What they look like in practice.** A Zeta task usually uses the same seven tools: Google
> Drive, Zeta SQL, Jira, Confluence, Freshdesk, Email and Slack. An Aster task usually uses
> one tool, such as GitHub or Notion.

---

## 3. Single connector or Multi-connector (the count)

The dashboard counts the **different connector tools** the task declares: in its
`task.toml`, or in the delivery manifest when the package itself wasn't read.

| Connectors | Label |
|---|---|
| 1 | **Single connector** |
| 2 or more | **Multi-connector** |

Rules for counting:

- **Only real tools count.** These are names ending in `-gym` (`jira-gym`, `slack-gym`…),
  plus `slack`, `linear`, `github` and `notion`.
- **Other entries don't count.** `harbor` (the test runner) and tags such as `read-only` or
  `quality-review` are left out.
- **The same tool written two ways counts once.** For example, `slack` and `slack-gym`.

If no tools are listed at all, the label ends in **connectors not read**.

---

## 4. The labels you will see

Delivery tab, Current view, 6 Oct 2026. Company Bench has 1,673 tasks:

| Label | Tasks | What it means |
|---|---:|---|
| **Zeta · Multi-connector** | 1,356 | Zeta task using several tools: the normal Zeta task |
| **Zeta · Single connector** | 2 | Zeta task using one tool |
| **Aster · Single connector** | 181 | Aster task using one tool: the normal Aster task |
| **Aster · Multi-connector** | 0 | Aster task using several tools (none delivered so far) |
| **Company Bench · Single connector** | 19 | One tool, but nothing says Aster or Zeta (see below) |
| **Company Bench · connectors not read** | 115 | Neither the harness nor the tools are recorded (see below) |

### Why some say "Company Bench" instead of Aster or Zeta

- **19 tasks in Batches 1, 2 and 4.1** (the Company Bench share of each batch): they use
  only Google Drive or Slack, which both harnesses have, and their manifests record no
  image. So nothing tells Aster from Zeta.
- **115 tasks in Batch 5.1:** its manifest lists only `harbor` for these packages, with no
  image and no tools. So neither the harness nor the count can be read.

---

## 5. Pipeline tab vs Delivery tab

Both tabs use the same labels and the same counting rules, but start from different data:

- **Pipeline tab:** tasks in the bucket. The harness comes from the task's own Dockerfile
  image first, and the tool list from its `task.toml`.
- **Delivery tab:** delivered packages. It reads what the Drive folders and their manifests
  say.

So a task's label can be more complete on one tab than the other. For example, a Batch 5.1
task the Delivery tab can't read may be labelled fully on the Pipeline tab, because there
its own package was read.
