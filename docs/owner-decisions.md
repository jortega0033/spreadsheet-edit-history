# Owner decisions

Dated record of the decisions the owner made for this repository, so the rules do not depend on anyone's memory of a conversation. Changing any entry needs the owner. An agent that finds a decision blocking a ticket stops and says so.

| # | Date | Decision | Implemented in |
|---|---|---|---|
| 1 | 2026-11-22 | The instructions, tooling and playbook live on the default branch (`main`). | `CLAUDE.md`, `.claude/`, `docs/` |
| 2 | 2026-11-22 | Persona agents run automatically during ticket work and carry instructions tailored to this project. | `.claude/agents/`, `.claude/agency-agents/README.md`, `.claude/skills/implement-ticket/SKILL.md` |
| 3 | 2026-11-22 | Every open ticket is about app implementation; tooling is installed, not ticketed. | `CLAUDE.md` "Delivery workflow", `.github/ISSUE_TEMPLATE/implementation-ticket.md` |
| 4 | 2026-11-22 | Agents may take a ticket up to a ready pull request. Only the owner merges and releases. | `CLAUDE.md` "Delivery workflow", `.claude/skills/implement-ticket/SKILL.md`, `.claude/skills/next-ticket/SKILL.md`, `docs/RELEASING.md`, `.claude/settings.json` (deny rules) |
| 5 | 2026-11-22 | No scheduler. Ticket work starts only on the owner's go signal (`/next-ticket`), because the repository is used to train AI models. | `.claude/skills/next-ticket/SKILL.md` (`disable-model-invocation: true`), `LOOP.md` |
| 6 | 2026-11-22 | A review gate hook blocks opening or readying a pull request until the gate roles have run after the last code edit. | `.claude/hooks/role_gate.py`, `.claude/settings.json` (`hooks`), `.gitignore` |
| 7 | 2026-11-22 | Loop Engineering stays at L1, report-only and unscheduled. | `LOOP.md`, `loop-constraints.md` |
| 8 | 2026-11-22 | Continuous integration runs on Linux and Windows; the default branch requires a pull request and green checks. | `.github/workflows/ci.yml`; branch protection is set by the owner in GitHub settings |
| 9 | 2026-11-22 | Permission rules: documented commands are allowed; force pushes, pushes to the default branch, merges, releases and reads of secrets are denied; edits to CI, agent configuration and Loop files ask first. | `.claude/settings.json` |
| 10 | 2026-11-22 | Open decisions on tickets are settled with the ticket's stated default; where a ticket states none, the conservative option is taken and flagged in the issue. Listed below. | Epic #1 "Owner decisions" and the tickets named below |
| 11 | 2026-11-22 | Rust is verified in CI only. Not applicable: this repository has no Rust. | not applicable |
| 12 | 2026-11-22 | The ten UI rules in `docs/ui-quality.md` are binding, and the `ui-ux-pro-max` and `unslop` skills are installed in the repository and used for UI work and for copy. | `docs/ui-quality.md`, `.claude/skills/ui-ux-pro-max/`, `.claude/skills/unslop/`, `.claude/skills/implement-ticket/SKILL.md` |
| 13 | 2026-11-23 | Visual system: Pipenzo Flow look tokens (docs/design-tokens.md). SDLC kit version: jortega0033/sdlc-kit v1.0.0. | `docs/design-tokens.md`, `sheet_history/static/tokens.css` |
| 14 | 2026-11-23 | Colour rules for the Pipenzo tokens, four items, each with its source. D1 Current selection: the yellow accent is used for the primary action, the current-step marker and the current selection (UI rule 8). Decided by the owner on 2026-11-23. How (recommended by the orchestrator, adopted under the owner's delegation of the same day): a selection uses a solid --primary fill with --on-primary text (not only a yellow border, which has about 1.5:1 against white on light), plus a second sign that is not colour (weight, icon or text) and the existing aria attribute. Never a tint with a same-hue border and never a thick one-sided border. D2 Focus ring: --focus is a focus indicator, exempt from the accent limit, including where it is yellow in dark. A ticket that says the focus style stays unchanged means the rule on main after the token pull request. Recommended by the orchestrator, adopted under the owner's delegation of 2026-11-23. D3 Themes: contrast and no-colour-alone checks cover both the light and the dark block of tokens.css. Recommended by the orchestrator, adopted under the owner's delegation of 2026-11-23. D4 Linking: a ticket that creates a page or its static allowlist links tokens.css before any other stylesheet and serves it (allowlist and its test). Recommended by the orchestrator, adopted under the owner's delegation of 2026-11-23. | `docs/design-tokens.md` (D1 to D3), `docs/ui-quality.md` (rule 8 reading); D4 applies to tickets that create a page or its static allowlist |

## Entry 10: open decisions settled by the ticket default

From the owner-decision table in epic #1.

| Decision | Ticket | Settled by |
|---|---|---|
| D1 Whether an installed browser may be an optional test tool | #8 | The ticket states no default answer, only what happens if declined. Conservative option taken: do not use an installed browser; write the manual procedure instead. Flag in issue. |
| D2 Formula rules the PRD does not state | #2 | The rules listed in #2 ("Decisions fixed by this ticket") |
| D3 Schema 2, no pre-migration revisions, no downgrade | #3 | As listed in #3 |
| D4 History in a side panel, `main` reserved, at most 20 branches | #4 | As listed in #4 |
| D5 Common-ancestor rule; an empty merge still adds a revision | #5 | As listed in #5 |
| D6 CSV export of formula text, used range, byte order mark, safe mode | #6 | As listed in #6 |
| D7 Minimum 8x6 size, changed-cell saves, multiline editor, 262144-byte CSV cap | #7 | As listed in #7 |
