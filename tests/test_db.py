import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import db


class GetConnectionTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(db, "DATABASE", Path(tmp.name) / "test.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        db.init_db()

    def count_devices(self):
        with db.get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]

    def test_connection_is_closed_after_block(self):
        with db.get_connection() as conn:
            conn.execute("SELECT 1")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_commits_on_success(self):
        with db.get_connection() as conn:
            conn.execute("INSERT INTO devices (mac, name) VALUES ('AA:00:00:00:00:01', 'x')")
        self.assertEqual(self.count_devices(), 1)

    def test_rolls_back_and_closes_on_exception(self):
        with self.assertRaises(RuntimeError):
            with db.get_connection() as conn:
                conn.execute("INSERT INTO devices (mac, name) VALUES ('AA:00:00:00:00:01', 'x')")
                raise RuntimeError("boom")
        self.assertEqual(self.count_devices(), 0)
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_rows_support_column_access(self):
        with db.get_connection() as conn:
            row = conn.execute("SELECT 1 AS one").fetchone()
        self.assertEqual(row["one"], 1)


if __name__ == "__main__":
    unittest.main()
