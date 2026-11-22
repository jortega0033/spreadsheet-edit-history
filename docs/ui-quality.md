# UI quality rules

Binding for every change to `sheet_history/static/` and to user-facing text. Rules 1 and 2 were stated by the owner; rules 3 to 10 were proposed and approved by the owner on 2026-11-22 and have the same standing. See [owner-decisions.md](owner-decisions.md), entry 12.

1. No thick accent border on one side of a card, callout, alert, list item or quote (for example `border-left: 4px solid <accent>`). Use spacing, type weight, an icon or a full hairline border instead.
2. No soft tinted background with a thin border of the same hue as the default way to mark a status, tag, callout or card. One neutral surface and one clear signal (text, icon or a solid chip) is enough.
3. No gradient text and no purple-to-blue gradient as a default accent.
4. No blur or glass panels, and no drop shadow plus large radius on every card.
5. No emoji used as icons or bullets, and no sparkle marks.
6. No pill or badge on things that are not states. No all-caps, letter-spaced micro labels as section decoration.
7. No centred hero with a slogan in an application screen. Screens open on the user's task.
8. One accent colour, used for the primary action and the current selection. Status colours only for status.
9. Dense, aligned layouts on a consistent spacing scale. No card grid where a table or a list is the right form.
10. User-facing copy is plain and specific: no filler, no exclamation marks, and the same word for the same thing everywhere.

## How the rules are applied

- A UI ticket starts with the `ui-ux-pro-max` skill (`.claude/skills/ui-ux-pro-max/`): search the design system for the product type before changing a screen.
- A UI ticket ends with a check of every changed screen against the ten rules above. The pull request lists the result under Evidence.
- User-facing copy, documentation and pull request text go through the `unslop` skill (`.claude/skills/unslop/`) before the pull request is opened.
- Frontend Developer, Accessibility Auditor and Code Reviewer carry this file in their checklists. The Code Reviewer gate runs on every ticket, so a breach is a review finding.
- Enforcement is by that review gate, not by a script. Rule 1 can be linted; rule 2 cannot be detected reliably from CSS.
- This repository's UI also has hard limits that these rules never override: no inline style or script, no external request, system fonts, visible focus, contrast of at least 4.5:1 (see [../CLAUDE.md](../CLAUDE.md) and PRD section 7).
- Existing breaches are tracked in one implementation ticket, not fixed ad hoc.
