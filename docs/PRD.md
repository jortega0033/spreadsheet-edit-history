# Spreadsheet with Edit History — PRD

Status legend: **[Implemented baseline]** = implemented in M1 (see [baseline verification](../README.md#baseline-verification)); **[Future]** = specified only, not built.

## 1. Intended user and workflow
A single person working offline on a small model who changes assumptions (rates, quantities, headcounts) and needs to keep a record of how the working numbers got there.

Workflow: open the local page → create or pick a sheet from the project list → type inputs and the occasional formula → Save explicitly → later, change an assumption, see a stale-save conflict if another tab saved first, and never lose typed text. Future milestones add a replayable history, what-if branches, merges and CSV exchange.

## 2. Milestones
| Milestone | Status | Summary |
|---|---|---|
| M1 | [Implemented baseline] | 8×6 grid, text/number inputs, one pure `=A1+B1` formula, SQLite persistence, explicit Save, Sheet title, New sheet, project list, stale-save conflicts |
| SH-1 / backlog P1 | [Future] | Dependency evaluator and formula parser |
| SH-2 / P2 | [Future] | Append-only revisions, replay, checkpoints |
| SH-3 / P3 | [Future] | Branch from a past revision, named what-if view |
| SH-4 / P4 | [Future] | Cell-wise three-way merge |
| SH-5 / P5, P6 | [Future] | CSV import/export (P5); multiline editor and large-grid keyboard check (P6) |

## 3. Scope boundaries
In: one local user, one browser, one process, loopback only, offline.
Out: sign-in, multi-user, remote sync, hosting, paid services, external media, model integration, charts, cell styling, multi-sheet formulas, undo stack, real user data.

## 4. System stack
Python 3.12 standard library only (`http.server.ThreadingHTTPServer`, `sqlite3`, `decimal`, `json`, `re`, `unittest`); static HTML/CSS/native JS served from the package; no build step, no external packages. Entry: `python -m sheet_history --data-dir <path> --port <port>` (`python3` on Linux). Binds `127.0.0.1` only. Data in `<data-dir>/sheets.sqlite`.

## 5. Contracts [Implemented baseline]
Authoritative engineering detail lives in the implementation; the stable surface is:

### 5.1 Grid and cell rules
- 8 rows × 6 columns, ids `A1`…`F8`. Cell input 0–200 Unicode code points, stored exactly as typed (UTF-8, no trim or normalization). Control characters and lone surrogates are rejected.
- Number: `^-?[0-9]+(\.[0-9]+)?$`. Any other text is literal. A leading `=`, `+`, `-` or `@` never executes anything.
- Formula: only `=<cell>+<cell>` (e.g. `=A1+B1`, no spaces), matched by regex and evaluated with `Decimal`; no `eval`. Empty operand = 0; text operand → `#VALUE!`; operand that is itself a formula → `#NESTED`. Any other `=…` text is literal and has no computed value.
- Canonical grid: JSON object of non-empty cells only, keys in row-major order, `ensure_ascii=False`, compact separators.

### 5.2 HTTP API
Errors are `{"error":{"code","message"}}`.

| Request | Success | Errors |
|---|---|---|
| `GET /` | HTML page | |
| `GET /static/app.css`, `/static/app.js` | assets | other paths 404 |
| `GET /api/v1/health` | 200 `{"status":"ok","schema":1}` | |
| `GET /api/v1/sheets` | 200 `{"sheets":[{id,title,revision,updated_at}]}` | |
| `POST /api/v1/sheets` `{"title"}` | 201 sheet | 400, 422 `limit_reached` (50 sheets) |
| `GET /api/v1/sheets/{id}` | 200 sheet | 404 |
| `PUT /api/v1/sheets/{id}` `{"base_revision","title","cells"}` | 200 sheet, revision+1 | 400, 404, 409 `conflict` (body includes `current`) |

Other codes: 403 `forbidden_origin` (bad Host, or foreign Origin on mutation), 405, 413 (body > 65536 bytes), 415 (mutation not `application/json`), 500 generic. No CORS headers are sent. Sheet object: `{id,title,revision,rows:8,cols:6,cells,computed,updated_at}`.

### 5.3 Schema
`PRAGMA user_version = 1`; table `sheets(id INTEGER PRIMARY KEY, title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 80), grid TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=1), created_at, updated_at)`. Updates use `BEGIN IMMEDIATE` and `UPDATE … WHERE id=? AND revision=?`; zero rows changed means conflict. A database with a newer `user_version` is refused.

### 5.4 UI contract
Labeled controls: Sheet title, Save, New sheet, Load sample (A1=3, B1=4, C1==A1+B1, local until saved), project list (current item `aria-current`), status region (`role=status`), conflict region (`role=alert`) with "Load server version" and "Keep my edits and retry". Grid is a real `<table>` with caption, column headers A–F, row headers 1–8; each cell is a text input whose accessible name is exactly its id (`A1`…). Formula cells also show an `<output>` with the result. Arrow/Enter navigation, Ctrl/Cmd+S saves, unsaved-change warning on unload. All user text is written via `textContent`/`.value`.

### 5.5 Algorithm: stale-save handling
Client sends `base_revision`. On 409 the client keeps all local text, shows the server revision, and offers load-server or retry-on-top; nothing is merged automatically.

## 6. Deterministic fixtures
| Fixture | Input | Expected |
|---|---|---|
| F1 | A1=`3`, B1=`4`, C1=`=A1+B1` | C1 computed `7`; same after restart |
| F2 | A1=`1.5`, B1=`2.5`, C1=`=A1+B1` | `4` |
| F3 | A1=`x`, C1=`=A1+B1` | `#VALUE!` |
| F4 | C1=`=A1+B1`, A1=`=B1+B1` | C1 `#NESTED` |
| F5 | A1=`=cmd()`, B1=`@x`, C1=`+1`, D1=`-1` | stored verbatim as literal text, no computed entries |
| F6 | A1=`héllo ✓ 日本` | returned byte-identical |
| F7 | stale PUT with `base_revision` 1 after revision 2 | 409, body `current.revision`=2 |

## 7. Responsiveness and accessibility
At 800×600 and 360 px wide there is no body horizontal overflow (the grid wrapper may scroll internally). System fonts, visible `:focus-visible`, text contrast ≥ 4.5:1, every input has an associated label or accessible name, status and conflict messages are announced.

## 8. Errors, retry, restart, concurrency
- Network failure: edits stay in the grid, message “Could not reach the server…”, Save can be pressed again.
- Validation errors from the API are shown verbatim in the status region.
- Restart: data is read from SQLite on start; the browser reopens the last sheet id from `localStorage`.
- Concurrency: simultaneous writers are serialized by SQLite; the loser gets 409 and its typed text stays in the grid. The conflict banner lists cells changed on the server; "Keep my edits and retry" replaces the whole grid and so overwrites those cells, only on explicit click. Cell-wise merging is future work (P4).
- Bad `--data-dir` (empty, a file, unwritable) exits with code 2; port in use exits 1.

## 9. Versioning
API prefix `/api/v1`; schema version in `PRAGMA user_version` with ordered, deterministic migrations; breaking API changes require `/api/v2`.

## 10. Security and validation
Loopback bind only; Host must be loopback on the server's port; Origin checked on POST/PUT; no CORS; CSP with `script-src 'self'`; `nosniff`, `no-store`; static files only from a three-path allowlist; request bodies capped; shapes, lengths and cell ids validated; SQL always parameterized; no `eval` of any input; 10 s socket timeout.

## 11. Future work (one epic)
**Epic: Auditable assumption changes in a single-person offline spreadsheet.** Machine-readable copy: `.prep/backlog.json`.

Epic acceptance: replay of 1000 seeded edits is byte-exact; branches survive restart independently; merges show explicit decisions; CSV round-trips losslessly with literal safety.

### P1 — Dependency evaluator and formula parser (SH-1) [Future]
Story: as a modeller I chain cells and trust one ordered recalculation. Depends on: M1.
Acceptance: A1=2, B1=3, C1==A1+B1, D1==C1*B1 → C1=5, D1=15; A1=4 → 7 and 21 with one evaluation per formula; A1==B1 with B1==A1 → `#CYCLE` in both; `=A1/B1` with B1=0 → `#DIV/0!`; no `eval`/`exec`.

### P2 — Append-only revisions with replay and checkpoints (SH-2) [Future]
Story: as a modeller I can see the exact grid at any past revision. Depends on: P1.
Acceptance: seed 20240601, 1000 modifications, every revision replays to model bytes; checkpoint every 100 revisions; a 5-change batch with one invalid cell changes nothing; UPDATE/DELETE on revisions is rejected.

### P3 — Branch from a past revision (SH-3) [Future]
Story: as a modeller I try a what-if without touching the main sheet. Depends on: P2.
Acceptance: branch 'low-case' from revision 2 diverges from the parent (B1=2 vs B1=10 → C1 5 vs 13) and stays so after restart; duplicate name → 409; past revisions are read-only.

### P4 — Cell-wise three-way merge (SH-4) [Future]
Story: as a modeller I combine a what-if back into the main sheet and decide each clash. Depends on: P3.
Acceptance: independent edits combine (A1=5 ours, B1=6 theirs → C1=11); both changing A1 differently → one conflict, apply without decision → 422; one merge adds exactly one revision; previews are byte-deterministic.

### P5 — CSV interoperability (SH-5) [Future]
Story: as a modeller I move data to and from other tools safely. Depends on: P1, P2.
Acceptance: 3×2 fixture with commas, CRLF inside quotes, `=1+1`, `@SUM(A1)` and UTF-8 round-trips byte-identical; >262144-byte import → 413; safe mode prefixes `=1+1` with one quote and strips it on import; imported text is never executed.

### P6 — Multiline editor and large keyboard-navigable grid (SH-5) [Future]
Story: as a modeller I edit multiline cells and work in grids up to 200×26 by keyboard. Depends on: P5.
Acceptance: all 5200 cells of a 200×26 grid are reached by a scripted keyboard walk in row-major order; no body overflow at 800×600 or 360 px; 201 rows or 27 columns → 400; the multiline editor round-trips `line1\nline2` across restart.

Any package or tool required for future work must be plannable offline and approved before it is staged.

## 12. Acceptance matrix (M1)
| ID | Check | Measure |
|---|---|---|
| M1-1 | Set A1=3, B1=4, C1==A1+B1, Save | C1 result 7 |
| M1-2 | Restart server, reload | A1=3, B1=4, C1 `=A1+B1`, result 7 |
| M1-3 | UTF-8 `héllo ✓ 日本` | byte-identical after reload |
| M1-4 | 201-character cell / 81-character title | 400, nothing saved |
| M1-5 | Stale save | 409, local text retained, banner shown |
| M1-6 | Foreign Host or Origin on PUT | 403 |
| M1-7 | `GET /static/../x`, `%2e%2e` | 404 |
| M1-8 | `=cmd()` typed in a cell | stored literally |
| M1-9 | 800×600 and 360 px | no body horizontal scroll |
| M1-10 | Keyboard only | every cell reachable, Save via Ctrl+S |

## 13. Sample demo
Start the server, press New sheet, title it “Budget”, press Load sample, Save → C1 shows 7. Stop and restart the server on the same data directory, reload → same values. Change B1 in a second tab and save, then save in the first → conflict banner, typed text kept.

## 14. Test plan
Unit tests under `tests/` (standard `unittest` discovery) cover validation, evaluation, storage and restart, conflict, HTTP security headers and rejections, static allowlist, and the static element ids in `index.html`. The JS-built grid, keyboard navigation, conflict banner and layout (M1-5, M1-9, M1-10) are manual checks only. See the README for the browser workflow and observed checks.

## 15. Open choices
- Whether formulas may reference formula cells before the P1 evaluator (currently `#NESTED`).
- Whether the history view lives in a side panel or a separate page.
- Whether the multiline cell editor (P5) replaces or complements the single-line input.
