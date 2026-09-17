---
name: labeling-kg-communities
description: Use when graphify community names are placeholders (`Community N`) or bare node names (`BaseModel`, `app.js`, `.select`), when `graphify label` batches fail with 429 / "usage limit" / "package is required", or after any rebuild or update of the harbor KG.
---

# Labeling KG communities

**REQUIRED BACKGROUND:** harbor-kg. Run from `work/kg`. `PY="$(cat graphify-out/.graphify_python)"`.

Community names come from an LLM reading each cluster's members. ~2k communities = ~21 batches of 100.

## Backend choice

| Backend | Use when | Gotcha |
|---|---|---|
| `--backend claude-cli --model opus` | default — Claude Code subscription, no key, no quota | serial (concurrency forced to 1), ~15 min for 2k |
| `--backend claude --model claude-opus-5` | ANTHROPIC_API_KEY with spend headroom, passed as a process env var only | needs `uv tool install graphifyy --with anthropic --force`; HTTP 400 "workspace API usage limit" = console spend cap hit |
| `--backend gemini` | never for >5 batches | free tier = 5 req/min → 429; lower label quality |

```
graphify label . --backend claude-cli --model opus --batch-size 100
```
Always pass `--backend`. Without it graphify picks Gemini, because `GEMINI_API_KEY` is set. The log ends with `Done - N communities` even when batches failed, so check for `failed` lines rather than trusting the last line.

## A failed run silently overwrites good labels

After runs with failed batches, `.graphify_labels.json` has held the **top member node's own label** (`FigmaStrictBaseModel`, `app/models/__init__.py`) instead of `Community N`. This happened on every failed run with 0.9.58, so `--missing-only` finds nothing missing and the vault exports symbol names as titles. After any run with a `failed` line:

```
$PY relabel.py                      # resets fallback names → 'Community N'
graphify label . --missing-only --backend claude-cli --model opus
```
Never chain `export` after `label` with `&&` unless the log shows zero `failed` batches.

## Verify before export

```
$PY -c "import json;l=json.load(open('graphify-out/.graphify_labels.json',encoding='utf-8'));print(list(l.values())[:10], sum(v.startswith('Community ') for v in l.values()))"
```
Names should read like *Golden Trajectory Validation*, not like symbols. Repeated `Test Client Fixtures_N` on one-node communities is expected noise.
