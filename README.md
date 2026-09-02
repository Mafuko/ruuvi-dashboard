# RuuviTag IoT Monitor

## Project Purpose

A 24/7 IoT system for Raspberry Pi 4 that collects Bluetooth LE measurement data from one or more RuuviTag sensors, stores the data in a local database, and provides a modern, mobile-friendly web dashboard for monitoring measurements.

The goal is to make the project a secure and long-lived home server that can also be accessed over the Internet without directly exposing Raspberry Pi ports to the public Internet.

This is still work in progress.

## Next to do

- Try out with all available RuuviTags.
- Improve the Dashboard.

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
