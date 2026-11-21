# Spreadsheet with Edit History

A local, offline, single-person spreadsheet workbench. The M1 baseline is an 8×6 grid with plain text, numbers and one pure `=A1+B1` formula, saved to SQLite. The goal is to keep a record of how working numbers got there; revisions, branches, merges and CSV are future work.

M1 implements a saved spreadsheet with a small formula subset. See the baseline verification below.

## Requirements
Python 3.12, standard library only. Nothing to install.

## Run
Linux:
```
python3 -m sheet_history --data-dir ./data --port 8765
```
Windows:
```
python -m sheet_history --data-dir .\data --port 8765
```
Open `http://127.0.0.1:8765/`. The server binds to 127.0.0.1 only. `GET /api/v1/health` returns `{"status":"ok","schema":1}`. Stop with Ctrl-C.

## M1 smoke steps
1. Open the page and press **New sheet**; set **Sheet title** to `Budget`.
2. Type `3` in A1, `4` in B1, `=A1+B1` in C1 (or press **Load sample**).
3. Press **Save** (or Ctrl/Cmd+S). Status says “Saved revision 2” and C1 shows result `7`.
4. Stop the server and start it again with the same `--data-dir`; reload the page. A1=3, B1=4, C1 `=A1+B1`, result 7.
5. Type `=cmd()` in D1 and save: it stays literal text.
6. Open a second tab, change and save A1, then save in the first tab: a conflict message appears and your typed text is kept.

## Limits
- Grid 8 rows × 6 columns, ids A1–F8.
- Cell text up to 200 characters; title 1–80 characters; request body up to 64 KiB; up to 50 sheets.
- Control characters are rejected; text is stored exactly as typed in UTF-8.
- Only the form `=<cell>+<cell>` is a formula; a formula operand that is itself a formula shows `#NESTED`.

## Local persistence
Data lives in `<data-dir>/sheets.sqlite` (created if missing). The `data/` folder and SQLite files are git-ignored. A bad data directory (empty, a file, unwritable) exits with code 2.

## Tests
```
python -m unittest discover -s tests -t .
```
(`python3` on Linux.) Tests use temporary directories and port 0.

## Planned scope
Dependency evaluator and parser, append-only revisions with replay, branches for what-if views, cell-wise three-way merge, offline CSV import/export. See [docs/PRD.md](docs/PRD.md).

## Baseline verification

- Windows with Python 3.13.14 and Ubuntu 24.04 WSL with Python 3.12.3 each passed 94 unit and API tests. WSL unit tests used temporary storage on tmpfs.
- Chrome 157 verified the main workflow with external requests blocked. Arrow keys moved between cells, A1=3 and B1=4 evaluated to 7, and the inputs and formula reopened after a server restart.
