import gzip
import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import backup


class CreateBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.source_db = self.tmp_path / "source.db"
        self.backup_dir = self.tmp_path / "backups"

        conn = sqlite3.connect(self.source_db)
        conn.execute("CREATE TABLE measurements (id INTEGER PRIMARY KEY, temperature REAL)")
        conn.execute("INSERT INTO measurements (temperature) VALUES (21.5)")
        conn.commit()
        conn.close()

    def test_backup_filename_is_date_only(self):
        when = datetime(2026, 9, 19, 3, 0, 0)
        self.assertEqual(backup.backup_filename(when), "ruuvi-2026-09-19.db")

    def test_create_backup_writes_gzipped_snapshot_with_source_data(self):
        when = datetime(2026, 9, 19, 3, 0, 0)

        gz_path = backup.create_backup(self.source_db, self.backup_dir, when)

        self.assertEqual(gz_path, self.backup_dir / "ruuvi-2026-09-19.db.gz")
        self.assertTrue(gz_path.exists())
        self.assertFalse((self.backup_dir / "ruuvi-2026-09-19.db").exists())

        restored = self.tmp_path / "restored.db"
        with gzip.open(gz_path, "rb") as f_in, open(restored, "wb") as f_out:
            f_out.write(f_in.read())
        conn = sqlite3.connect(restored)
        row = conn.execute("SELECT temperature FROM measurements").fetchone()
        conn.close()
        self.assertEqual(row[0], 21.5)

    def test_create_backup_same_day_overwrites_not_duplicates(self):
        when = datetime(2026, 9, 19, 3, 0, 0)

        backup.create_backup(self.source_db, self.backup_dir, when)
        backup.create_backup(self.source_db, self.backup_dir, when)

        files = sorted(self.backup_dir.glob("ruuvi-2026-09-19.db*"))
        self.assertEqual(files, [self.backup_dir / "ruuvi-2026-09-19.db.gz"])


if __name__ == "__main__":
    unittest.main()
