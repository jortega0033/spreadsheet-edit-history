# CLAUDE.md

Spreadsheet with Edit History is a local, offline, single-person spreadsheet workbench: an 8×6 grid of text, numbers and one formula form, saved in SQLite and served to one browser on the loopback interface. The baseline (milestone M1) is built. The epic that adds a general formula evaluator, an append-only revision log, what-if branches, cell-wise merges, CSV exchange and a larger grid (issue #1) is not.

## Commands

Both commands were run on 2026-11-22 on Windows 11 with Python 3.13.14, from the repository root.

| Purpose | Command | Observed |
|---|---|---|
| Test | `python -m unittest discover -s tests -t .` | `Ran 94 tests`, `OK`, about 27 seconds |
| Run | `python -m sheet_history --data-dir ./data --port 8765` | Observed with a scratch data directory and `--port 8793`: it printed `Serving on http://127.0.0.1:8793 (Ctrl-C to stop)`, and `GET /api/v1/health` returned 200. The command as shown, with `./data` and port 8765, is the README form and was not run in that exact form. Open the URL it prints. |

- There is no install step. Python 3.12 or newer is the only requirement. On Windows the interpreter is `python`; on Linux use `python3`.
- Keep `-t .` in the test command: the test modules import `tests.support`.
- `--data-dir` is required. `--port` defaults to 8765; the tests use port 0 through `make_server`.
- There is no lint, format, type-check or build command. CI runs the test command and the hook self-test (see Delivery workflow). Do not claim that lint, format, type-check or build passed.
- The Linux and Python 3.12 runs reported in the README were not repeated during preparation.
- Stop every server you start, then check that its port has no listener. On Windows, `kill` from Git Bash can leave the Python process running; stop it by PID (`taskkill //PID <pid> //F`). Stop only processes you started.
- `data/`, `*.sqlite*` and `*.db` are ignored by Git. Use a scratch `--data-dir` for experiments.

## Hard constraints

These come from [docs/PRD.md](docs/PRD.md) sections 3, 4, 5, 10 and 11. Several are enforced by tests.

- Python standard library only, for the application and its tests. No pip or npm dependency, no package manifest, no build step.
- Any package or tool that future work needs must be approved by the owner before it is staged (PRD section 11). A tool that happens to be installed on your machine does not count as approved.
- No external request of any kind at run time: no CDN, web font, remote URL or telemetry.
- The server binds `127.0.0.1` only. Every new route goes through `Handler._handle` in `sheet_history/server.py`, so that the Host and Origin checks, the body cap and the response headers apply to it.
- The Content-Security-Policy forbids inline script and inline style. UI code stays in `sheet_history/static/`. A new static file must be added to `STATIC_FILES` in `sheet_history/server.py`, or it is not served.
- Write user text to the page with `textContent` or `.value`. Do not build HTML from strings; a test rejects `innerHTML` in `app.js`.
- Cell text is data. Nothing a user types, imports or merges is ever passed to `eval`, `exec`, `compile` or a dynamic import. Formulas are evaluated only by the formula code of the grid-model layer: today that is one fixed pattern and `compute` in `sheet_history/sheet.py` (there is no parser yet); issue #2 replaces it with a hand-written parser in `sheet.py` or in a pure module next to it.
- Cell text and titles are stored exactly as given: no trimming, no Unicode normalization.
- Sample and fixture data are invented. Do not commit real user data or a data directory.

## Sources of truth

| Question | Where to look |
|---|---|
| What the product is, limits, the HTTP API, fixtures, the acceptance matrix, the future milestones P1 to P6 and the open choices | [docs/PRD.md](docs/PRD.md) |
| How the code is layered, the traced save workflow, invariants, what is implemented, planned or unverified, and where the PRD and the code differ | [docs/architecture.md](docs/architecture.md) |
| What to build next and in which order | Epic issue #1 on GitHub and its eight sub-issues, in the dependency order given in the epic body: #8 (browser checks), #2 (formulas), #3 (revision log), #4 (branches), #6 (CSV), #5 (merge), #7 (multiline editor and large grid), #9 (epic acceptance run). #8, #2 and #3 depend on no other ticket and can start in parallel; owner decision D1 for #8 is settled conservatively (no installed browser; write the manual procedure and flag it in #8; see `docs/owner-decisions.md` entry 10), so #8 is not blocked by it. |
| What was reported to work at baseline, and on which platforms | [README.md](README.md), "Baseline verification" |

Code and tests show what the product does. The PRD says what it should do. When they disagree, do not pick one silently: add a row to the drift table in `docs/architecture.md` and raise it in the ticket.

`.prep/` is ignored by Git and holds notes from an earlier build session on the owner's machine. It is not part of the repository and is not a source of truth, although PRD section 11 mentions a file in it.

## Architecture boundaries

Details and source citations are in [docs/architecture.md](docs/architecture.md). The rules that a change must keep:

- `sheet_history/sheet.py` is pure: no I/O, no SQLite, no HTTP. Validation, the canonical grid and formula evaluation live here. New pure logic (parser, dependency evaluation, delta and replay, three-way merge, CSV reading and writing) belongs in pure modules next to it, each testable without a server.
- `sheet_history/storage.py` owns SQLite. Each operation opens its own connection. Each write is one `BEGIN IMMEDIATE` transaction that checks the stored revision first. Validation runs before the transaction opens. A schema change is a new, numbered migration; a database with a newer `user_version` is refused.
- `sheet_history/server.py` owns HTTP: guards, routing, the error envelope `{"error":{"code","message"}}` and static files. It calls validation and storage; it holds no state other than the storage handle and the allowed Host values.
- `sheet_history/__main__.py` owns arguments and the exit codes (2 for a bad data directory or a newer schema, 1 when the port cannot be bound).
- `sheet_history/static/` is the whole UI. The server owns all saved state; the browser owns only the unsaved edits.
- A stale save is never merged automatically. The client always sends the revision it started from, and a mismatch is a 409 that carries the current sheet.
- The canonical grid bytes (`sheet.dumps_grid`) are the unit of comparison for anything that claims "identical": replay, branches, merges and CSV round trips.
- Request bodies have exact key sets. Add a route or a query parameter instead of an optional key on an existing body; a breaking change needs `/api/v2` (PRD section 9).

## Git workflow

The rules below are the working defaults until the owner replaces them. CI exists now (see "Delivery workflow"); branch protection on `main` is set by the owner in GitHub settings.

- Never commit to `main` directly. Branch from the tip of `origin/main`, one branch per ticket, named `<type>/<issue-number>-<short-slug>` (for example `feat/2-formula-evaluator`).
- Keep commits small and use the existing subject style (`feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `chore: ...`).
- Open a draft pull request that names the issue (`Part of epic #1`, `Closes #N`) as "Delivery workflow" says. The owner reviews and merges. Do not merge, force-push or rewrite published history.
- Migrations are numbered in merge order. If another schema change was merged first, rebase and renumber yours before review.
- Do not commit a data directory, a SQLite file, `__pycache__`, an exported CSV file or a browser report folder.
- A change to behaviour updates the matching PRD section, the fixtures in PRD section 6, the acceptance matrix in PRD section 12 and `docs/architecture.md` in the same pull request.

## Evidence before claiming a ticket done

Report only what you ran and saw. For each ticket, capture:

1. The full-suite command and its last lines: `python -m unittest discover -s tests -t .`, with the test count, `OK` and the number of skipped tests with their reasons. The count must not go down. If a ticket has to change an existing test, list each changed test and the PRD rule that changed with it.
2. The names of the new tests and the acceptance criteria of the issue that each one covers.
3. For API changes: one request and response for the main case and one for a rejected case, taken from a real server on a scratch data directory, including the status code.
4. For UI changes: the browser and its version, the steps performed, and what the page showed (status text, alert text, focused element, cell values). Say plainly if no browser run was done. Labels, keyboard operation and the status and alert regions are part of the acceptance criteria (PRD sections 5.4 and 7), not polish.
5. For schema changes: a test or a run that opens a database created by the previous schema version with data in it and shows the data intact, including the revision numbers.
6. For anything that claims byte-exact behaviour (replay, branch isolation, merge, CSV): the fixture, the seed if there is one, and the comparison that was made on canonical grid bytes.
7. For a pull request: the CI result from `gh pr checks`, green on the current commit. The driver checks this on the draft pull request after both gates passed; the gates work from the local evidence above and do not confirm a CI result. A pull request is not marked ready, and a ticket is not done, until CI is green.
8. `git status --short` showing no stray files, and confirmation that every server and browser started for the check was stopped.

State what was not verified. A README or PRD claim that you did not reproduce is a claim, not evidence.

## Project agents and ticket work

`.claude/agents/` holds ten project-local roles copied from Agency Agents at a pinned revision. Each role file starts with an "In this repository" section written for this project: the constraints that bind the role, the files it owns or reviews, its commands or the evidence it must be given, its checklist, the parts of the upstream text that do not apply here, and what it hands back. That section and this file override the upstream text below it. Source paths, licence, local changes, the name collision with a user-level install and the loading check are in [.claude/agency-agents/README.md](.claude/agency-agents/README.md). The same folder holds `loop-verifier.md`, which belongs to the Loop and is not part of ticket work.

When asked to implement, continue or finish a GitHub issue, follow the playbook in [`.claude/skills/implement-ticket/SKILL.md`](.claude/skills/implement-ticket/SKILL.md); it has the steps and the exact trigger of each role. Claude Code loads it on its own for ticket work, and `/implement-ticket <issue number>` starts it by hand. Delegate to the roles without waiting to be asked: each role's `description` ends with a "Use proactively ..." sentence, which is what makes Claude Code delegate.

- **Before coding:** Codebase Onboarding Engineer when the ticket touches an unfamiliar area (trace the code paths), and Software Architect when it adds or changes a module boundary, data model, storage schema, public API or dependency (check the approach against [docs/architecture.md](docs/architecture.md)). Both are read-only.
- **While coding:** Backend Architect for `sheet_history/*.py` and Frontend Developer for `sheet_history/static/`, which can edit; Database Optimizer, read-only, when SQL, the schema or a migration changes.
- **After coding:** Application Security Engineer and Accessibility Auditor, read-only, and API Tester, which writes the HTTP-level tests in `tests/`, each when its trigger matches the change.
- **Gates on every ticket, whatever its size:** Code Reviewer on the full diff (the review gate), then Reality Checker on the acceptance criteria and the evidence (the acceptance gate). Both run on the full diff and the recorded local evidence, after the local checks pass and before the draft pull request is opened. A ticket is not done until both pass and CI is green on the draft pull request.
- The seven read-only roles have `tools: Read, Grep, Glob` and cannot run commands. Give them the diff, the acceptance criteria and the recorded command output.
- The session or role that wrote a change does not count as its reviewer.
- In the pull request description, list the roles that ran and their verdicts under "Agent roles run".

## Delivery workflow

How a ticket gets from the queue to the owner. Each piece has one home; this part only links them.

- **Start and driver.** Ticket work starts only when the owner starts it, with `/next-ticket` ([`.claude/skills/next-ticket/SKILL.md`](.claude/skills/next-ticket/SKILL.md)); it runs one ticket and there is no scheduler. The steps and roles are in the playbook [`.claude/skills/implement-ticket/SKILL.md`](.claude/skills/implement-ticket/SKILL.md). Push the ticket branch and open the pull request only when the owner asked for it in the current session; a `/next-ticket` run counts as that request, for that run.
- **Review gate hook.** [`.claude/hooks/role_gate.py`](.claude/hooks/role_gate.py) blocks `gh pr create` and `gh pr ready` until Code Reviewer and Reality Checker have run after the last code edit, so a pull request is never opened or marked ready with a gate not run. `ROLE_GATE=off` in the environment Claude Code is started from switches it off for that session; agents never do that.
- **Permissions.** [`.claude/settings.json`](.claude/settings.json): documented commands are allowed; force pushes, pushes to `main`, merges, releases and reads of `.env` are denied; edits to `.github/`, the agent configuration paths under `.claude/` (agents, skills, hooks, `settings.json`, agency-agents), `CLAUDE.md`, `AGENTS.md` and the Loop files ask first.
- **CI.** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the test command and the hook self-test on Linux and Windows, Python 3.12 and 3.13. The order is: local checks, Code Reviewer, Reality Checker, `gh pr create --draft`, CI on the draft, and `gh pr ready` only when every job is green on the current commit. If CI fails, fix, re-run the local checks and both gates, and push.
- **Pull request.** Use [`.github/pull_request_template.md`](.github/pull_request_template.md); tickets use [`.github/ISSUE_TEMPLATE/implementation-ticket.md`](.github/ISSUE_TEMPLATE/implementation-ticket.md).
- **Labels.** `status:ready`, `status:blocked`, `status:in-progress`, `needs-decision`; epic #1.
- **Changelog.** Every ticket pull request adds one line under `Unreleased` in [CHANGELOG.md](CHANGELOG.md).
- **UI and copy.** [docs/ui-quality.md](docs/ui-quality.md) lists ten binding UI rules; UI tickets start with the `ui-ux-pro-max` skill, and copy goes through `unslop`.
- **Decisions.** [docs/owner-decisions.md](docs/owner-decisions.md) records what the owner decided and where it is implemented.
- **Merging and releasing.** Only the owner merges and releases; see [SECURITY.md](SECURITY.md) and [docs/RELEASING.md](docs/RELEASING.md).

## Loop

Loop Engineering is set up with the `issue-triage` pattern at L1: report-only and started by hand. It has no scheduler and makes no GitHub writes. See [LOOP.md](LOOP.md) and [loop-constraints.md](loop-constraints.md).
