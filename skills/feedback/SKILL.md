---
name: feedback
description: Use whenever the user corrects how Claude worked (not a fact), states a preference ("always…", "never…", "not like that", "I prefer…"), rates an output, or says feedback / learn this — including when the correction is implicit in a terse or annoyed reply.
---

# Feedback loop (ledger → policy) — runs in the background

Corrections are training signal. Log the experience, then change the policy that produced it.

**Facts are not feedback.** "That IP is wrong" → fix the fact, no ledger row. "Stop guessing IPs, check the sheet" → ledger row.

First, apply the rule to *this* conversation immediately (behave correctly from the next message). Then dispatch ONE background `fork` subagent (Agent tool, `subagent_type: "fork"`, description `log feedback`) with the prompt below, reply with one line — `logged; policy update running in background.` — and continue.

Fork prompt:

> Record one piece of feedback from this session. Work only in the workspace root.
>
> 1. **Ledger.** Append to `FEEDBACK.md`:
>    ```
>    | YYYY-MM-DD | <what Claude did / user said, ≤15 words> | <rule, imperative, one line> | <target> |
>    ```
>    Target is exactly one of: `CLAUDE.md#work-style` · `skills/<name>` · `.claude/skills/<name>`.
> 2. **Policy.** Edit the target so the rule is in force:
>    - `CLAUDE.md#work-style` — one bullet. Keep the list ≤ 15; when the new rule overlaps an old one, replace the old one.
>    - a skill — change the step that produced the behavior; no "notes" section.
> 3. `sh sync.sh`.
> 4. Report the ledger row and the diff of the target. Nothing else.
