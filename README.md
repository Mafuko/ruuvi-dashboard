# RuuviTag IoT Monitor

A 24/7 RuuviTag (Bluetooth LE sensor) monitor: a `collector.py` script writes
readings into SQLite, and a Flask dashboard (`app.py`) displays them. Target
deployment is a Raspberry Pi 4, eventually exposed to the Internet via
Cloudflare Tunnel. Full product vision and phase-by-phase roadmap live in
[RuuviTag_IoT_Project_Summary_EN.md](RuuviTag_IoT_Project_Summary_EN.md); day-to-day
where-things-stand notes live in [PROJECT_STATUS.md](PROJECT_STATUS.md).

This file is for how do I get this running.

## One-time setup (any machine)

```bash
python -m venv venv

# activate it:
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux / Raspberry Pi

pip install -r requirements.txt
```

Then create your local secrets file (gitignored, never committed):

```bash
cp config.example.py config.py     # Windows: copy config.example.py config.py
```

Edit `config.py` and fill in:

- `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- `ADMIN_USERNAME` — whatever you want to log in with
- `ADMIN_PASSWORD_HASH` — generate with
  `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"`

> Login currently checks the request against these two `config.py` values
> directly — see [PROJECT_STATUS.md](PROJECT_STATUS.md) for why `create_user.py`
> and the `users` table aren't actually wired into login yet.

Then create the database (creates `data/ruuvi.db` with `users`/`devices`/`measurements` tables):

```bash
python init_db.py
```

## Running the dashboard (works on any machine, no BLE needed)

```bash
venv\Scripts\activate      # if not already active
python app.py
```

Open `http://localhost:5000`, log in with the admin credentials from
`config.py`, then go to **Devices → Add device** and register the MAC
address(es) of your RuuviTag(s) — the collector only stores data from MACs
registered here.

## Running the collector (needs a BLE-capable Linux host — i.e. the Pi)

```bash
python collector.py
```

This listens for RuuviTag BLE broadcasts and writes readings into
`measurements` for any MAC present and active in the `devices` table.
It won't do anything useful on a machine without Bluetooth hardware/drivers
that `ruuvitag_sensor` can use (in practice: the Raspberry Pi, not this dev
machine).

## Deploying to the Raspberry Pi as systemd services

Full step-by-step instructions (service user, venv, secrets, `systemd`
units, verification, reboot test) are already written up in
[systemd/README.md](systemd/README.md) — follow that once the code is on
the Pi. Short version: `sudo systemctl enable --now ruuvi-collector.service
ruuvi-dashboard.service`, then `journalctl -u <service> -f` to watch logs.

## Where things live

| Thing | Location |
|---|---|
| SQLite database | `data/ruuvi.db` (gitignored; path set by `DATABASE_PATH` in `config.py`) |
| Secrets | `config.py` (gitignored — copy from `config.example.py`) |
| Backups | `backups/` (directory exists, nothing automated writes here yet) |
| systemd units | `systemd/ruuvi-collector.service`, `systemd/ruuvi-dashboard.service` |
| Templates | `templates/*.html` (Jinja2 + Tailwind CDN + Chart.js CDN, no build step) |

## Cheat sheet

```bash
python init_db.py       # one-time: create the database/tables
python app.py            # run the dashboard dev server on 0.0.0.0:5000
python collector.py      # run the BLE collector (Pi/BLE host only)
```

There's no test suite, linter, or build step in this repo.
