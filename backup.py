import gzip
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

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
    if not source_db.exists():
        raise FileNotFoundError(f"Source database not found: {source_db}")

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


if __name__ == "__main__":
    pass
