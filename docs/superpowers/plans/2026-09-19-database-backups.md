# Database Backups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Daily, automated, gzip-compressed local backups of `data/ruuvi.db`, retained for 30 days, run via a new systemd timer on the Pi.

**Architecture:** A new standalone script `backup.py` (same style as `init_db.py`/`create_user.py`) uses SQLite's `Connection.backup()` API to take a consistent snapshot of the live database, gzips it, and deletes snapshots older than the retention window. A new `systemd` oneshot service + timer runs it once a day, following the same pattern as the existing collector/dashboard units.

**Tech Stack:** Python stdlib only (`sqlite3`, `gzip`, `shutil`, `pathlib`, `logging`, `datetime`) plus this repo's `db.py`. Tests use stdlib `unittest` (no new test framework dependency). No new pip dependencies.

**Spec:** `docs/superpowers/specs/2026-09-19-database-backups-design.md`

## Global Constraints

- No new dependencies — stdlib only, plus `db.py`. (spec: "no new dependencies")
- Backup filenames are date-only: `ruuvi-YYYY-MM-DD.db` (pre-compression) / `ruuvi-YYYY-MM-DD.db.gz` (final). Same-day re-runs overwrite, never duplicate.
- Retention: 30 days, local only (`backups/`). No off-Pi shipping in this plan.
- Backups must be taken via SQLite's backup API, never a raw file copy, because the source database may be written concurrently by `collector.py`.
- A pruning failure (individual bad file) must never prevent that day's backup from being created or counted as successful.
- systemd units follow the existing pattern in `systemd/`: `User=ruuvi`, `Group=ruuvi`, `WorkingDirectory=/home/ruuvi/ruuvi`, venv interpreter at `/home/ruuvi/ruuvi/venv/bin/python`.

---

### Task 1: `create_backup()` — consistent gzip snapshot

**Files:**
- Create: `backup.py`
- Create: `tests/test_backup.py`

**Interfaces:**
- Produces: `backup.backup_filename(when: datetime) -> str` — returns `"ruuvi-YYYY-MM-DD.db"` for the given datetime.
- Produces: `backup.create_backup(source_db: Path, backup_dir: Path, when: datetime) -> Path` — creates `backup_dir` if missing, writes a consistent snapshot of `source_db` into `backup_dir / backup_filename(when)`, gzips it to the same name + `.gz`, deletes the uncompressed copy, and returns the `Path` to the `.gz` file. Safe to call twice with the same `when` (overwrites, no duplicate).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_backup.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_backup -v`
Expected: `ModuleNotFoundError: No module named 'backup'` (the file doesn't exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `backup.py`:

```python
import gzip
import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backup")

BACKUP_DIR = Path(__file__).parent / "backups"
RETENTION_DAYS = 30


def backup_filename(when):
    """Returns the date-only backup filename for a given datetime, e.g. 'ruuvi-2026-09-19.db'."""
    return f"ruuvi-{when:%Y-%m-%d}.db"


def create_backup(source_db, backup_dir, when):
    """Writes a consistent gzip snapshot of source_db into backup_dir and returns its path.

    Uses SQLite's own backup API rather than a file copy, since source_db may be
    written concurrently by the collector. Re-running with the same `when` overwrites
    the existing snapshot for that day instead of creating a duplicate.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    db_path = backup_dir / backup_filename(when)
    gz_path = backup_dir / (db_path.name + ".gz")

    source_conn = sqlite3.connect(source_db)
    try:
        dest_conn = sqlite3.connect(db_path)
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        source_conn.close()

    with open(db_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    db_path.unlink()

    return gz_path


if __name__ == "__main__":
    pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_backup -v`
Expected: `OK` (3 tests passed).

- [ ] **Step 5: Commit**

```bash
git add backup.py tests/test_backup.py
git commit -m "feat: add create_backup() for consistent gzip snapshots of the RuuviTag database"
```

---

### Task 2: `prune_old_backups()` — 30-day retention

**Files:**
- Modify: `backup.py`
- Modify: `tests/test_backup.py`

**Interfaces:**
- Consumes: nothing from Task 1 directly (operates only on files in `backup_dir`, independent of `create_backup`'s internals).
- Produces: `backup.prune_old_backups(backup_dir: Path, days: int, now: datetime) -> list[Path]` — deletes any `backup_dir/ruuvi-*.db.gz` file whose date is more than `days` days before `now`, returns the list of deleted paths. Files that don't match the `ruuvi-YYYY-MM-DD.db.gz` naming pattern are skipped (logged, not deleted). A per-file delete failure is logged and does not stop pruning of the remaining files.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_backup.py` (below `CreateBackupTests`, above the `if __name__ == "__main__":` block):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_backup -v`
Expected: `AttributeError: module 'backup' has no attribute 'prune_old_backups'`.

- [ ] **Step 3: Write minimal implementation**

In `backup.py`, add below `create_backup` (and update the `datetime` import to include `date`... not needed, `datetime.strptime(...).date()` covers it):

```python
def _parse_backup_date(path):
    """Extracts the date from a 'ruuvi-YYYY-MM-DD.db.gz' filename, or None if it doesn't match."""
    prefix, suffix = "ruuvi-", ".db.gz"
    name = path.name
    if not (name.startswith(prefix) and name.endswith(suffix)):
        return None
    date_str = name[len(prefix):-len(suffix)]
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def prune_old_backups(backup_dir, days, now):
    """Deletes backup_dir/ruuvi-*.db.gz files older than `days` days before `now`.

    Returns the list of deleted paths. Unrecognized filenames are skipped (not
    deleted). A failure deleting one file is logged and does not stop the rest.
    """
    deleted = []
    for path in sorted(backup_dir.glob("ruuvi-*.db.gz")):
        backup_date = _parse_backup_date(path)
        if backup_date is None:
            logger.warning(f"Skipping unrecognized backup filename: {path.name}")
            continue

        age_days = (now.date() - backup_date).days
        if age_days > days:
            try:
                path.unlink()
                deleted.append(path)
            except OSError:
                logger.exception(f"Failed to delete old backup: {path}")

    return deleted
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_backup -v`
Expected: `OK` (6 tests passed).

- [ ] **Step 5: Commit**

```bash
git add backup.py tests/test_backup.py
git commit -m "feat: add prune_old_backups() for 30-day local retention"
```

---

### Task 3: `main()` orchestration and manual smoke test

**Files:**
- Modify: `backup.py`

**Interfaces:**
- Consumes: `create_backup(source_db, backup_dir, when)` and `prune_old_backups(backup_dir, days, now)` from Tasks 1–2; `db.DATABASE` (existing `Path` constant in `db.py` pointing at the configured database file).
- Produces: `backup.main()` — no return value; run as the script's entry point. Logs a successful backup, logs+exits non-zero on backup failure, logs pruning results (or logs+continues on pruning failure).

This task wires the tested functions together; it's thin orchestration and logging, so it's verified by manual smoke test rather than a new unit test (consistent with the spec's Testing section).

- [ ] **Step 1: Implement `main()`**

Replace the `if __name__ == "__main__": pass` placeholder at the bottom of `backup.py` with:

```python
def main():
    try:
        gz_path = create_backup(db.DATABASE, BACKUP_DIR, datetime.now())
        logger.info(f"Backup created: {gz_path}")
    except Exception:
        logger.exception("Backup failed")
        sys.exit(1)

    try:
        deleted = prune_old_backups(BACKUP_DIR, RETENTION_DAYS, datetime.now())
        for path in deleted:
            logger.info(f"Pruned old backup: {path}")
    except Exception:
        logger.exception("Pruning failed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full test suite**

Run: `python -m unittest tests.test_backup -v`
Expected: `OK` (still 6 tests passed — `main()` has no new unit tests, this just confirms the edit didn't break anything).

- [ ] **Step 3: Manual smoke test against the real database**

Run: `python backup.py`
Expected: a log line `Backup created: backups\ruuvi-<today>.db.gz` (or `backups/...` on Linux), and no `Pruning failed` line.

Verify:
```bash
ls backups/
```
Expected: `ruuvi-<today>.db.gz` present, no leftover `.db` file.

Run it a second time immediately and confirm the same filename is reused (still exactly one `ruuvi-<today>.db.gz`, no `.db.gz.gz` or numbered duplicate).

- [ ] **Step 4: Commit**

```bash
git add backup.py
git commit -m "feat: wire up backup.py main() to create and prune daily backups"
```

---

### Task 4: systemd timer/service and deployment docs

**Files:**
- Create: `systemd/ruuvi-backup.service`
- Create: `systemd/ruuvi-backup.timer`
- Modify: `systemd/README.md`

**Interfaces:**
- Consumes: `backup.py` (Task 3) as the executable the service runs; the existing `ruuvi` service user/venv layout already documented in `systemd/README.md` (`/home/ruuvi/ruuvi`, `/home/ruuvi/ruuvi/venv`).
- Produces: nothing consumed by later tasks — this is the last task in the plan.

This task is Pi-specific (systemd doesn't run on the dev machine), so it's verified by documented manual steps rather than an automated test.

- [ ] **Step 1: Create the service unit**

Create `systemd/ruuvi-backup.service`:

```ini
[Unit]
Description=Ruuvi Dashboard - daily database backup
After=network.target

[Service]
Type=oneshot
User=ruuvi
Group=ruuvi
WorkingDirectory=/home/ruuvi/ruuvi
ExecStart=/home/ruuvi/ruuvi/venv/bin/python backup.py
```

- [ ] **Step 2: Create the timer unit**

Create `systemd/ruuvi-backup.timer`:

```ini
[Unit]
Description=Run ruuvi-backup.service daily

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: Document installation in `systemd/README.md`**

Read the current file first:

Run: `cat systemd/README.md` (or open it in an editor)

Add a new section after the existing "## 7. Install and start the services" section (renumber/adjust surrounding step numbers if needed to keep the walkthrough sequential), with this content:

```markdown
## 7a. Install the daily backup timer

```bash
sudo cp /home/ruuvi/ruuvi/systemd/ruuvi-backup.service /home/ruuvi/ruuvi/systemd/ruuvi-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ruuvi-backup.timer
```

This backs up `data/ruuvi.db` into `backups/` once a day (03:00), gzipped,
keeping the last 30 days locally. `Persistent=true` means a missed run (Pi
was off at 03:00) executes on next boot instead of being skipped.

Verify it's scheduled:

```bash
sudo systemctl list-timers ruuvi-backup.timer
```

Trigger one manually to confirm it works end-to-end:

```bash
sudo systemctl start ruuvi-backup.service
sudo systemctl status ruuvi-backup.service
journalctl -u ruuvi-backup.service -n 20
ls -la /home/ruuvi/ruuvi/backups/
```

Expect a `ruuvi-<today>.db.gz` file owned by `ruuvi:ruuvi`.
```

- [ ] **Step 4: Commit**

```bash
git add systemd/ruuvi-backup.service systemd/ruuvi-backup.timer systemd/README.md
git commit -m "docs: add systemd timer for daily database backups"
```

---

## Post-plan follow-up (not part of this plan)

Once this is deployed and confirmed working on the Pi, update
`PROJECT_STATUS.md`'s Phase 10 entry to reflect that local daily backups are
done, and note the remaining Phase 10 sub-projects (off-Pi shipping, health
checks, SD/temperature monitoring) as still open.
