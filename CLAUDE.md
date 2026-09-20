# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project vision vs. current state

Full product vision, target architecture, and phase-by-phase roadmap live in `RuuviTag_IoT_Project_Summary_EN.md` — read it for context on where this is headed. In short: a 24/7 RuuviTag (Bluetooth LE sensor) monitor meant to run on a Raspberry Pi 4, with a Flask dashboard exposed to the Internet via Cloudflare Tunnel.

The current code already implements a working collector, a multi-page dashboard (overview, per-sensor history, multi-sensor comparison, device management), and a `systemd` deployment path for the Pi — see `PROJECT_STATUS.md` for a living, phase-by-phase snapshot of what's done vs. still ahead (e.g. Cloudflare Tunnel, backups, alerts, CSV export, and a public API are not built yet). Don't assume a roadmap item is implemented — verify against the actual files first, and re-check `PROJECT_STATUS.md` if it's been a while since it was last updated.

## Running the app

See `README.md` for the full first-time setup walkthrough (venv, `config.py`, `init_db.py`). Quick reference once set up:

```
python init_db.py       # one-time: creates data/ruuvi.db with users/devices/measurements tables
python create_user.py   # prompts for username/password, hashes it, inserts a row into `users`
python app.py           # runs the Flask dashboard on 0.0.0.0:5000 (debug via config.py)
python collector.py     # BLE collector: listens for RuuviTag broadcasts, writes to db
```

Dependencies are pinned in `requirements.txt`: `flask`, `werkzeug`, `ruuvitag_sensor` (collector.py only — requires a BLE-capable host, typically Linux), `gunicorn` (production WSGI server for the dashboard, used by `systemd/ruuvi-dashboard.service`). There's no build system or linter in this repo. There is a small stdlib `unittest` suite for `backup.py` — run it with `python -m unittest discover -v`.

## Architecture

- **app.py** — Flask web app, session-based auth via `@login_required`. Routes: `/` (overview grid of latest reading per sensor, auto-refreshed client-side from `/api/latest`), `/sensor/<mac>` (per-sensor chart with selectable range: 1h/6h/24h/7d/30d), `/history` + `/api/history` (overlay multiple sensors/metrics on one chart), `/devices`, `/devices/new`, `/devices/<mac>/edit`, `/devices/<mac>/toggle` (device management), `/login` and `/logout` (session auth checked against `ADMIN_USERNAME`/`ADMIN_PASSWORD_HASH` in `config.py`).
- **collector.py** — standalone async script (not part of the Flask process), meant to run continuously (as its own systemd service — see `systemd/`). Subscribes to `RuuviTagSensor.get_data_async` and writes each reading to the `measurements` table, filtering by `get_allowed_macs()` from `db.py` — device authorization is DB-driven, not a hardcoded MAC list.
- **db.py** — the authoritative schema/connection module: `get_connection()` (sqlite3 with `Row` factory), `init_db()` (creates `users`, `devices`, `measurements` tables plus an index on `measurements(mac, timestamp)` if missing), and `get_allowed_macs()`. Both `app.py` and `collector.py` depend on this module. `DATABASE_PATH` (from `config.py`) is resolved relative to the repo root here.
- **init_db.py** — a thin wrapper that calls `db.init_db()`. `db.py` is the source of truth for the schema.
- **config.py** — gitignored (holds secrets); copy from `config.example.py` to create it. Defines `DEBUG`, `DATABASE_PATH`, `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`.
- **create_user.py** — prompts for username/password, hashes the password with werkzeug, and inserts a row into `users` using parameterized SQL.
- **templates/** — server-rendered Jinja2 + Tailwind (via CDN) + Chart.js (via CDN, on the sensor/history pages). No frontend build step. Files: `index.html`, `login.html`, `sensor.html`, `history.html`, `devices.html`, `device_form.html`.
- **systemd/** — `ruuvi-collector.service`, `ruuvi-dashboard.service` (runs the app via `gunicorn`), and `ruuvi-backup.service`/`ruuvi-backup.timer` (daily, see below), plus `systemd/README.md` with a full Pi deployment walkthrough (service user, venv, secrets, install, verify, reboot test).
- **backup.py** — daily local backup: takes a consistent snapshot of `data/ruuvi.db` via SQLite's backup API (not a raw file copy, since the collector may be writing concurrently), gzips it into `backups/`, and prunes anything older than 30 days. Runs via `systemd/ruuvi-backup.timer`. Covered by `tests/test_backup.py`.

## Data model

Three tables in the sqlite3 database (`data/ruuvi.db`):
- `users` — dashboard login credentials (`password_hash` via werkzeug).
- `devices` — allow-list of sensor MAC addresses (`mac`, `name`, `location`, `active`), used both to label the dashboard and to filter which BLE MACs the collector will persist.
- `measurements` — time series of `mac, temperature, humidity, pressure, battery, timestamp` readings, indexed on `(mac, timestamp)`.

## Development principles (from the project spec)

These apply to any change in this repo, per `RuuviTag_IoT_Project_Summary_EN.md`:

- If any of the following princibles does not make sense or you have better idea, mention it.
- Don't make unnecessary technology changes; preserve the existing working architecture unless there's a clear reason to change it.
- Don't hardcode RuuviTag MAC addresses in Python — device authorization goes through the `devices` table.
- Never store passwords in plaintext; use parameterized SQL queries; handle/close SQLite connections correctly (`with` context managers).
- Neither Flask nor the collector should run as root.
- Make changes in small, testable steps; don't add dependencies without a justified reason.
- Keep Raspberry Pi resource usage and SD card write activity reasonable (this is intended to run 24/7 on a Pi with an SD card).
- Consider security for every new Internet-facing feature (this dashboard is meant to eventually be exposed via Cloudflare Tunnel).
- Don't assume a file or feature exists — verify first; inspect current code before major architectural changes.
