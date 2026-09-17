---
name: building-harbor-kg
description: Use when the harbor knowledge graph must be (re)built or refreshed — graph.json missing, obi-rl-gym pulled with code changes, scope changed (new dirs), a graphify version bump, or a "refusing to overwrite / shrink graph.json" error.
---

# Building the harbor KG

**REQUIRED BACKGROUND:** harbor-kg. Run in Git Bash from `work/kg` with `PY="$(cat graphify-out/.graphify_python)"`.

## Refresh = full rebuild

This layout has no incremental path. `graphify update` and `graphify watch` write `graphify-out/` inside the scanned repo, ignore `detect.py`'s excludes, and `graphify update .` scans `kg/` itself. Never run them here.

Caches keep a rebuild cheap: unchanged code and docs are skipped. The scanned tree is the untracked nested copy (see harbor-kg), so a `git pull` alone changes nothing the graph reads.

| Step | Command | Notes |
|---|---|---|
| 1 detect | `$PY detect.py` | ~5 min NTFS walk. Scope and excludes live in the script. Patterns without a leading `/` match at any depth. |
| 2 docs | `rm -f graphify-out/.graphify_chunk_*.json; $PY chunk.py` | Prints `N files need extraction` and the chunks. If N is 0, skip. Otherwise run one `general-purpose` subagent per chunk using `~/.claude/skills/graphify/references/extraction-spec.md`, with FILE_LIST, CHUNK_NUM, TOTAL_CHUNKS, DEEP_MODE=false and an absolute CHUNK_PATH (`…/kg/graphify-out/.graphify_chunk_NN.json`) filled in. Drop favicon, og and icon images. The `rm` matters: step 4 merges every chunk file it finds. |
| 3 code | `$PY extract_ast.py` | ~2 min. Run it in the background, alongside step 2. |
| 4 build | `cp graphify-out/graph.json graphify-out/graph.json.bak; $PY merge_build.py` | Merges cached and new docs with the AST, drops test paths, clusters, runs a health check. It refuses to shrink `graph.json`. If the shrink is expected (deleted code, version bump), delete `graph.json` and rerun. |
| 5 label | labeling-kg-communities | Community ids renumber on every build, so relabel all; no `--missing-only`. `label` also re-clusters and rewrites `graph.json` and `graph.html` (same shrink guard) and leaves a dated backup folder in `graphify-out/`. |
| 6 export | exporting-kg-obsidian | |
| 7 finish | `rm -f graphify-out/.graphify_{detect,extract,ast,semantic,cached}.json graphify-out/.graphify_chunk_*.json graphify-out/.graphify_uncached.txt graphify-out/.chunks.json` | Keep `.graphify_analysis.json`, `.graphify_labels.json` and `graph.json.bak` until the vault checks pass. There is no manifest step; the manifest only serves `update`. |

## Version pinning

A newer graphify (`uv tool install … --force`) dedups nodes differently. The symptom is "new graph has N nodes but existing has N+101 … refusing to overwrite". Point `graphify-out/.graphify_python` at the uv tool python (`uv tool run --from graphifyy python -c "import sys;print(sys.executable)"`) and rerun steps 3–4. Never mix the system-python graphify with the CLI's.

## Common mistakes

- `graphify update`, `watch` or `extract` on this graph (see above).
- `detect()` on the repo root without the exclude list: 6+ min, and 665 MB of task bundles in the corpus.
- Gemini for doc extraction: 5 requests/min on the free tier.
- `ls` or `du` on `vault/` or `graphify-out/`: minutes on NTFS.
