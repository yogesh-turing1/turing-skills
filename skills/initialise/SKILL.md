---
name: initialise
description: Use at the start of a Turing/Harbor session in this workspace, after a context compaction, or whenever unsure what the current objectives, recent changes, or available skills are.
---

# Initialise

Run the loader, then read what it prints before doing anything else:

```bash
bash .claude/init.sh
```

It prints, in order: OBJECTIVES.md · last 3 CHANGELOG entries · every skill with its trigger · git state of `work/` · node 7 health and whether the VM tree matches local HEAD.

Then reply with a 3–5 line brief: current objective, what the last entry left as *Next*, and any drift (uncommitted files, VM tree behind, harbor7 unreachable). Do not start work in the same turn unless the user already asked for something.

If `harbor7 unreachable`: say so, keep going — local work does not need the VM.
