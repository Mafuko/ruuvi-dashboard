# Project Status

Last reviewed: 2026-09-20. This is a working snapshot, not a permanent
record — re-check against actual code/files before trusting it if much time
has passed, per the "don't assume, verify" principle in
[CLAUDE.md](CLAUDE.md). Roadmap phase numbers refer to
[RuuviTag_IoT_Project_Summary_EN.md](RuuviTag_IoT_Project_Summary_EN.md);
its checkboxes are all still unchecked even though several phases are
substantially implemented in code — the checkboxes haven't been kept in
sync with the work.

## Where things actually stand

**Phase 1 (clean Pi environment)** — can't be verified from this repo;
status depends on the Pi itself. The roadmap's "Known concern (found during
Pi setup/testing)" note (added to the collector section) implies the
collector has already been run on real Pi hardware against real RuuviTags.

**Phase 2 (project structure)** — done, and slightly ahead of the roadmap's
sketch: also has `config.example.py`, `data/`, `backups/`, and `systemd/`,
none of which were in the original planned tree.

**Phase 3 (database)** — implemented. `db.py` creates `users`, `devices`
(with `location`/`active` columns — the roadmap treats those as a future
addition, but they already exist), and `measurements` (including `battery`),
plus an index on `(mac, timestamp)`. `init_db.py` is now a thin wrapper
around `db.init_db()`, not a stale duplicate schema.

**Phase 4 (collector)** — implemented: filters against `get_allowed_macs()`,
error-handles and logs per-reading failures without crashing, keeps running.
One open item is already tracked in the roadmap doc itself: unauthorized/
unregistered nearby MACs log a warning on *every* BLE advertisement (every
few seconds) instead of being throttled, and `get_data_async()` could
instead be called with `macs=list(allowed_macs)` to filter at the library
level rather than after the fact.

**Phase 5 (dashboard)** — implemented: login/session, overview grid
(`index.html`, dark theme, auto-refreshes every 30s via `/api/latest` plus a
live "updated Ns ago" ticker), per-sensor detail page with range selector,
and a `history.html` page that overlays multiple sensors/metrics on one
Chart.js chart via `/api/history`. This covers the roadmap's "multiple
sensors on the same chart" feature.

**Phase 6 (device management)** — implemented: `/devices` list,
`/devices/new`, `/devices/<mac>/edit`, `/devices/<mac>/toggle` (activate/
deactivate). MAC input is validated and normalized server-side.

**Phase 7 (systemd)** — unit files and a detailed deployment walkthrough
exist (`systemd/ruuvi-collector.service`, `systemd/ruuvi-dashboard.service`,
`systemd/README.md`), including a restricted `ruuvi` service user, `gunicorn`
for the dashboard, and a reboot/restart-on-failure test procedure. Whether
this has actually been run through end-to-end on the Pi isn't verifiable
from the repo alone.

**Phase 8 (security)** — partial. Passwords are hashed, sessions are
Flask's signed cookies with a real `SECRET_KEY`, SQL is parameterized
throughout. **Not yet done:** CSRF protection (no tokens on any POST form —
`/devices/new`, `/devices/<mac>/edit`, `/devices/<mac>/toggle`, `/login` are
all unprotected), rate limiting / login-attempt protection, and the
`users`-table login path described below.

**Phase 9 (Cloudflare Tunnel)** — not started. No `cloudflared` config in
the repo. The dashboard service still binds `0.0.0.0:5000` rather than
`127.0.0.1` — `systemd/README.md` notes this is intentional until the
tunnel exists, and should be revisited once it does.

**Phase 10 (reliability)** — local daily backups done; the rest of the phase
is not started. `backup.py` takes a consistent gzip snapshot of
`data/ruuvi.db` via SQLite's backup API (never a raw file copy, since the
collector may write concurrently) and prunes anything older than 30 days;
`systemd/ruuvi-backup.timer` runs it daily. Not yet done: shipping backups
off-Pi (`backups/` is local-only for now, by design — see
`docs/superpowers/specs/2026-09-19-database-backups-design.md`), a
documented/scripted restore procedure, alerting if backups stop succeeding,
health checks, and SD card/temperature monitoring.

## A gap worth knowing about: login vs. the `users` table

`create_user.py` works (inserts a hashed-password row into `users`), but
`app.py`'s `/login` route doesn't query that table at all — it checks the
submitted credentials directly against `ADMIN_USERNAME` /
`ADMIN_PASSWORD_HASH` in `config.py`. So today there's effectively one
hardcoded admin login, and the `users` table (and `create_user.py`) is dead
code from the app's point of view. Worth deciding: is multi-user login
actually needed, or was `users` premature scaffolding for something the
single-admin model already covers? If multi-user login is wanted, `/login`
needs to look the username up in `users` instead of `config.py`.

## Suggested next steps

Roughly in order of what unblocks real-world use vs. what's polish:

1. **Decide the collector's log-spam fix** — throttle unauthorized-MAC
   warnings or switch to `get_data_async(macs=...)`. Already scoped in the
   roadmap; small, contained change.
2. **Resolve the login/`users` table gap above** before building anything
   else on top of auth.
3. **CSRF protection** on the device-management and login forms — needed
   before this is Internet-facing at all (Phase 8).
4. **Cloudflare Tunnel** (Phase 9) — the actual "expose to the Internet"
   step; do this only after #3.
5. Confirm the backup timer actually runs on the Pi as documented
   (`systemd/README.md` §8) — deployed from this repo's history but not yet
   confirmed running on real hardware. Ship backups off-Pi as a follow-up
   once local backups are confirmed working.
6. Confirm Phase 7's reboot/restart-on-failure test has actually been run
   on the Pi, if it hasn't already.
