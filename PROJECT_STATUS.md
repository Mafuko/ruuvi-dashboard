# Project Status

Last reviewed: 2026-10-26. This is a working snapshot, not a permanent
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
for the dashboard, and a reboot/restart-on-failure test procedure.

**Deviation found on the real Pi (2026-10-26):** the actual running
deployment is under the regular login user (`mafuko`) at `/home/mafuko/ruuvi`,
not the documented dedicated `ruuvi` service account at `/home/ruuvi/ruuvi`.
This was carried over from an earlier manual setup (predating
`systemd/README.md`'s current walkthrough) and the unit files installed on
the Pi were hand-adapted (`User=`/`Group=`/paths) to match. It works, but is
less isolated than intended — if the dashboard were ever compromised, it'd
have the full permissions of a regular login account rather than a
restricted one. Worth migrating to the documented `ruuvi` account if this Pi
stays long-term, but not urgent. Phase 7's reboot/restart-on-failure test
(README §10) has not yet been re-run against this corrected setup.

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

**Phase 10 (reliability)** — local daily backups done and **confirmed
running on the real Pi** (2026-10-26): manually triggered
`ruuvi-backup.service` and it produced `ruuvi-2026-10-26.db.gz` in
`backups/`, owned by the deployment user, `status=0/SUCCESS`. The timer
itself (`ruuvi-backup.timer`, daily 03:00) is enabled and scheduled. Rest of
the phase not started: shipping backups off-Pi (`backups/` is local-only for
now, by design — see
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

## Bug found during Pi re-deployment (2026-10-26): new devices need a collector restart — fixed

`collector.py` used to load the allowed-MAC list once at startup and never
re-read it, so devices added (or deactivated) in the dashboard had no effect
until `sudo systemctl restart ruuvi-collector.service`. Fixed on branch
`fix-collector-device-reload`: the `AllowedMacs` class in `collector.py`
re-reads the `devices` table at most every 30 seconds
(`ALLOWED_MACS_REFRESH_SECONDS`), logs `Allowed MACs changed: ...` when the
set changes, and keeps the previous list if a reload fails. Covered by
`tests/test_collector.py`.

## Dashboard UX gaps noticed during real-world use (2026-10-26) — done

Fixed on branch `dashboard-ux-gaps` (overview page only):

1. Cards lead with **Location** as the heading, device Name smaller below
   (falls back to Name as heading when no location is set).
2. **Low-battery indicator**: the battery pill (bottom-right) turns amber
   with "Low", using Ruuvi Station's temperature-aware thresholds in
   `battery.py` (<2.5 V at ≥0 °C, <2.3 V down to −20 °C, <2.0 V below),
   covered by `tests/test_battery.py`. Also fixed the battery display: the
   library reports millivolts, which the old card printed as e.g.
   "2995.00 V"; it now shows "3.00 V".
3. **Stale-data indicator**: a card with no reading for over 1 hour fades to
   gray and shows an amber "No data · Nh" (or "Nd") tag. Computed in the
   browser, so it updates live while the page is open.

Not covered: the per-sensor and Devices pages don't show these indicators;
user-configurable thresholds belong to per-device alerting (below).

## Feature request: per-device alerting (2026-10-26)

Not built yet — this is the roadmap's "alerts" item, still unscoped beyond
this note. Requested shape:

- Configurable per device: pick which collected metric it's based on
  (temperature, humidity, pressure, battery) and a threshold for when it
  should alert.
- Visual: an alerting device should be highlighted on the **Overview** page.
- Notification: the Pi itself should push some kind of notification out
  (not just a passive dashboard highlight) when a device is alerting —
  mechanism (push service, email, something else) still to be decided.

Needs a brainstorming/design pass before implementation (schema for
thresholds, where the check runs — collector vs. a separate checker,
notification delivery mechanism, etc.).

## Suggested next steps

Roughly in order of what unblocks real-world use vs. what's polish:

1. ~~Fix the collector reload bug~~ — done (branch
   `fix-collector-device-reload`); deploy to the Pi with `git pull` +
   `sudo systemctl restart ruuvi-collector.service`.
2. **Decide the collector's log-spam fix** — throttle unauthorized-MAC
   warnings or switch to `get_data_async(macs=...)`. Already scoped in the
   roadmap; small, contained change.
3. **Resolve the login/`users` table gap above** before building anything
   else on top of auth.
4. **CSRF protection** on the device-management and login forms — needed
   before this is Internet-facing at all (Phase 8).
5. **Cloudflare Tunnel** (Phase 9) — the actual "expose to the Internet"
   step; do this only after #4.
6. ~~Dashboard UX gaps~~ — done (branch `dashboard-ux-gaps`); deploy to
   the Pi with `git pull` + `sudo systemctl restart ruuvi-dashboard.service`.
7. Ship backups off-Pi, now that local daily backups are confirmed working
   on real hardware.
8. Migrate the Pi deployment from the `mafuko` user to the documented
   dedicated `ruuvi` service account, and re-run Phase 7's reboot/
   restart-on-failure test against that corrected setup.
9. **Per-device alerting** (see above) — bigger feature, needs a
   brainstorming/design pass before implementation.
