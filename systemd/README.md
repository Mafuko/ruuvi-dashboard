# Deploying the systemd services

These steps run on the Raspberry Pi itself — none of this can be tested from
a dev machine without systemd/BlueZ. Run everything below over SSH on the Pi.

## 1. Create the restricted service user

```bash
sudo useradd --system --home-dir /home/ruuvi --create-home --shell /usr/sbin/nologin ruuvi
sudo usermod -aG bluetooth ruuvi
```

`ruuvi` is a system account with no login shell — it can't be SSH'd into or
used interactively. It's added to the `bluetooth` group because the collector
uses BlueZ's D-Bus API (via the `bleak` backend, the default for
`ruuvitag_sensor` on all platforms) rather than raw HCI sockets, so it
shouldn't need root or special capabilities to scan — group membership is
normally enough on Raspberry Pi OS.

If the collector logs D-Bus permission errors anyway, check
`/etc/dbus-1/system.d/bluetooth.conf` for the policy your OS version ships,
or as a fallback grant raw capabilities directly to the venv's interpreter:
`sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f /home/ruuvi/ruuvi/venv/bin/python3)`
(you'll need to redo this if the venv is ever recreated).

## 2. Get the code onto the Pi

Copy the project to `/home/ruuvi/ruuvi` — via `git clone` if you've pushed
this repo to a remote, or `scp`/`rsync` otherwise. Then fix ownership:

```bash
sudo chown -R ruuvi:ruuvi /home/ruuvi/ruuvi
```

## 3. Create the venv and install dependencies

```bash
sudo -u ruuvi python3 -m venv /home/ruuvi/ruuvi/venv
sudo -u ruuvi /home/ruuvi/ruuvi/venv/bin/pip install -r /home/ruuvi/ruuvi/requirements.txt
```

## 4. Configure secrets

`config.py` is gitignored, so it won't come across with the code copy —
create it directly on the Pi:

```bash
sudo -u ruuvi cp /home/ruuvi/ruuvi/config.example.py /home/ruuvi/ruuvi/config.py
sudo -u ruuvi nano /home/ruuvi/ruuvi/config.py
```

Set a real `SECRET_KEY` (e.g. `python3 -c "import secrets; print(secrets.token_hex(32))"`)
and your real `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH`
(`venv/bin/python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('yourpassword'))"`).

## 5. Initialize the database

```bash
sudo -u ruuvi /home/ruuvi/ruuvi/venv/bin/python /home/ruuvi/ruuvi/init_db.py
```

## 6. Register devices

Once the dashboard is running (next step), log in and add your RuuviTags
under **Devices** — the collector only accepts data from MACs registered
there.

## 7. Install and start the services

```bash
sudo cp /home/ruuvi/ruuvi/systemd/ruuvi-collector.service /home/ruuvi/ruuvi/systemd/ruuvi-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ruuvi-collector.service ruuvi-dashboard.service
```

## 8. Verify

```bash
sudo systemctl status ruuvi-collector.service
sudo systemctl status ruuvi-dashboard.service
journalctl -u ruuvi-collector.service -f
journalctl -u ruuvi-dashboard.service -f
```

The dashboard should be reachable at `http://<pi-ip>:5000`.

## 9. Test restart-on-failure and boot survival

```bash
sudo systemctl kill -s SIGKILL ruuvi-collector.service   # should restart within ~5s
sudo reboot
# after it comes back up:
sudo systemctl status ruuvi-collector.service ruuvi-dashboard.service
```

## Notes

- If the deployment path or username differs from `/home/ruuvi/ruuvi` /
  `ruuvi`, edit `WorkingDirectory`, `ExecStart`, `User`, and `Group` in both
  `.service` files before copying them to `/etc/systemd/system/`.
- The dashboard still binds `0.0.0.0:5000` (LAN-reachable) rather than
  `127.0.0.1` — intentional for now since Cloudflare Tunnel (Phase 9) isn't
  set up yet. Revisit this once it is.
