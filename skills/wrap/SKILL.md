---
name: wrap
description: Use when the user says wrap up / log this / save progress, wants to shape the changelog entry or update objectives by hand, or when the last CHANGELOG entry is a mechanical `auto (…, no summary)` one that needs replacing. (Session end and compaction already auto-write an entry via close.sh.)
---

# Wrap — runs in the background

Dispatch ONE background `fork` subagent (Agent tool, `subagent_type: "fork"`, description `wrap session`) with the prompt below. Then reply with exactly one line — `wrap running in background; entry will follow.` — and carry on with whatever the user asks next. When the fork's completion notification arrives, relay its entry in ≤10 lines.

Fork prompt:

> You are wrapping this session. Work only in the workspace root. Do these steps in order, then report the changelog entry verbatim and the sync result.
>
> 1. Prepend one entry to `CHANGELOG.md` directly under the `# Changelog` line (newest first):
>    ```
>    ## YYYY-MM-DD HH:MM IST — <3–6 word title>
>    - Done: …
>    - Decided: …
>    - Next: …
>    ```
>    Facts from this session only, ≤8 bullets, one per line, IST timestamps. If the top entry is an `auto (…, no summary)` one for this same session, replace it.
> 2. If the user corrected a *behavior* this session and `FEEDBACK.md` has no row for it, apply the `feedback` skill's two steps (ledger row + policy edit) for each.
> 3. Update any objective in `OBJECTIVES.md` whose status changed, or add one the user stated.
> 4. `sh sync.sh`.
