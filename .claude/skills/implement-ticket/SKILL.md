---
name: implement-ticket
description: Playbook for implementing a GitHub issue in this repository from start to pull request, with the project subagents run at fixed steps. Use whenever asked to implement, start, continue or finish a ticket, an issue or an epic child, for example "implement #12" or "work on the next ticket".
argument-hint: "[issue number]"
---

# Implement a ticket

Use this playbook for every implementation ticket in this repository. `CLAUDE.md` holds the commands, the architecture boundaries, the Git workflow and the evidence rules; where this playbook and `CLAUDE.md` differ, `CLAUDE.md` wins.

The project subagents in `.claude/agents/` are part of the work. Delegate to them at the steps below without waiting to be asked. If a step names a role that is not installed, do that step yourself and say so in the pull request.

## Steps

1. **Read the ticket.** `gh issue view <number>` and the epic it belongs to. Check that every issue the ticket depends on is closed. The owner decisions are listed in the epic (#1): each has a default stated in its ticket and does not block the work. D1 (for #8) is settled conservatively in `docs/owner-decisions.md` entry 10: no installed browser, write the manual procedure and flag it in #8. If the ticket is blocked, stop and say what blocks it.
2. **Read the rules.** `CLAUDE.md`, then the architecture notes it links to.
3. **Orient and check the approach.** Delegate as the table "Before coding" says. Settle open design questions before writing code. For a ticket that changes the UI, start with the `ui-ux-pro-max` skill (`python .claude/skills/ui-ux-pro-max/scripts/search.py "<product type>" --design-system`) and read [docs/ui-quality.md](../../../docs/ui-quality.md).
4. **Branch** as the Git workflow in `CLAUDE.md` says. Never work on the default branch.
5. **Implement** inside the ticket's stated scope. Delegate the work to the implementing role that matches the files being changed (table "While coding"). Do not widen scope; note anything else you find as a follow-up.
6. **Test.** Add or change tests for every acceptance criterion and material edge case, then run the checks listed in `CLAUDE.md` locally. Record each command and its result; the gates below start only when they pass.
7. **Specialist review.** For a UI ticket, check every changed screen against the ten rules in `docs/ui-quality.md` and record the result. Run every role in the table "After coding" whose trigger matches the change. Finish the final diff before the gates: add one line for the change under `Unreleased` in `CHANGELOG.md`, and run the `unslop` skill over the user-facing copy and documentation you wrote, so the gates judge the final diff.
8. **Review gate, always.** Run Code Reviewer on the full diff. Fix every material finding, re-run the checks, and have the reviewer look again until no material finding is left.
9. **Acceptance gate, always.** Run Reality Checker with the ticket's acceptance criteria and the recorded local evidence. It checks that the documented checks were run and passed locally and that CI is configured to run them; it does not confirm a CI result, which only exists once the draft pull request is open. Do not open a pull request unless it passes. Reviewers have no shell: before calling either gate, write the diff and the recorded check output to `.claude/state/review/` in the ticket worktree (`git diff --stat origin/main...HEAD`, `git diff origin/main...HEAD`) and name those files in the request.
10. **Hand off.** Capture the evidence `CLAUDE.md` asks for. Run the `unslop` skill over the pull request text only (the changelog line, copy and documentation were finished before the gates). Push the branch and open the pull request as a draft (`gh pr create --draft`) only after both gates passed on the current diff (a `/next-ticket` run is the owner's request to push and open it), using `.github/pull_request_template.md`, naming the issue with `Closes #<n>`. Then wait for CI without polling: end the turn with "Draft pull request #N is waiting for CI" and read `gh pr checks <n>` once when woken. If it fails, fix, re-run the local checks and both gates, and push. Mark the pull request ready (`gh pr ready`) and comment on the issue with the CI run link only when CI is green and both gates passed on the current diff; you check CI, not Reality Checker. If the ticket is the last open sub-issue of a parent, the pull request also says `Closes #<parent>`. An acceptance step that needs a person (for example "by hand in a normal browser") is done as far as a scripted or headless run allows, with the evidence, and the rest is listed under "Owner checks" in the pull request. Never change agent configuration (`.claude/agents`, skills, hooks, `settings.json`) in a ticket, by shell command either. Never open or ready a pull request with a gate not run. Only the owner merges; never merge or release.

## Roles

### Before coding

| Role | Access | Delegate to it |
|---|---|---|
| Codebase Onboarding Engineer | read-only reviewer | At the start of a ticket in an unfamiliar area, to trace the relevant code paths before anything is changed |
| Software Architect | read-only reviewer | Before implementing a ticket that adds or changes a module boundary, data model, storage schema, public API or dependency, to check the approach against the architecture notes |

### While coding

| Role | Access | Delegate to it |
|---|---|---|
| Backend Architect | can edit | When a ticket changes server-side code, HTTP routes, validation, persistence or data migrations |
| Database Optimizer | read-only reviewer | When a ticket changes SQL, the schema, indexes or query paths |
| Frontend Developer | can edit | When a ticket changes browser-side code such as pages, components, client state, styling or keyboard interaction |

### After coding

| Role | Access | Delegate to it |
|---|---|---|
| Application Security Engineer | read-only reviewer | After a ticket touches input parsing, file upload or import, sanitization, origin and host checks, or any handling of untrusted data |
| Accessibility Auditor | read-only reviewer | After a ticket changes user-facing UI, keyboard handling, focus order or markup |
| API Tester | can edit | After a ticket adds or changes an HTTP endpoint, status code or request and response contract |

### Gates that run on every ticket

| Role | Access | Delegate to it |
|---|---|---|
| Code Reviewer | read-only reviewer | After implementing or changing code for a ticket, after the local checks pass, before a pull request is opened |
| Reality Checker | read-only reviewer | As the last step of every ticket, after Code Reviewer, to check each acceptance criterion against the local evidence that was actually produced, before the draft pull request is opened |

## Rules

- The session or role that wrote a change does not count as its reviewer.
- Read-only reviewers cannot run commands. Give them the diff, the acceptance criteria and the recorded command output.
- Where a role's general advice (frameworks, dependencies, cloud services) conflicts with `CLAUDE.md`, `CLAUDE.md` wins.
- In the pull request description, add a section "Agent roles run" listing each role that ran, what it was asked and its verdict, and any step you did yourself because a role was missing.
