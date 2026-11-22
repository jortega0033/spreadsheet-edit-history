---
name: next-ticket
description: Owner-started driver that takes one ticket of epic #1 from the queue to a ready pull request. Only the owner starts it, with /next-ticket.
argument-hint: "[issue number]"
disable-model-invocation: true
---

# Next ticket

Starting this skill is the owner's go signal for one run. It counts as the owner's request, for this run, to push the ticket branch and open the pull request. It handles one ticket and stops. It never merges and never starts another run by itself.

Rules that still apply: `CLAUDE.md` (commands, hard constraints, Git workflow, evidence), `docs/owner-decisions.md`, `docs/ui-quality.md`, and the permission rules in `.claude/settings.json`. If a rule blocks the ticket, stop and say so.

## Labels

`status:ready`, `status:blocked`, `status:in-progress`, `needs-decision`. The epic is #1. If a label does not exist yet, say so and carry on without it; do not create labels.

## Steps

1. **Refresh the queue.** `gh issue list --state open --limit 100` and read the dependency table in epic #1 ("Tickets in dependency order": #8, #2, #3, #4, #6, #5, #7, #9). A `status:blocked` ticket whose blockers are all closed becomes `status:ready` (`gh issue edit <n> --add-label status:ready --remove-label status:blocked`).
2. **Pick one ticket.** With an issue number argument, use that ticket (it must be open and not `status:in-progress`). Otherwise take the first `status:ready` ticket in the epic's dependency order that is not `status:in-progress` and not `needs-decision`. If none qualifies, report that and stop. Owner decisions are settled as `docs/owner-decisions.md` entry 10 says: D1 for #8 is settled conservatively (no installed browser; write the manual procedure and flag it in #8), so D1 does not block #8.
3. **Claim it.** `gh issue edit <n> --add-label status:in-progress` and `--remove-label status:ready`.
4. **Worktree and branch.** `git fetch origin`, then `git worktree add ../spreadsheet-edit-history-<n> -b <type>/<n>-<short-slug> origin/main`, as the Git workflow in `CLAUDE.md` says. Work only in that worktree. Never work on `main`.
5. **Implement.** Follow `.claude/skills/implement-ticket/SKILL.md` step by step, including the role delegation, the two gates, `docs/ui-quality.md` for UI tickets, `unslop` for copy, a `CHANGELOG.md` line and the pull request template.
6. **Push and open the pull request.** Only after the local checks passed and the Code Reviewer gate and then the Reality Checker gate have passed on the current diff (the gate hook blocks `gh pr create` and `gh pr ready` otherwise; Reality Checker does not judge CI): `git push -u origin <branch>`, then `gh pr create --draft` with `.github/pull_request_template.md` filled in and `Closes #<n>`. Never push to `main`. Never force-push. Do not switch the hook off.
7. **CI.** Wait for the CI checks with `gh pr checks`. If a check fails, fix it, re-run the local checks and both gates on the new diff, push and look again. Mark the pull request ready (`gh pr ready`) only when CI is green and both gates passed on the current diff, then comment on the issue with the CI run link. You check CI; Reality Checker does not.
8. **Report.** Comment on the issue with the pull request link, the evidence summary and the roles that ran. Leave the label `status:in-progress` for the owner to change on merge.
9. **Stop.** Do not merge, release, close the issue or start the next ticket. Only the owner merges.

If you cannot finish (blocked, a gate keeps failing, a decision is needed), comment on the issue with what is done and what blocks it, then stop. Do not leave a pull request open and ready with a gate or CI check failing.
