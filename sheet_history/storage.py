"""SQLite persistence. One connection per operation; no shared state."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import sheet as sh

SCHEMA_VERSION = 1
MAX_SHEETS = 50
DB_NAME = "sheets.sqlite"

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS sheets(
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 80),
  grid TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision>=1),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""


class StorageError(Exception):
    pass


class NotFoundError(Exception):
    pass


class LimitError(Exception):
    pass


class ConflictError(Exception):
    def __init__(self, current):
        super().__init__("revision conflict")
        self.current = current


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Storage:
    def __init__(self, data_dir):
        if not isinstance(data_dir, str) or data_dir == "":
            raise StorageError("data directory must not be empty")
        path = os.path.abspath(data_dir)
        if os.path.exists(path) and not os.path.isdir(path):
            raise StorageError("data directory path is not a directory")
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            raise StorageError("cannot create data directory: %s" % _oneline(exc)) from exc
        self.db_path = os.path.join(path, DB_NAME)
        try:
            self._init_db()
        except sqlite3.Error as exc:
            raise StorageError("cannot open database: %s" % _oneline(exc)) from exc

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _immediate(self, conn):
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        else:
            conn.execute("COMMIT")

    def _init_db(self):
        with self._connection() as conn:
            self._check_version(conn)  # refuse newer DBs before changing anything
            conn.execute("PRAGMA journal_mode=WAL").fetchall()
            with self._immediate(conn):
                version = self._check_version(conn)
                if version < 1:
                    conn.execute(_SCHEMA_V1)
                    conn.execute("PRAGMA user_version=%d" % SCHEMA_VERSION)

    @staticmethod
    def _check_version(conn):
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise StorageError(
                "database schema version %d is newer than supported (%d)"
                % (version, SCHEMA_VERSION)
            )
        return version

    @staticmethod
    def _to_sheet(row):
        grid = sh.loads_grid(row["grid"])
        return {
            "id": row["id"],
            "title": row["title"],
            "revision": row["revision"],
            "rows": sh.ROWS,
            "cols": sh.COLS,
            "cells": grid,
            "computed": sh.compute(grid),
            "updated_at": row["updated_at"],
        }

    def _load(self, row):
        try:
            return self._to_sheet(row)
        except sh.ValidationError as exc:
            raise StorageError("stored sheet %d is corrupt" % row["id"]) from exc

    def list_sheets(self):
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, title, revision, updated_at FROM sheets ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_sheet(self, sheet_id):
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM sheets WHERE id=?", (sheet_id,)).fetchone()
        if row is None:
            raise NotFoundError("sheet not found")
        return self._load(row)

    def create_sheet(self, title):
        title = sh.validate_title(title)
        now = _now()
        with self._connection() as conn:
            with self._immediate(conn):
                count = conn.execute("SELECT COUNT(*) FROM sheets").fetchone()[0]
                if count >= MAX_SHEETS:
                    raise LimitError("at most %d sheets are allowed" % MAX_SHEETS)
                cur = conn.execute(
                    "INSERT INTO sheets(title, grid, revision, created_at, updated_at)"
                    " VALUES(?,?,?,?,?)",
                    (title, "{}", 1, now, now),
                )
                new_id = cur.lastrowid
            row = conn.execute("SELECT * FROM sheets WHERE id=?", (new_id,)).fetchone()
        return self._load(row)

    def update_sheet(self, sheet_id, base_revision, title, cells):
        """Replace title and grid if base_revision matches; else ConflictError."""
        title = sh.validate_title(title)
        grid = sh.canonicalize_cells(cells)
        grid_text = sh.dumps_grid(grid)
        now = _now()
        with self._connection() as conn:
            with self._immediate(conn):
                row = conn.execute(
                    "SELECT * FROM sheets WHERE id=?", (sheet_id,)
                ).fetchone()
                if row is None:
                    raise NotFoundError("sheet not found")
                changed = 0
                if row["revision"] == base_revision:
                    changed = conn.execute(
                        "UPDATE sheets SET title=?, grid=?, revision=revision+1,"
                        " updated_at=? WHERE id=? AND revision=?",
                        (title, grid_text, now, sheet_id, base_revision),
                    ).rowcount
                if changed != 1:
                    current = self._load(row)
                    raise ConflictError(current)
            row = conn.execute("SELECT * FROM sheets WHERE id=?", (sheet_id,)).fetchone()
        return self._load(row)


def _oneline(exc):
    return " ".join(str(exc).split())
