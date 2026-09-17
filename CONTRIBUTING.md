# Adding a skill

1. Fork the repo, create a branch.
2. Add `skills/<your-skill-name>/SKILL.md` (kebab-case folder name) with frontmatter:
   ```markdown
   ---
   name: your-skill-name
   description: Use when <trigger> — one line, it is what the agent matches on.
   ---
   ```
   Optional: `references/`, `scripts/`, `agents/openai.yaml` next to it.
3. Add one row for it to the **Skills** table in `README.md`.
4. Open a PR. Improvements to existing skills are welcome too.

## Never commit

Keys, passwords, tokens, VM/host IPs, private bucket names, internal URLs, or colleagues' names. Use placeholders like `<VM_IP>`, `<TASK_BUCKET>`, `<QC_PLATFORM_URL>`. PRs containing these get closed.
