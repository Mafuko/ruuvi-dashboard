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
