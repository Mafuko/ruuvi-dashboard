# RuuviTag IoT Monitor

## Project Purpose

A 24/7 IoT system for Raspberry Pi 4 that collects Bluetooth LE measurement data from one or more RuuviTag sensors, stores the data in a local database, and provides a modern, mobile-friendly web dashboard for monitoring measurements.

The goal is to make the project a secure and long-lived home server that can also be accessed over the Internet without directly exposing Raspberry Pi ports to the public Internet.

## Technical Environment

- Raspberry Pi 4
- Raspberry Pi OS Lite, 64-bit
- Python 3
- Python virtual environment (`venv`)
- `ruuvitag-sensor`
- Flask
- SQLite
- systemd
- Bluetooth / BLE
- Cloudflare Tunnel for remote access
- Git for version control
- Claude Code as the development tool

## Project Architecture

```text
RuuviTags
    │
    │ Bluetooth LE
    ▼
collector.py
    │
    ▼
SQLite (ruuvi.db)
    │
    ├── devices
    ├── measurements
    └── users
    │
    ▼
Flask / app.py
    │
    ▼
Web Dashboard
    │
    └── Cloudflare Tunnel
             │
             ▼
          Internet
```

## Main Components

### `collector.py`

Responsible for receiving RuuviTag Bluetooth data.

The collector should:

1. listen for RuuviTag BLE broadcasts
2. identify the sensor using its MAC address
3. check the MAC address against the `devices` database table
4. accept data only from registered/active devices
5. store measurements in the `measurements` table
6. continue operating despite individual errors
7. run as a systemd service and start automatically when the Raspberry Pi boots

The collector should no longer use a hardcoded `ALLOWED_MACS` list in `config.py`. Device authorization is managed through the database.

### `db.py`

Contains centralized SQLite database connection handling.

The goal is to provide functions such as:

- `get_connection()`
- `init_db()`
- database configuration and helper functions as needed

Database connections should be handled properly and closed automatically, for example by using Python's `with` context manager.

### `init_db.py`

Initializes the database and creates the required tables.

### `create_user.py`

Creates dashboard users in the database.

Passwords must never be stored in plaintext. Use a secure password hashing solution, such as Werkzeug's password hashing utilities.

### `app.py`

Flask application providing:

- login
- session management
- RuuviTag data display
- historical data
- API endpoints required by the dashboard
- device management
- user management later if needed

## Database

Planned basic structure:

### `devices`

Contains registered RuuviTags.

For example:

- `id`
- `mac`
- `name`
- `location`
- `active`
- `created_at`

The MAC address acts as the sensor identifier.

Example:

```text
id | mac               | name       | location    | active
1  | AA:BB:CC:DD:EE:FF | Living Room| Living Room | 1
2  | 11:22:33:44:55:66 | Bedroom    | Bedroom     | 1
```

### `measurements`

Contains measurement history.

For example:

- `id`
- `mac`
- `timestamp`
- `temperature`
- `humidity`
- `pressure`
- `battery`

The `mac` field connects a measurement to the corresponding device in the `devices` table.

### `users`

Contains dashboard users.

For example:

- `id`
- `username`
- `password_hash`
- `created_at`
- `active`

## Dashboard

The goal is a modern and mobile-friendly user interface.

The main view should contain sensor cards such as:

```text
Living Room
21.4 °C

45.2 %
1012 hPa
2.97 V

Updated 8 seconds ago
```

The dashboard should support multiple RuuviTags simultaneously.

### History

The user can select:

- sensor
- time range
- measurement type

Example time ranges:

- 1 hour
- 6 hours
- 24 hours
- 7 days
- 30 days
- custom

### Multiple Sensors on the Same Chart

An important feature is the ability to display, for example, living room, bedroom, and outdoor sensor temperatures on the same chart.

This makes it easy to compare different locations.

### Other Planned Dashboard Features

- latest measurements
- battery status
- sensor online/offline status
- system status
- collector service status
- database status
- Raspberry Pi uptime
- alerts
- CSV export
- sensor management
- user settings

## UI Style

The goal is a modern SaaS-style interface:

- dark mode as the primary theme
- responsive desktop/tablet/mobile layout
- clear sensor cards
- charts
- icons
- color-coded sensors
- clear navigation
- as little unnecessary UI complexity as possible

Example main navigation:

```text
Overview
History
Devices
Alerts
Settings
Users
Logs
```

## Security

Because the dashboard may be exposed to the Internet, security is an important part of the project.

Planned security measures:

- Raspberry Pi OS Lite
- keep the operating system up to date
- SSH key authentication
- disable SSH password authentication after key-based access has been tested
- firewall
- optionally Fail2ban for SSH
- Flask user authentication
- hashed passwords
- secure session cookies
- CSRF protection where needed
- input validation
- avoid SQL injection by using parameterized queries
- Cloudflare Tunnel for Internet exposure
- do not expose the Raspberry Pi HTTP port directly to the Internet
- regular system and dependency updates
- database backups

Cloudflare Tunnel does not replace operating-system or application security. It is one additional security layer for exposing the service to the Internet.

## systemd

The project uses separate systemd services.

### `ruuvi-collector.service`

Responsible for continuously running the collector.

Goals:

- start at boot
- start after Bluetooth is available
- use the project's virtual environment
- automatically restart after crashes
- run under a restricted user account
- logs should be available through `journalctl`

### `ruuvi-dashboard.service`

Responsible for running the Flask dashboard.

Goals:

- start at boot
- use the project's virtual environment
- restart after crashes
- never run as root
- preferably listen on localhost because Cloudflare Tunnel acts as the external access layer

## Database Performance and SD Card

The Raspberry Pi uses a microSD card as its primary storage medium.

Current plan:

- 128 GB high-quality microSD card
- consider SQLite WAL mode
- indexes especially for `mac` + `timestamp` queries
- automatic cleanup of old data can be implemented later
- regular database backups
- preferably store backups outside the Raspberry Pi

Measurement data grows slowly, so 128 GB is more than sufficient for this project.

## Development Roadmap

### Phase 1 — Clean Raspberry Pi Environment

- [ ] Install Raspberry Pi OS Lite 64-bit
- [ ] Update the operating system
- [ ] Configure SSH
- [ ] Configure WiFi/Ethernet
- [ ] Verify Bluetooth
- [ ] Install Python 3, pip and venv
- [ ] Create project directory
- [ ] Create virtual environment

### Phase 2 — Project Structure

Recommended structure:

```text
ruuvi/
├── app.py
├── collector.py
├── db.py
├── init_db.py
├── create_user.py
├── requirements.txt
├── ruuvi.db
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   ├── history.html
│   └── devices.html
├── static/
│   ├── css/
│   └── js/
├── backups/
└── venv/
```

The structure can later be expanded with directories such as `services/`, `routes/`, `models/`, and `utils/` if the application grows.

### Phase 3 — Database

- [ ] Implement `db.py`
- [ ] Implement `init_db.py`
- [ ] Create `devices`
- [ ] Create `measurements`
- [ ] Create `users`
- [ ] Add indexes
- [ ] Test database CRUD operations
- [ ] Create the first user

### Phase 4 — Collector

- [ ] Implement BLE scanning
- [ ] Test data from one RuuviTag
- [ ] Test multiple RuuviTags
- [ ] Check MAC address against the `devices` table
- [ ] Store data only from active devices
- [ ] Add error handling
- [ ] Add logging
- [ ] Test continuous collector operation

### Phase 5 — Dashboard

- [ ] Implement login
- [ ] Implement session management
- [ ] Implement overview
- [ ] Sensor cards
- [ ] Latest measurements
- [ ] History
- [ ] Charts
- [ ] Multiple sensors on the same chart
- [ ] Responsive UI
- [ ] Dark mode
- [ ] Automatic data refresh

### Phase 6 — Device Management

The dashboard should allow users to:

- add a RuuviTag
- name a RuuviTag
- define its location
- activate/deactivate a device
- view its MAC address
- view the latest measurement
- view battery status

The collector uses the same database to determine which devices are authorized.

### Phase 7 — systemd

- [ ] Create collector service
- [ ] Create dashboard service
- [ ] Enable services at boot
- [ ] Configure restart on failure
- [ ] Test after reboot
- [ ] Test `journalctl` logs

### Phase 8 — Security

- [ ] SSH key authentication
- [ ] Firewall
- [ ] Disable unnecessary services
- [ ] Flask security hardening
- [ ] Secure cookies
- [ ] CSRF protection
- [ ] Rate limiting / login protection
- [ ] User roles if needed
- [ ] Regular updates

### Phase 9 — Cloudflare Tunnel

- [ ] Create Cloudflare account
- [ ] Install `cloudflared`
- [ ] Create tunnel
- [ ] Route tunnel traffic to the dashboard on localhost
- [ ] Use HTTPS
- [ ] Do not expose port 5000 directly to the Internet
- [ ] Consider Cloudflare Access as an additional security layer

### Phase 10 — Reliability

- [ ] Automatic database backups
- [ ] Backup retention policy
- [ ] Monitor SD card usage/health where possible
- [ ] Monitor Raspberry Pi temperature
- [ ] Collector health check
- [ ] Dashboard health check
- [ ] Watchdog if needed
- [ ] UPS later if power outages need to be handled

## Future Development Ideas

### Alerts

Examples:

- temperature too high
- temperature too low
- humidity too high
- battery low
- RuuviTag has not been seen for X minutes

Notification methods:

- email
- Telegram
- push notification
- Discord

### Statistics

- daily min/max/average
- weekly min/max/average
- monthly trends
- sensor comparisons
- rate of temperature change

### External Weather Data

The dashboard could later include:

- outdoor temperature from a weather API
- weather forecast
- precipitation
- atmospheric pressure comparison

This would allow the RuuviTag's outdoor measurements to be compared with weather-service data.

### Energy Monitoring

Other IoT sensors could later be integrated with the Raspberry Pi, for example:

- electricity consumption
- air quality
- CO₂
- motion detection
- light level

The project could eventually evolve into a general home IoT monitoring system.

### API

A REST API could be implemented, for example:

```text
GET /api/devices
GET /api/devices/<id>
GET /api/measurements
GET /api/measurements/<device_id>
GET /api/health
```

The API must be authenticated when it exposes private data.

### Data Export

- CSV
- JSON
- possibly Excel
- possibly automated monthly reports

### SQLite → Time-Series Database

SQLite is sufficient for the initial version.

If the number of measurements or sensors grows significantly, the following could be evaluated later:

- InfluxDB
- PostgreSQL
- TimescaleDB

Do not switch databases before there is a real need.

## Important Development Principles for Claude Code

If any of these does not make sense or you have better idea, mention and hilight it.

1. Do not hardcode RuuviTag MAC addresses in Python code.
2. Use the database for device management and authorization.
3. Never store passwords in plaintext.
4. Do not run Flask or the collector as root.
5. Use parameterized SQL queries.
6. Handle and close SQLite connections correctly.
7. Make changes in small, testable steps.
8. Do not add dependencies without a justified reason.
9. Keep Raspberry Pi resource usage and SD card write activity reasonable.
10. Security must be considered for every new Internet-facing feature.
11. Before making major architectural changes, inspect the current project structure and existing code.
12. Do not assume a file or feature exists — verify it first.
13. Keep documentation up to date when making changes.

## Final Goal

The final system is an easy-to-maintain Raspberry Pi-based home server that:

- collects data from multiple RuuviTags 24/7
- stores measurement history locally
- provides a modern web dashboard
- allows sensor management
- displays real-time and historical data
- runs as systemd-managed services
- automatically recovers from failures
- is protected by user authentication
- can be securely exposed to the Internet through Cloudflare Tunnel
- performs automatic backups
- can later be expanded to monitor other home IoT measurements
