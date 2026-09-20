import gzip
import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

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
        self.assertEqual(list(self.backup_dir.glob("*.tmp")), [])

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

    def test_create_backup_raises_on_missing_source_database(self):
        when = datetime(2026, 9, 19, 3, 0, 0)
        missing_db = self.tmp_path / "nonexistent.db"

        with self.assertRaises(FileNotFoundError):
            backup.create_backup(missing_db, self.backup_dir, when)

        # Verify no backup file was created as a side effect
        files = list(self.backup_dir.glob("*"))
        self.assertEqual(files, [])

    def test_create_backup_cleans_up_on_write_failure(self):
        when = datetime(2026, 9, 19, 3, 0, 0)

        with patch("backup.shutil.copyfileobj", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                backup.create_backup(self.source_db, self.backup_dir, when)

        # No uncompressed .db leftover, no leftover .gz.tmp, and no partial/final
        # .gz either -- a failed attempt must not leave anything behind that looks
        # like (or could be mistaken for) a valid backup.
        remaining = sorted(p.name for p in self.backup_dir.glob("*"))
        self.assertEqual(remaining, [])

    def test_create_backup_does_not_clobber_existing_gz_on_write_failure(self):
        when = datetime(2026, 9, 19, 3, 0, 0)

        # Establish a real, valid backup first.
        good_gz = backup.create_backup(self.source_db, self.backup_dir, when)
        original_contents = good_gz.read_bytes()

        with patch("backup.shutil.copyfileobj", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                backup.create_backup(self.source_db, self.backup_dir, when)

        # The pre-existing good backup must survive a failed re-attempt untouched.
        self.assertTrue(good_gz.exists())
        self.assertEqual(good_gz.read_bytes(), original_contents)
        remaining = sorted(p.name for p in self.backup_dir.glob("*"))
        self.assertEqual(remaining, [good_gz.name])


class PruneOldBackupsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backup_dir = Path(self.tmp.name)

    def _touch_backup(self, date_str):
        path = self.backup_dir / f"ruuvi-{date_str}.db.gz"
        with gzip.open(path, "wb") as f:
            f.write(b"fake")
        return path

    def test_prune_deletes_only_backups_older_than_retention(self):
        old = self._touch_backup("2026-08-01")     # 49 days before "now"
        recent = self._touch_backup("2026-09-10")  # 9 days before "now"
        now = datetime(2026, 9, 19)

        deleted = backup.prune_old_backups(self.backup_dir, days=30, now=now)

        self.assertEqual(deleted, [old])
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    def test_prune_ignores_files_that_dont_match_backup_naming(self):
        stray = self.backup_dir / "notes.txt"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stray.write_text("not a backup")
        now = datetime(2026, 9, 19)

        deleted = backup.prune_old_backups(self.backup_dir, days=30, now=now)

        self.assertEqual(deleted, [])
        self.assertTrue(stray.exists())

    def test_prune_on_empty_directory_returns_empty_list(self):
        now = datetime(2026, 9, 19)
        deleted = backup.prune_old_backups(self.backup_dir, days=30, now=now)
        self.assertEqual(deleted, [])


if __name__ == "__main__":
    unittest.main()
