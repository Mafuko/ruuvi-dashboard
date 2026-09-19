# Database Backups (Phase 10, part 1) — Design

Status: approved, ready for implementation planning.

## Purpose

The Pi runs `collector.py` 24/7 writing to `data/ruuvi.db` on the SD card,
with no backup in place. This is the first sub-project of roadmap Phase 10
(reliability): automated, local daily backups of the measurement database.
Off-Pi shipping and other Phase 10 items (health checks, SD/temperature
monitoring, watchdog) are explicitly out of scope — separate sub-projects.

## Scope

In scope:
- Daily, automated, consistent snapshot of `data/ruuvi.db` into `backups/`.
- 30-day local retention (older snapshots pruned automatically).
- Gzip compression of each snapshot.
- Runs via `systemd` on the Pi, consistent with the collector/dashboard.

Out of scope (future sub-projects, not this one):
- Shipping backups off the Pi (NAS/cloud/remote host).
- Backing up code — code lives in GitHub, not part of this design.
- Restore tooling/automation (restore is a manual `gunzip` + file swap for now).
- Health checks, SD card/temperature monitoring, watchdog, UPS.

## Components

### `backup.py` (new, repo root)

Follows the existing style of `init_db.py` / `create_user.py`: a small,
directly-runnable script, no new dependencies (uses only stdlib `sqlite3`,
`gzip`, `pathlib`, `logging`, plus this repo's `db.py`).

- `create_backup()`:
  1. Opens the live database via `db.get_connection()`.
  2. Uses SQLite's `Connection.backup()` API to write a consistent snapshot
     to `backups/ruuvi-YYYY-MM-DD.db` (date from the run time). Using the
     backup API rather than a plain file copy avoids grabbing a
     half-written file while the collector is actively writing.
  3. Gzips that file to `ruuvi-YYYY-MM-DD.db.gz` and removes the
     uncompressed `.db` copy.
  4. Filename is date-only (no time component), so re-running on the same
     day overwrites the same file rather than erroring — this makes manual
     re-runs and testing safe/idempotent.
- `prune_old_backups(days=30)`: deletes any `backups/*.db.gz` whose
  filename date is older than `days`. A pruning failure (e.g. one bad file)
  must not prevent that day's backup from having been created — pruning
  runs after and independently of `create_backup()`.
- `main()`: runs `create_backup()` then `prune_old_backups()`, logging via
  the same `logging.basicConfig` pattern `collector.py` already uses
  (timestamped INFO/ERROR lines). On failure in `create_backup()`, logs the
  exception and exits non-zero so the systemd run shows as failed.
- Runnable directly (`python backup.py`) on any machine, including this
  Windows dev machine — no BLE/Pi-specific dependency.

### `systemd/ruuvi-backup.service` (new)

- `Type=oneshot`.
- `User=ruuvi`, `Group=ruuvi` (the existing restricted service account).
- `WorkingDirectory=/home/ruuvi/ruuvi`.
- `ExecStart=/home/ruuvi/ruuvi/venv/bin/python backup.py`.
- No `Restart=` needed (oneshot, triggered by the timer, not meant to loop).

### `systemd/ruuvi-backup.timer` (new)

- `OnCalendar=daily` (specific time, e.g. `03:00`, chosen to avoid overlap
  with any dashboard/collector load patterns — exact time is an
  implementation detail, not load-bearing).
- `Persistent=true` — if the Pi was off at the scheduled time, the backup
  runs on next boot instead of being silently skipped.
- `WantedBy=timers.target`.

### `systemd/README.md`

Add a short section documenting installing/enabling
`ruuvi-backup.timer` alongside the existing collector/dashboard service
install steps, and how to check it ran
(`systemctl list-timers`, `journalctl -u ruuvi-backup.service`).

## Data flow

```
systemd timer (daily, 03:00)
    │
    ▼
ruuvi-backup.service (oneshot) → python backup.py
    │
    ├─ create_backup()
    │    ├─ db.get_connection() → live data/ruuvi.db
    │    ├─ sqlite3 .backup() → backups/ruuvi-YYYY-MM-DD.db
    │    ├─ gzip → backups/ruuvi-YYYY-MM-DD.db.gz
    │    └─ remove uncompressed .db
    │
    └─ prune_old_backups(30)
         └─ delete backups/*.db.gz older than 30 days
```

## Error handling

- `create_backup()` failure (e.g. DB locked, disk full): logged with
  exception detail, `main()` exits non-zero. Visible via
  `systemctl status ruuvi-backup.service` and `journalctl`.
- `prune_old_backups()` failure on an individual file: log and continue
  pruning the rest rather than aborting; must never affect whether that
  day's backup counts as having succeeded.
- No retry logic — `Persistent=true` on the timer already recovers from
  "Pi was off"; a failed run surfaces in logs for manual attention rather
  than silently retrying.

## Testing

- Run `python backup.py` manually (on this dev machine or the Pi) against
  the existing `data/ruuvi.db` and confirm a `backups/ruuvi-<today>.db.gz`
  appears and no `.db` file is left behind.
- Run it twice in a row same day and confirm the second run overwrites
  cleanly (no error, no duplicate).
- Create/rename a few `backups/*.db.gz` with dates >30 days in the past
  and confirm `prune_old_backups()` removes exactly those, not
  recent ones.
- On the Pi: install the timer/service, confirm `systemctl list-timers`
  shows the next scheduled run, and verify a manual
  `systemctl start ruuvi-backup.service` produces a backup file owned by
  `ruuvi`.

## Open items for later (explicitly not this sub-project)

- Shipping backups off-Pi.
- A documented/scripted restore procedure.
- Alerting if backups stop succeeding.
