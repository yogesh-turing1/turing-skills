---
name: exporting-kg-obsidian
description: Use when the Obsidian vault for the harbor KG is missing, stale after a rebuild or relabel, must be placed inside an existing vault (obsidianKB), or someone asks to open the knowledge graph in Obsidian.
---

# Exporting the KG to Obsidian

**REQUIRED BACKGROUND:** harbor-kg. Run in Git Bash from `work/kg` with `PY="$(cat graphify-out/.graphify_python)"`. Labels must be verified first (labeling-kg-communities).

```
graphify export obsidian --dir vault      # ~10 min, ~40k notes; run in background
```
`graph.html` needs no separate export, because `graphify label` rewrites it.

**The export is done and correct when:**
- the background task exited 0;
- `vault/.graphify_obsidian_manifest.json` is newer than `graphify-out/.graphify_labels.json`;
- the manifest's `_COMMUNITY_` count is within a few of the label count (2043 vs 2044 on the current build).

`$PY -c "import json;m=json.load(open('vault/.graphify_obsidian_manifest.json',encoding='utf-8'))['files'];print(sum(f.startswith('_COMMUNITY_') for f in m))"`

Notes from earlier exports that graphify owns are pruned automatically, so no stale duplicates are left.

Output: one note per node with `[[wikilinks]]`, one `_COMMUNITY_<name>.md` per community (entry points), `graph.canvas`, and `.graphify_obsidian_manifest.json` listing every file graphify owns. Re-export overwrites only manifest-listed files — user notes in the same folder survive.

Open: Obsidian → *Open folder as vault* → `C:\cpio_db\Turing\work\kg\vault`.

## Into an existing vault

`graphify export obsidian --dir C:\cpio_db\obsidianKB\Turing` writes beside the user's notes; the manifest protects them. A symlink `obsidianKB/Turing` → `work/kg/vault` also works with no second export.

## Common mistakes

- `ls` / `du` / `find` on `vault/`: 40k files on NTFS = minutes, and errors on files being renamed mid-export. Inspect `graphify-out/.graphify_labels.json` or `graph.json` instead.
- Exporting before labels are verified — the vault carries symbol names as community titles and must be re-exported.
- Committing `vault/` or `graphify-out/graph.json` (110 MB + 55 MB, regenerable) — both are in `kg/.gitignore`.
