---
name: querying-harbor-kg
description: Use when answering any question about obi-rl-gym infra/connectors structure, data flow, callers/callees or blast radius, and work/kg/graphify-out/graph.json exists. Also when the user types /graphify query, path, explain or affected.
---

# Querying the harbor KG

**REQUIRED BACKGROUND:** harbor-kg (locations; run from `work/kg`).

Answer from the graph first; open repo files only to confirm a specific edge the graph cites.

| Question shape | Command |
|---|---|
| "How does X work / flow from A to B?" | `graphify query "<question>"` (BFS; add `--dfs` for one specific path, `--budget 3000` for more) |
| "Is A directly linked to B?" | `graphify path "A" "B" --undirected` with exact code symbols as endpoints. Trust only 1–2 hop results. In this graph almost every longer path runs through the pathlib `Path` hub (`FastPreqcRunner` → `.run_task()` → `Path` ← `main()` ← `pipeline.py`), which is noise, not a real link. For flow between stages, use `query` or `explain` each stage. |
| "What is X?" | `graphify explain "X"` |
| "What breaks if I change X?" | `graphify explain "X.py"` lists the file's functions, then `graphify affected "<function>()" --depth 2` for each one. A file node only has `contains` edges, so `affected "X.py"` always prints "No affected nodes". Always confirm in Git Bash from `work/kg`: `rg -nw X ../obi-rl-gym/obi-rl-gym/infra ../obi-rl-gym/obi-rl-gym/connectors`. harbor_gce imports siblings as bare `import auto_batch`, which the graph does not link (none of `auto_batch`'s 7 non-test importers appear), and tests and module-constant uses are not in the graph either. |

Node names are the labels in `graph.json` (function names, file names, doc concepts like `Pre-QC gate`). Generic words match everywhere: "task … finalisation" starts BFS on the Jira `Task` model and `move_issues_to_board`. Put component words in the question (`harbor_gce`, `auto_batch`, `canonical_qc`, `final_qc`, `preqc`), raise `--budget 3000` when output says TRUNCATED, and run `graphify explain` on each stage file to follow its `calls` edges. Still noisy? grep `graphify-out/.graphify_labels.json` or `GRAPH_REPORT.md` for the community name and query with those terms.

Cite `source_location` (file:line) from the output when stating a fact. Edges tagged INFERRED/AMBIGUOUS are hypotheses — say so.

## Staleness

The graph is a snapshot of the untracked nested tree (see harbor-kg), so git dates and the commit id in `GRAPH_REPORT.md` say nothing about freshness. Compare file times instead (~2 min, run in background):

```
find ../obi-rl-gym/obi-rl-gym/infra ../obi-rl-gym/obi-rl-gym/connectors \( -name '*.py' -o -name '*.md' \) -newer graphify-out/graph.json | grep -vE '/(tests?|final-50[^/]*|kyle_[^/]*)/'
```

No output means the graph is current. If files the question touches are listed, say the answer may be stale and offer a rebuild (building-harbor-kg). Don't rebuild silently.

## Common mistakes

- Reading the repo instead of querying — the graph exists to avoid that.
- Running `graphify` from `work/` or the repo root: it finds no `graphify-out/` and offers to build a new graph there. Always `cd work/kg`.
- Treating `Test Client Fixtures_N` communities as real: 74 one-node communities of unresolved type references (`Any`, `client`) — noise.
