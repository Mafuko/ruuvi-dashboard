# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project vision vs. current state

Full product vision, target architecture, and phase-by-phase roadmap live in `RuuviTag_IoT_Project_Summary_EN.md` — read it for context on where this is headed. In short: a 24/7 RuuviTag (Bluetooth LE sensor) monitor meant to run on a Raspberry Pi 4, with a Flask dashboard exposed to the Internet via Cloudflare Tunnel.

**The current code is an early, minimal implementation, not the target system.** All roadmap checkboxes in that file are still unchecked. Concretely, none of the following exist yet: `requirements.txt`, a `venv`, `static/` assets, systemd service files, Cloudflare Tunnel config, device/user management UI, alerts, CSV export, or an API. Don't assume a roadmap item is implemented — verify against the actual files first.

## Running the app

```
python init_db.py       # one-time: creates ruuvi.db with users/measurements/devices tables
python create_user.py   # prompts for username/password, inserts a user row
python app.py           # runs the Flask dashboard on 0.0.0.0:5000 (debug via config.py)
python collector.py     # BLE collector: listens for RuuviTag broadcasts, writes to db
```

Dependencies (inferred from imports, install via pip as needed — no `requirements.txt` yet): `flask`, `werkzeug`, `ruuvitag_sensor` (collector.py only — requires a BLE-capable host, typically Linux). There's no build system, test suite, or linter in this repo.

## Architecture

- **app.py** — Flask web app. Two routes behind `@login_required` (session-based): `/` (dashboard grid of latest reading per sensor) and `/sensor/<mac>` (last-24h chart data for one sensor). `/login` and `/logout` handle session auth against a single admin credential pulled from `config.py`.
- **collector.py** — standalone async script (not part of the Flask process), meant to run continuously (eventually as its own systemd service). Subscribes to `RuuviTagSensor.get_data_async` and writes each reading to the `measurements` table, filtering by `get_allowed_macs()` from `db.py` — device authorization is DB-driven, not a hardcoded MAC list.
- **db.py** — the authoritative schema/connection module: `get_connection()` (sqlite3 with `Row` factory) and `init_db()` (creates `users`, `devices`, `measurements` tables if missing). Both `app.py` (indirectly, via queries) and `collector.py` depend on this module.
- **init_db.py** — a standalone duplicate of the schema creation in `db.py` (older/manual variant, missing the `battery` column on `measurements`). Prefer `db.py`'s `init_db()` as the source of truth if the schema needs to change; update both if `init_db.py` is kept in sync intentionally.
- **config.py** — currently only defines `DEBUG` and `DATABASE_PATH`. `app.py` also imports `SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD_HASH` from this module, which are not currently defined there — these need to be added locally (and kept out of version control) before `app.py` will start. `DATABASE_PATH` in `config.py` is not currently wired up; `db.py` hardcodes its own path (`<repo>/ruuvi.db`) instead.
- **create_user.py** — has a broken SQL statement (the values are inlined into the query string instead of using the `?` placeholders it also passes); needs fixing before it will run successfully.
- **templates/** — server-rendered Jinja2 + Tailwind (via CDN) + Chart.js (via CDN, on the sensor detail page). No frontend build step. Only `index.html`, `login.html`, `sensor.html` exist so far (the roadmap's `dashboard.html`/`history.html`/`devices.html` split hasn't happened).

## Data model

Three tables in the sqlite3 database (`ruuvi.db`):
- `users` — dashboard login credentials (`password_hash` via werkzeug).
- `devices` — allow-list of sensor MAC addresses with display `name`, used both to label the dashboard and to filter which BLE MACs the collector will persist. The roadmap envisions adding `location` and `active` columns; they don't exist in the current schema.
- `measurements` — time series of `mac, temperature, humidity, pressure, battery, timestamp` readings.

`sensors` is referenced in `app.py`'s dashboard query (`JOIN sensors s ON m.mac = s.mac`) but the schema (in both `db.py` and `init_db.py`) only creates a `devices` table — the join target name is inconsistent with the actual table name.

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
