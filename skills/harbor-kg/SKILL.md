---
name: harbor-kg
description: Use when asked how obi-rl-gym infra/ or connectors/ code fits together (architecture, call flows, "what depends on X", pre-QC→finalisation flow), or when asked to build, refresh, query, label or export the graphify knowledge graph / Obsidian vault in work/kg.
---

# Harbor knowledge graph (work/kg)

One graphify graph of `obi-rl-gym/obi-rl-gym/{infra,connectors}` (tests, task bundles and data files excluded) plus an Obsidian vault built from it. Everything lives in `C:\cpio_db\Turing\work\kg`; run every `graphify` command from that directory (it looks for `./graphify-out/graph.json`).

**Source tree caveat:** the graph scans `work/obi-rl-gym/obi-rl-gym/`, an untracked nested copy. The `work/obi-rl-gym` clone's git index is empty (every tracked file shows as a staged deletion), so `git pull` does not change what the graph reads, and git dates say nothing about graph freshness. This holds until the clone is repaired.

| Path | What |
|---|---|
| `kg/graphify-out/graph.json` | the graph (~38k nodes, 2k communities) — source of truth |
| `kg/graphify-out/.graphify_labels.json` | community names |
| `kg/graphify-out/GRAPH_REPORT.md` | god nodes, surprising connections, suggested questions |
| `kg/vault/` | Obsidian vault (40k notes, gitignored) — never `ls`/`du` it, NTFS takes minutes |
| `kg/detect.py chunk.py extract_ast.py merge_build.py relabel.py` | the build pipeline scripts |
| `kg/graphify-out/.graphify_python` | interpreter to use for scripts (uv tool env). Mixing graphify versions changes node dedup and `graph.json` refuses to shrink |

## Which sub-skill

| Need | REQUIRED SUB-SKILL |
|---|---|
| Answer a question from the graph (default for any architecture question) | querying-harbor-kg |
| Repo pulled / scope changed / graph missing → full rebuild (no incremental path) | building-harbor-kg |
| Community names are `Community N` or bare node names (`BaseModel`, `app.js`) | labeling-kg-communities |
| Vault missing, stale, or wanted inside another vault | exporting-kg-obsidian |

Rule: if `graph.json` exists, a question is a **query**, never a rebuild. Rebuild only on an explicit request or when the graph is missing.
