# turing-skills

Agent skills for Turing / Company Bench / Harbor trainer and QC work, packaged for Claude Code and Codex. Anyone can add their own skills — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Install

```bash
git clone https://github.com/yogesh-turing1/turing-skills
# Claude Code: copy (or symlink) a skill into your skills dir
cp -r turing-skills/skills/harbor-kg ~/.claude/skills/
# Codex: same folder layout under ~/.codex/skills/
```

Environment-specific values (VM IPs, buckets, platform URLs, teammate names) are redacted as `<PLACEHOLDER>` — fill them from your team's internal docs, never commit them back.

## Skills

`initialise`, `wrap` and `feedback` are workspace-ritual skills: they expect `.claude/init.sh`, `sync.sh`, `CHANGELOG.md`, `OBJECTIVES.md` and `FEEDBACK.md` in the workspace root.

| Skill | What it does |
|---|---|
| [`building-harbor-kg`](skills/building-harbor-kg/SKILL.md) | Use when the harbor knowledge graph must be (re)built or refreshed — graph.json missing, obi-rl-gym pulled with code changes, scope changed (new dirs), a graphify version bump, or a "refusing to overwrite / shrink graph.json" error. |
| [`delivery-harbor-task-repair`](skills/delivery-harbor-task-repair/SKILL.md) | Use when Harbor task packages fail client QC with findings about doubled image digests, fractional rewards, oracle-frozen stability evidence, duplicate evaluation batteries, or unbuildable environments — and the packages must be repaired with an auditable record of every change. |
| [`delivery-packager`](skills/delivery-packager/SKILL.md) | End-to-end Harbor/Shannon task delivery — select a batch from the accepted GCS source, audit it against the fourteen QC factors, remediate and sanitise what is genuinely wrong, package into difficulty/category folders with a reconciled manifest, and emit the client dataset report. Use when asked to prepare, package, remediate, sanitise, or ship a batch of Harbor task archives, or to produce a dataset/delivery report for one. Runs end to end without further input. |
| [`exporting-kg-obsidian`](skills/exporting-kg-obsidian/SKILL.md) | Use when the Obsidian vault for the harbor KG is missing, stale after a rebuild or relabel, must be placed inside an existing vault (obsidianKB), or someone asks to open the knowledge graph in Obsidian. |
| [`feedback`](skills/feedback/SKILL.md) | Use whenever the user corrects how Claude worked (not a fact), states a preference ("always…", "never…", "not like that", "I prefer…"), rates an output, or says feedback / learn this — including when the correction is implicit in a terse or annoyed reply. |
| [`google-sheets-task-links`](skills/google-sheets-task-links/SKILL.md) | Recover, reconcile, validate, and export exact original-task, modified-task, and source-row links from Google Sheets cells, including Drive smart chips whose URLs are not visible in plain cell values. |
| [`google-sheets-workbook-operator`](skills/google-sheets-workbook-operator/SKILL.md) | Inspect, analyze, repair, edit, reconcile, export, and validate existing Google Sheets workbooks, including formulas, dashboards, filters, hidden tabs, hyperlinks, Drive smart chips, and operational data integrity. |
| [`harbor-final-check-only`](skills/harbor-final-check-only/SKILL.md) | Run only the explicitly selected final Harbor review against a frozen task manifest and existing evidence, with bounded spend, resumable jobs and VM-local handoff; not a full Harbor audit. |
| [`harbor-gce`](skills/harbor-gce/SKILL.md) | Connect to Yogesh's Harbor GCE worker VMs for task checks or analysis while keeping obi-rl-gym mining data untouched. |
| [`harbor-kg`](skills/harbor-kg/SKILL.md) | Use when asked how obi-rl-gym infra/ or connectors/ code fits together (architecture, call flows, "what depends on X", pre-QC→finalisation flow), or when asked to build, refresh, query, label or export the graphify knowledge graph / Obsidian vault in work/kg. |
| [`harbor-next-batch-selection`](skills/harbor-next-batch-selection/SKILL.md) | Select another Harbor finalisation batch while excluding a prior delivery by canonical identity and exact source versions, with explicit distribution and evidence limits. |
| [`initialise`](skills/initialise/SKILL.md) | Use at the start of a Turing/Harbor session in this workspace, after a context compaction, or whenever unsure what the current objectives, recent changes, or available skills are. |
| [`internal-delivery-report`](skills/internal-delivery-report/SKILL.md) | Build the internal edition of a Harbor/Shannon delivery report — the client report plus everything held out of it: the real four-status audit matrix, every change made to the source archives, the provenance behind each, hygiene before and after, and a per-package change log. Use when asked for an internal, engineering, or full-disclosure version of a delivery report, or when a client report needs its repackaging work put back on the record. |
| [`labeling-kg-communities`](skills/labeling-kg-communities/SKILL.md) | Use when graphify community names are placeholders (`Community N`) or bare node names (`BaseModel`, `app.js`, `.select`), when `graphify label` batches fail with 429 / "usage limit" / "package is required", or after any rebuild or update of the harbor KG. |
| [`querying-harbor-kg`](skills/querying-harbor-kg/SKILL.md) | Use when answering any question about obi-rl-gym infra/connectors structure, data flow, callers/callees or blast radius, and work/kg/graphify-out/graph.json exists. Also when the user types /graphify query, path, explain or affected. |
| [`task-packaging`](skills/task-packaging/SKILL.md) | Package existing benchmark or Harbor task archives from local folders, Google Drive, GCS, or dashboard inventories into difficulty and category folders with a verified JSON manifest. Use when organizing task deliveries or preparing a selected batch of task ZIPs. |
| [`turing-aws-harbor-runner`](skills/turing-aws-harbor-runner/SKILL.md) | Run Company Bench/Turing Harbor Oracle and five-attempt GLM evidence batches through the persistent AWS EC2 runner instead of local Docker. Use whenever Codex is asked to run, rerun, measure, benchmark, accelerate, or collect Harbor evidence for a Turing task; submit a frozen task package; inspect an AWS Harbor run; retrieve its artifacts; diagnose runner, SSM, S3, Docker, credential, quota, or model exceptions; or resize/manage the existing Turing AWS runner. Pair with turing-trainer-qc for trainer judgment and evidence interpretation. |
| [`turing-false-positive-audit`](skills/turing-false-positive-audit/SKILL.md) | Reconcile disputed Company Bench/Turing QC flags across task packages, runtime evidence and review spreadsheets; identify false alarms with explicit evidence-based confidence. Use for requested false-positive audits, not ordinary sheet editing or automatic task acceptance. |
| [`turing-trainer-lessons`](skills/turing-trainer-lessons/SKILL.md) | Use for Company Bench/Harbor trainer retrospectives, repeated-failure diagnosis, verifier repair, evidence/version reconciliation, package cleanup, Drive upload and tracker handoff, or when starting a new Turing task and needing lessons from prior iterations. Applies concrete mistakes and prevention checks from completed trainer sessions without replacing the authoritative turing-trainer-qc workflow. |
| [`turing-trainer-qc`](skills/turing-trainer-qc/SKILL.md) | Use for Company Bench / Harbor trainer work and internal QC: task-package inspection, portfolio failure triage, prompt/verifier repair, deterministic and mutation grading checks, Oracle and five-run evaluation, semantic hardening, unified QC, version/evidence reconciliation, and submission readiness. Treat the Trainer/QC Bible as the quality authority whenever a task needs configuration, iteration, measurement, packaging, or trainer/QC judgment. |
| [`turing-workflow-orchestrator`](skills/turing-workflow-orchestrator/SKILL.md) | Orchestrate Company Bench/Turing trainer tasks from isolated cold review through verifier repair and calibration, immutable packaging, AWS Harbor Oracle and five-run evidence, unified QC, and approved handoff. Use whenever a Turing task is created, hardened, measured, resumed, reconciled, or prepared for submission. |
| [`wrap`](skills/wrap/SKILL.md) | Use when the user says wrap up / log this / save progress, wants to shape the changelog entry or update objectives by hand, or when the last CHANGELOG entry is a mechanical `auto (…, no summary)` one that needs replacing. (Session end and compaction already auto-write an entry via close.sh.) |
