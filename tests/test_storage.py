import os
import re
import sqlite3
import tempfile
import unittest

from sheet_history import sheet as sh
from sheet_history import storage as st


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        self.data_dir = os.path.join(tmp.name, "data")
        self.store = st.Storage(self.data_dir)


class CrudTests(StorageTestCase):
    def test_create_get_list(self):
        sheet = self.store.create_sheet("First")
        self.assertEqual(sheet["id"], 1)
        self.assertEqual(sheet["revision"], 1)
        self.assertEqual((sheet["rows"], sheet["cols"]), (8, 6))
        self.assertEqual(sheet["cells"], {})
        self.assertEqual(sheet["computed"], {})
        self.assertRegex(sheet["updated_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.store.create_sheet("Second")
        listing = self.store.list_sheets()
        self.assertEqual([s["id"] for s in listing], [1, 2])
        self.assertEqual(set(listing[0]), {"id", "title", "revision", "updated_at"})
        self.assertEqual(self.store.get_sheet(1)["title"], "First")

    def test_update_increments_revision_and_computes(self):
        self.store.create_sheet("S")
        out = self.store.update_sheet(1, 1, "S2", {"A1": "3", "B1": "4", "C1": "=A1+B1"})
        self.assertEqual(out["revision"], 2)
        self.assertEqual(out["title"], "S2")
        self.assertEqual(out["computed"], {"C1": "7"})

    def test_update_replaces_whole_grid(self):
        self.store.create_sheet("S")
        self.store.update_sheet(1, 1, "S", {"A1": "1", "B1": "2"})
        out = self.store.update_sheet(1, 2, "S", {"B1": "9"})
        self.assertEqual(out["cells"], {"B1": "9"})

    def test_not_found(self):
        with self.assertRaises(st.NotFoundError):
            self.store.get_sheet(99)
        with self.assertRaises(st.NotFoundError):
            self.store.update_sheet(99, 1, "t", {})

    def test_utf8_round_trip_and_stored_as_text(self):
        text = "héllo ✓ 日本"
        self.store.create_sheet(text)
        self.store.update_sheet(1, 1, text, {"A1": text})
        got = self.store.get_sheet(1)
        self.assertEqual(got["title"], text)
        self.assertEqual(got["cells"]["A1"], text)
        conn = sqlite3.connect(self.store.db_path)
        try:
            grid, typ = conn.execute("SELECT grid, typeof(grid) FROM sheets").fetchone()
        finally:
            conn.close()
        self.assertEqual(typ, "text")
        self.assertEqual(grid, '{"A1":"%s"}' % text)

    def test_literal_formula_like_text_not_executed(self):
        self.store.create_sheet("S")
        cells = {"A1": "=1+2", "B1": "@x", "C1": "-y", "D1": "+z"}
        out = self.store.update_sheet(1, 1, "S", cells)
        self.assertEqual(out["cells"], cells)
        self.assertEqual(out["computed"], {})


class BoundaryTests(StorageTestCase):
    def test_sheet_cap_50(self):
        for i in range(50):
            self.store.create_sheet("s%d" % i)
        with self.assertRaises(st.LimitError):
            self.store.create_sheet("one too many")
        self.assertEqual(len(self.store.list_sheets()), 50)

    def test_stale_base_conflicts_with_current(self):
        self.store.create_sheet("S")
        self.store.update_sheet(1, 1, "S", {"A1": "server"})
        with self.assertRaises(st.ConflictError) as ctx:
            self.store.update_sheet(1, 1, "S", {"A1": "mine"})
        self.assertEqual(ctx.exception.current["revision"], 2)
        self.assertEqual(ctx.exception.current["cells"], {"A1": "server"})
        self.assertEqual(self.store.get_sheet(1)["cells"], {"A1": "server"})

    def test_future_base_also_conflicts(self):
        self.store.create_sheet("S")
        with self.assertRaises(st.ConflictError):
            self.store.update_sheet(1, 5, "S", {"A1": "x"})
        self.assertEqual(self.store.get_sheet(1)["revision"], 1)

    def test_retry_with_current_revision_succeeds(self):
        self.store.create_sheet("S")
        self.store.update_sheet(1, 1, "S", {"A1": "server"})
        try:
            self.store.update_sheet(1, 1, "S", {"A1": "mine"})
        except st.ConflictError as exc:
            out = self.store.update_sheet(1, exc.current["revision"], "S", {"A1": "mine"})
        self.assertEqual(out["revision"], 3)
        self.assertEqual(out["cells"], {"A1": "mine"})

    def test_invalid_update_changes_nothing_and_store_stays_usable(self):
        self.store.create_sheet("S")
        self.store.update_sheet(1, 1, "S", {"A1": "ok"})
        bad_updates = [
            ("", {"A1": "x"}),
            ("t" * 81, {"A1": "x"}),
            ("S", {"A1": "x" * 201}),
            ("S", {"G1": "x"}),
            ("S", {"A1": "a\x00b"}),
        ]
        for title, cells in bad_updates:
            with self.subTest(title=title[:5], cells=list(cells)):
                with self.assertRaises(sh.ValidationError):
                    self.store.update_sheet(1, 2, title, cells)
        got = self.store.get_sheet(1)
        self.assertEqual((got["revision"], got["cells"]), (2, {"A1": "ok"}))
        self.assertEqual(self.store.update_sheet(1, 2, "S", {"A1": "next"})["revision"], 3)

    def test_invalid_title_on_create(self):
        for bad in ("", "x" * 81, "a\nb", 5):
            with self.subTest(bad=bad):
                with self.assertRaises(sh.ValidationError):
                    self.store.create_sheet(bad)
        self.assertEqual(self.store.list_sheets(), [])

    def test_corrupt_grid_reports_storage_error(self):
        self.store.create_sheet("S")
        conn = sqlite3.connect(self.store.db_path)
        try:
            conn.execute("UPDATE sheets SET grid='not json'")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(st.StorageError):
            self.store.get_sheet(1)
        # listing does not parse grids, so other views remain usable
        self.assertEqual(len(self.store.list_sheets()), 1)


class PersistenceAndSetupTests(StorageTestCase):
    def test_restart_persistence(self):
        self.store.create_sheet("Keep")
        self.store.update_sheet(1, 1, "Keep", {"A1": "3", "B1": "4", "C1": "=A1+B1"})
        reopened = st.Storage(self.data_dir)
        got = reopened.get_sheet(1)
        self.assertEqual(got["revision"], 2)
        self.assertEqual(got["cells"], {"A1": "3", "B1": "4", "C1": "=A1+B1"})
        self.assertEqual(got["computed"], {"C1": "7"})

    def test_schema_version_and_wal(self):
        conn = sqlite3.connect(self.store.db_path)
        try:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
        finally:
            conn.close()

    def test_no_sheet_auto_created(self):
        self.assertEqual(self.store.list_sheets(), [])

    def test_data_dir_created_when_missing(self):
        nested = os.path.join(self.root, "a", "b", "c")
        st.Storage(nested)
        self.assertTrue(os.path.isfile(os.path.join(nested, "sheets.sqlite")))

    def test_empty_data_dir_rejected(self):
        with self.assertRaises(st.StorageError):
            st.Storage("")

    def test_file_as_data_dir_rejected(self):
        path = os.path.join(self.root, "afile")
        with open(path, "w") as fh:
            fh.write("x")
        with self.assertRaises(st.StorageError):
            st.Storage(path)

    def test_database_path_blocked_by_directory_rejected(self):
        d = os.path.join(self.root, "blocked")
        os.makedirs(os.path.join(d, "sheets.sqlite"))
        with self.assertRaises(st.StorageError):
            st.Storage(d)

    def test_newer_schema_refused(self):
        d = os.path.join(self.root, "future")
        os.makedirs(d)
        conn = sqlite3.connect(os.path.join(d, "sheets.sqlite"))
        conn.execute("PRAGMA user_version=2")
        conn.commit()
        conn.close()
        with self.assertRaises(st.StorageError):
            st.Storage(d)
        conn = sqlite3.connect(os.path.join(d, "sheets.sqlite"))
        try:
            tables = conn.execute("SELECT name FROM sqlite_master").fetchall()
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)
        finally:
            conn.close()
        self.assertEqual(tables, [])

    def test_not_a_database_file_rejected(self):
        d = os.path.join(self.root, "garbage")
        os.makedirs(d)
        with open(os.path.join(d, "sheets.sqlite"), "wb") as fh:
            fh.write(b"this is definitely not sqlite" * 20)
        with self.assertRaises(st.StorageError):
            st.Storage(d)

    def test_error_messages_are_single_line(self):
        try:
            st.Storage("")
        except st.StorageError as exc:
            self.assertNotIn("\n", str(exc))
        self.assertTrue(re.match(r".+", "x"))


if __name__ == "__main__":
    unittest.main()
