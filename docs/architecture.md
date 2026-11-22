# Architecture notes and PRD drift

Checked against commit `2fd3a12` (the M1 baseline) on 2026-11-22, on Windows 11 with Python 3.13.14. The product intent is in [PRD.md](PRD.md); this file records how the code is built today, what was observed to work, and where the documents and the code differ.

Evidence marks used below:

- **ran**: observed during preparation by running the code (test suite, a real server on a scratch data directory, HTTP requests, or a local headless browser).
- **read**: taken from the source, not exercised by hand.
- **not verified**: claimed by a document, not reproduced.

## Shape

One Python package, standard library only, in three layers plus a static page. There is no framework, no package manifest and no build step.

| Layer | File | Owns | Imports from the package |
|---|---|---|---|
| Command line | `sheet_history/__main__.py` | arguments, exit codes, the serve loop | `server`, `storage` (for `StorageError`) |
| HTTP adapter | `sheet_history/server.py` | request guards, routing, JSON envelope, static allowlist | `sheet`, `storage` |
| Persistence | `sheet_history/storage.py` | SQLite file, schema version, transactions, the revision check | `sheet` |
| Grid model | `sheet_history/sheet.py` | validation, canonical grid, formula evaluation; no I/O | nothing |
| Browser page | `sheet_history/static/index.html`, `app.js`, `app.css` | rendering, unsaved edits, keyboard handling | talks to the API only |

The dependency direction is `__main__` → `server` → `storage` → `sheet`. `sheet.py` imports only `json`, `re` and `decimal`.

## Traced workflow: edit a cell, save, restart, reopen

1. **Start.** `main()` parses `--data-dir` (required) and `--port` (default 8765, 0 to 65535) (`__main__.py:26-33`) and calls `make_server` (`server.py:295-302`). `make_server` opens `Storage`, binds `127.0.0.1`, and records the two accepted Host values, `127.0.0.1:<port>` and `localhost:<port>`. A storage error exits with code 2 and a bind error with code 1 (`__main__.py:37-46`). *ran: a file as data directory gave exit 2; a port already in use gave exit 1.*
2. **Open the database.** `Storage.__init__` creates the directory and calls `_init_db` (`storage.py:49-63, 89-97`): refuse a newer `PRAGMA user_version`, switch to WAL, then create the `sheets` table and set `user_version=1` inside one `BEGIN IMMEDIATE` transaction.
3. **Load the page.** `GET /`, `/static/app.css` and `/static/app.js` are the only static paths (`server.py:21-25, 183-189`). `app.js` builds the 8×6 table (`app.js:239-281`), fetches `GET /api/v1/sheets`, and opens the sheet id remembered in `localStorage` under `sheet_history.last`, or the first sheet (`app.js:341-350`). *ran in headless Chrome 157: 48 inputs, status `Opened "Budget" at revision 2`, C1 showed `7`; the browser requested only the five local URLs.*
4. **Edit.** Typing fires `onCellInput`, which stores the text in the in-memory `local` map and marks the cell dirty (`app.js:283-287, 46-53`). Nothing is sent yet.
5. **Save.** The Save button or Ctrl/Cmd+S calls `save()` → `doSave(sheet.revision)` (`app.js:208-215, 182-206, 330-335`), which sends `PUT /api/v1/sheets/{id}` with exactly `{base_revision, title, cells}`; `cells` holds every non-empty cell of the grid (`app.js:176-180`).
6. **Guards.** `Handler._handle` checks that exactly one Host header is present and allowed, resolves the route, answers 405 for a wrong method, and on POST and PUT rejects an Origin header that is not one of the two loopback origins (`server.py:142-164`). `_read_json_object` requires `application/json`, a numeric `Content-Length`, at most 65536 bytes, valid UTF-8 JSON and an object (`server.py:211-235`). `_put` requires exactly the three keys and an integer `base_revision` (`server.py:200-208`).
7. **Validate and write.** `Storage.update_sheet` validates the title and the cells and builds the canonical grid text before it opens the transaction (`storage.py:160-165`; `sheet.py:28-58`). Inside `BEGIN IMMEDIATE` it reads the row, and when the stored revision equals `base_revision` it runs `UPDATE ... SET revision=revision+1 ... WHERE id=? AND revision=?` (`storage.py:166-179`). Any other case raises `ConflictError` carrying the current sheet (`storage.py:180-182`), which the handler turns into 409 with `current` (`server.py:124-131`).
8. **Respond.** `_to_sheet` loads the grid and adds `computed`, which is recalculated on every read and never stored (`storage.py:109-121`; `sheet.py:77-101`). The page replaces its state with the response and shows `Saved revision N` (`app.js:187-192, 71-81`). *ran: typing `5` in E2 and pressing Ctrl+S gave `Saved revision 3`, and the server returned E2.*
9. **Restart and reopen.** The grid lives in `<data-dir>/sheets.sqlite`. *ran: after stopping the server and starting it again on the same directory, `GET /api/v1/sheets/1` returned the same revision, cells and computed values.*

Stale save, also traced: with the page at revision 3, a second writer saved B1 over the API (revision 4). Saving in the page then gave status `Not saved: conflict with a newer revision.`, the alert region listed `B1` as changed on the server, focus moved to "Load server version", and the typed text stayed in the grid. "Keep my edits and retry" saved on top as revision 5 and overwrote B1 with the page's value (`app.js:83-97, 193-196, 324-329`). *ran.*

## Data ownership

- The server owns saved state. One row per sheet in `sheets(id, title, grid, revision, created_at, updated_at)` (`storage.py:14-23`). `grid` is the canonical JSON text of the non-empty cells; `revision` is a counter, not a history. **There is no revision log, no branch and no past state in the baseline.**
- The browser owns only unsaved edits: `sheet` is the last server version, `local` is the text typed since (`app.js:16-17`). Every save replaces the whole grid.
- `computed` is derived. It is never written to the database.

## Invariants a change must keep

| Invariant | Where | Covered by |
|---|---|---|
| Grid is 8 rows × 6 columns, ids `A1` to `F8`; the size is hard-coded in three places | `sheet.py:7-18`, `app.js:4-5`, `index.html:45` (caption), plus `rows`/`cols` in `storage.py:116-117` | `tests/test_sheet.py` `CellValidationTests` |
| Cell text is 0 to 200 code points, title 1 to 80; control characters (below U+0020, U+007F) and lone surrogates are rejected; text is stored as typed | `sheet.py:28-43` | `test_length_cap_counts_code_points`, `test_control_chars_and_surrogates_rejected`, `test_text_stored_exactly_without_trim` |
| Canonical grid: non-empty cells only, row-major key order, compact separators, `ensure_ascii=False` | `sheet.py:46-58` | `CanonicalTests` |
| Only `=<cell>+<cell>` is evaluated, with `Decimal` at 600 digits of precision; a formula operand gives `#NESTED`, a text operand `#VALUE!`; nothing is passed to `eval` | `sheet.py:15, 21, 77-101` | `FormulaTests` |
| A write succeeds only when `base_revision` equals the stored revision; a stale or future revision gets 409 with the current sheet and changes nothing | `storage.py:166-182`, `server.py:124-131` | `ConflictTests`, `test_concurrent_puts_exactly_one_wins` |
| One SQLite connection per operation, WAL, `busy_timeout` 5 s; every write is one `BEGIN IMMEDIATE` transaction | `storage.py:65-97` | `test_schema_version_and_wal` |
| A database with a newer `user_version` is refused before anything is changed | `storage.py:91, 99-107` | `test_newer_schema_refused` |
| Loopback bind; exactly one allowed Host header on every request; Origin checked on POST and PUT when present; no CORS headers | `server.py:17, 142-164, 295-302` | `HeaderAndRequestGuardTests` |
| Every response carries the CSP (`script-src 'self'`, `style-src 'self'`), `nosniff`, `no-store`, `no-referrer` and `Connection: close` | `server.py:27-37, 258-270` | `test_security_headers_on_all_response_kinds` |
| Static files come from an exact three-entry map; any other path is 404 | `server.py:21-25, 166-168` | `StaticTests` |
| JSON bodies only, at most 65536 bytes, exact key sets | `server.py:15, 194-235` | `ValidationTests`, `CapTests` |
| At most 50 sheets | `storage.py:11, 148-150` | `test_fifty_sheet_limit` |
| The page writes user text with `textContent` and `.value` only | `app.js` | `test_app_js_avoids_innerhtml` |
| Unhandled errors return a generic 500 and print the traceback to stderr | `server.py:134-139` | `test_internal_error_is_generic` |

## Implemented, planned, needs verification

| Area | Status | Evidence |
|---|---|---|
| M1 grid, one formula form, explicit Save, title, New sheet, sheet list | Implemented | ran: 94 tests pass; create, save and reopen observed over HTTP and in headless Chrome |
| HTTP API of PRD section 5.2 | Implemented | ran: health, create, save, 409, 400 for a 201-character cell, 403 for a foreign Origin and a foreign Host, 404 for traversal paths |
| Stale-save conflict banner and both of its actions (M1-5) | Implemented | ran in headless Chrome 157 ("Keep my edits and retry"); "Load server version" read only |
| Keyboard reach (M1-10) | Implemented | ran: Tab from A1 visited all 48 cells in row-major order; arrow keys and Enter moved as written in `app.js:296-310`; Ctrl+S saved |
| No horizontal page scroll at 800×600 and 360 px (M1-9) | Implemented | ran: `document.body.scrollWidth` was 800 at 800×600 and 345 at 360×640; the grid wrapper scrolls inside itself |
| Restart persistence (M1-2) | Implemented | ran |
| Exit codes 2 and 1 | Implemented | ran for "data directory is a file" and "port in use"; the other cases are covered by `tests/test_cli.py` |
| Contrast of 4.5:1, visible focus style, screen-reader announcements (PRD section 7) | Needs verification | read only; no measurement was made |
| Unload warning, New sheet and Load sample buttons in a browser | Needs verification | read only (`app.js:217-236, 336-338`) |
| Linux and Python 3.12 runs reported in the README | Needs verification | not repeated during preparation |
| General formula parser and dependency evaluator (PRD P1, issue #2) | Planned | `compute` handles one regex form (`sheet.py:15, 77-101`) |
| Append-only revisions, replay, checkpoints (P2, issue #3) | Planned | no revision table; `revision` is a counter |
| Branches (P3, issue #4), three-way merge (P4, issue #5) | Planned | nothing in the code |
| CSV import and export (P5, issue #6) | Planned | nothing in the code; line breaks in cells are rejected today (`sheet.py:37`) |
| Multiline editor and grids up to 200×26 (P6, issue #7) | Planned | the grid size is hard-coded (see the invariants table) |

The browser observations above came from a scripted run kept outside the repository. The repository itself has no browser test; PRD section 14 lists the browser checks as manual. Issue #8 plans a repeatable browser harness built on the standard library, and issue #9 plans one acceptance run over the whole epic; neither exists yet.

## Where the documents and the code differ

| # | Document says | Code or observation | Weight |
|---|---|---|---|
| 1 | PRD sections 2 and 11 label both P5 (CSV) and P6 (multiline editor, large grid) as `SH-5`; section 15 calls the multiline editor "P5" | The GitHub issues are separate: CSV is #6, the editor and large grid are #7 | Naming only. Use the issue numbers. |
| 2 | PRD section 11 points to `.prep/backlog.json` as the machine-readable backlog | `.prep/` is ignored by Git and is not in the repository | A clone does not have that file. The epic issue (#1) and its sub-issues are the backlog. |
| 3 | PRD section 5.1: any other `=…` text is literal and has no computed value; a formula operand gives `#NESTED` (fixtures F4, F5; M1-8) | True today. P1 (issue #2) replaces both rules: text starting with `=` is always parsed, and nested references are evaluated | Planned behaviour change. The ticket that builds P1 must update PRD sections 5.1, 6 and 12 and the tests that pin the old rule (`test_non_formulas_are_literal_and_not_computed`, `test_nested_and_self_reference`, `test_formula_operand_that_is_literal_equals_text`, part of `test_text_operand_is_value_error`). |
| 4 | PRD section 5.2 and the README show the health body as `{"status":"ok","schema":1}` | The server sends `{"status": "ok", "schema": 1}` (default `json.dumps` separators, `server.py:272-274`). The schema number is a literal in `server.py:170`, not `storage.SCHEMA_VERSION` | Cosmetic for the spacing; the tests compare parsed JSON. The literal matters when the schema version first changes (P2). |
| 5 | PRD section 5.2 lists "other codes" 403, 405, 413, 415, 500 | The server also answers 411 with code `invalid` when `Content-Length` is missing or `Transfer-Encoding` is present (`server.py:215-219`) | Small omission in the PRD. |
| 6 | PRD section 10: "Origin checked on POST/PUT" | The check applies only when an Origin header is present (`server.py:158-163`); a request without one is accepted | By design for non-browser clients on loopback; stated here so a reviewer does not assume more. |
| 7 | PRD section 4 and the README: "Python 3.12" | Observed on Python 3.13.14 (Windows). The README reports Python 3.12.3 on WSL, which was not repeated | Read the requirement as "3.12 or newer". |
| 8 | PRD section 14: browser checks are manual only; the README says Chrome 157 verified the main workflow | No script or recorded result is in the repository | The claim is not reproducible from the repository alone. Issue #8 plans the harness that would make it reproducible. |
| 9 | PRD section 5.1: cell input is 0 to 200 code points | The server counts code points (`sheet.py:33`); the page sets `maxLength = 200` on each input (`app.js:264`), which browsers count in UTF-16 code units | read only. A cell of characters outside the Basic Multilingual Plane is cut off earlier in the page than the server requires. |
| 10 | README "Run" shows `--port 8765` as part of the command | `--port` is optional and defaults to 8765; port 0 is accepted and binds a free port (`__main__.py:16-29`) | No conflict; noted for scripts. |

## Notes for the epic (issue #1)

These follow from the code above and are repeated in the tickets that they affect. The tickets are the sub-issues of #1, in dependency order: #8, #2, #3, #4, #6, #5, #7, #9.

- **Schema version (issue #3 first, then #4 and #7).** `_init_db` only knows "create version 1" (`storage.py:93-97`). The first schema change needs an ordered list of migrations that runs inside one `BEGIN IMMEDIATE` transaction. On SQLite 3.50.4 a `PRAGMA user_version` change made inside a transaction was rolled back with it (ran in a scratch check), so a failed migration can leave the version untouched. A database written by a newer schema cannot be opened by older code; that rule stays.
- **Whole-grid saves (issue #7).** The page sends every non-empty cell on each save and the body cap is 65536 bytes. That is enough for 48 cells of 200 characters. It is not enough for a 200×26 grid, so the large-grid ticket has to change how the page saves.
- **Exact key sets (issue #3).** `_create` and `_put` reject unknown keys (`server.py:196, 202`). New inputs go to new routes or to query parameters. The query string is ignored today (`server.py:147`); the first ticket that needs parameters has to add strict parsing.
- **Computed values on read (issue #2).** `compute` runs on every sheet read and on the `current` sheet inside a 409. An evaluator must bound its output: at 600 digits of precision `1/3` formats to 602 characters, and twelve squarings of a 200-digit number format to more than 800 000 characters before the thirteenth overflows (ran in a scratch check).
- **Line breaks (issues #6 and #7).** `<input type="text">` removes line breaks from any value assigned to it. The page keeps the real text in `local`, and `payload()` sends `local`, not the input values (`app.js:71-76, 176-180`), so an unedited multiline cell would survive a save, while an edited one would not.
- **Static allowlist and CSP.** A new script or style file must be added to `STATIC_FILES`. Inline script and inline style are blocked by the policy.
- **Stopping a server on Windows.** The listener uses `SO_EXCLUSIVEADDRUSE` (`server.py:283-292`). After stopping a server, check that the port has no listener; stop a leftover process by its PID.
