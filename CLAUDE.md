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
- There is no lint, format, type-check or build command, and no CI workflow. Do not claim that any of these passed.
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
- Cell text is data. Nothing a user types, imports or merges is ever passed to `eval`, `exec`, `compile` or a dynamic import. Formulas are evaluated only by the parser in `sheet_history/sheet.py`.
- Cell text and titles are stored exactly as given: no trimming, no Unicode normalization.
- Sample and fixture data are invented. Do not commit real user data or a data directory.

## Sources of truth

| Question | Where to look |
|---|---|
| What the product is, limits, the HTTP API, fixtures, the acceptance matrix, the future milestones P1 to P6 and the open choices | [docs/PRD.md](docs/PRD.md) |
| How the code is layered, the traced save workflow, invariants, what is implemented, planned or unverified, and where the PRD and the code differ | [docs/architecture.md](docs/architecture.md) |
| What to build next and in which order | Epic issue #1 on GitHub and its sub-issues, in the dependency order given in the epic body |
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

Observed state at preparation time: `main` is the default branch with one commit, it is not protected, there is no CI and there are no contribution rules in the repository. The rules below are the working defaults until the owner replaces them.

- Never commit to `main` directly. Branch from the tip of `origin/main`, one branch per ticket, named `<type>/<issue-number>-<short-slug>` (for example `feat/2-formula-evaluator`).
- Keep commits small and use the existing subject style (`feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `chore: ...`).
- Open a draft pull request that names the issue (`Part of epic #1`, `Closes #N`). The owner reviews and merges. Do not merge, force-push or rewrite published history.
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
7. `git status --short` showing no stray files, and confirmation that every server and browser started for the check was stopped.

State what was not verified. A README or PRD claim that you did not reproduce is a claim, not evidence.

## Project agents

`.claude/agents/` holds project-local roles copied from Agency Agents at a pinned revision, plus the Loop verifier. Source paths, licence, the name collision with a user-level install, and how to check that they load are in [.claude/agency-agents/README.md](.claude/agency-agents/README.md).

- Read-only reviewers (`tools: Read, Grep, Glob`): Software Architect, Code Reviewer, Codebase Onboarding Engineer, Database Optimizer, Accessibility Auditor, Reality Checker, Application Security Engineer.
- Implementing roles: Backend Architect (`sheet_history/*.py`), Frontend Developer (`sheet_history/static/`), API Tester (`tests/`).
- The upstream role texts were written for larger stacks. Where a role text suggests a framework, a cloud service, a scanner, another database or a new dependency, the constraints in this file win.

## Loop

Loop Engineering is set up with the `issue-triage` pattern at L1: report-only and started by hand. It has no scheduler and makes no GitHub writes. See [LOOP.md](LOOP.md) and [loop-constraints.md](loop-constraints.md).
