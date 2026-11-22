# AGENTS.md

The full repository instructions are in [CLAUDE.md](CLAUDE.md). This file repeats only what an agent needs before it reads that.

## Test commands

```
python -m unittest discover -s tests -t .
```

Use `python3` on Linux. Python 3.12 or newer, standard library only. There is no lint step, no build step and no package manifest. Do not add pip or npm dependencies.

## Run

```
python -m sheet_history --data-dir ./data --port 8765
```

## Ticket work

To implement a GitHub issue, follow the steps in [`.claude/skills/implement-ticket/SKILL.md`](.claude/skills/implement-ticket/SKILL.md) and the section "Project agents and ticket work" in [CLAUDE.md](CLAUDE.md). The role files in `.claude/agents/` each start with an "In this repository" section that says what the role checks here. Every ticket gets a code review and an acceptance check against recorded evidence before it is called done.

## Loop conventions

- The loop runs at L1: report-only, started by hand. It proposes; it does not label, comment, close, edit source, push or merge.
- No scheduler and no loop workflow is installed (the pull request CI workflow `.github/workflows/ci.yml` exists and runs the tests and the hook self-test). Do not add one without the owner's approval.
- See [LOOP.md](LOOP.md) for the manual command and the human gates.
