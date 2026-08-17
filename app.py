import re
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash
from config import SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD_HASH
from datetime import datetime, timedelta, timezone
from db import get_connection
from functools import wraps

RANGE_HOURS = {
    "1h": 1,
    "6h": 6,
    "24h": 24,
    "7d": 24 * 7,
    "30d": 24 * 30,
}
DEFAULT_RANGE = "24h"
METRIC_COLUMNS = {"temperature", "humidity", "pressure"}
MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

def normalize_mac(mac):
    return mac.strip().upper()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def to_iso_utc(timestamp):
    """Converts a 'YYYY-MM-DD HH:MM:SS' sqlite timestamp (UTC) into an ISO 8601 string JS can parse unambiguously."""
    return timestamp.replace(" ", "T") + "Z"

def since_for_range(range_key):
    """Returns a cutoff timestamp in the same 'YYYY-MM-DD HH:MM:SS' format sqlite's
    CURRENT_TIMESTAMP stores, so string comparison in SQL WHERE clauses works correctly."""
    hours = RANGE_HOURS.get(range_key, RANGE_HOURS[DEFAULT_RANGE])
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def latest_readings():
    query = """
        SELECT d.mac, d.name, m.temperature, m.humidity, m.pressure, m.battery, m.timestamp
        FROM measurements m
        JOIN devices d ON m.mac = d.mac
        INNER JOIN (
            SELECT mac, MAX(timestamp) as max_ts
            FROM measurements
            GROUP BY mac
        ) latest
        ON m.mac = latest.mac AND m.timestamp = latest.max_ts
        WHERE d.active = 1
        ORDER BY d.name
    """
    with get_connection() as conn:
        return conn.execute(query).fetchall()

app = Flask(__name__)
app.secret_key = SECRET_KEY

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if (username == ADMIN_USERNAME and
            check_password_hash(ADMIN_PASSWORD_HASH, password)):

            session["logged_in"] = True
            return redirect(url_for("index"))

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    rows = latest_readings()
    data = [
        {**dict(row), "timestamp_iso": to_iso_utc(row["timestamp"])}
        for row in rows
    ]
    return render_template("index.html", data=data)

@app.route("/api/latest")
@login_required
def api_latest():
    rows = latest_readings()
    return jsonify([
        {
            "mac": row["mac"],
            "name": row["name"],
            "temperature": row["temperature"],
            "humidity": row["humidity"],
            "pressure": row["pressure"],
            "battery": row["battery"],
            "timestamp": to_iso_utc(row["timestamp"]),
        }
        for row in rows
    ])

@app.route("/sensor/<mac>")
@login_required
def sensor(mac):
    range_key = request.args.get("range", DEFAULT_RANGE)
    if range_key not in RANGE_HOURS:
        range_key = DEFAULT_RANGE
    since = since_for_range(range_key)

    query = """
        SELECT timestamp, temperature, humidity, pressure
        FROM measurements
        WHERE mac = ? AND timestamp >= ?
        ORDER BY timestamp
    """

    with get_connection() as conn:
        rows = conn.execute(query, (mac, since)).fetchall()
        name = conn.execute(
            "SELECT name FROM devices WHERE mac = ?", (mac,)
        ).fetchone()

    return render_template(
        "sensor.html",
        mac=mac,
        name=name["name"] if name else mac,
        timestamps=[r["timestamp"] for r in rows],
        temperatures=[r["temperature"] for r in rows],
        humidities=[r["humidity"] for r in rows],
        pressures=[r["pressure"] for r in rows],
        ranges=list(RANGE_HOURS.keys()),
        selected_range=range_key
    )

@app.route("/history")
@login_required
def history():
    with get_connection() as conn:
        devices = conn.execute(
            "SELECT mac, name FROM devices WHERE active = 1 ORDER BY name"
        ).fetchall()

    return render_template(
        "history.html",
        devices=devices,
        ranges=list(RANGE_HOURS.keys()),
        default_range=DEFAULT_RANGE
    )

@app.route("/api/history")
@login_required
def api_history():
    macs = [m for m in request.args.get("macs", "").split(",") if m]
    metric = request.args.get("metric", "temperature")
    range_key = request.args.get("range", DEFAULT_RANGE)

    if metric not in METRIC_COLUMNS:
        return jsonify({"error": "invalid metric"}), 400
    if range_key not in RANGE_HOURS:
        range_key = DEFAULT_RANGE
    if not macs:
        return jsonify({"series": []})

    since = since_for_range(range_key)
    placeholders = ",".join("?" for _ in macs)
    # metric is whitelisted against METRIC_COLUMNS above, safe to interpolate as a column name
    query = f"""
        SELECT d.mac, d.name, m.timestamp, m.{metric} as value
        FROM measurements m
        JOIN devices d ON m.mac = d.mac
        WHERE m.mac IN ({placeholders}) AND m.timestamp >= ?
        ORDER BY d.name, m.timestamp
    """

    with get_connection() as conn:
        rows = conn.execute(query, (*macs, since)).fetchall()

    series = {}
    for row in rows:
        entry = series.setdefault(row["mac"], {"mac": row["mac"], "name": row["name"], "points": []})
        entry["points"].append({"t": to_iso_utc(row["timestamp"]), "v": row["value"]})

    return jsonify({"series": list(series.values())})

@app.route("/devices")
@login_required
def devices():
    query = """
        SELECT d.mac, d.name, d.location, d.active,
               m.temperature, m.humidity, m.pressure, m.battery, m.timestamp
        FROM devices d
        LEFT JOIN measurements m
            ON m.mac = d.mac
            AND m.timestamp = (SELECT MAX(timestamp) FROM measurements WHERE mac = d.mac)
        ORDER BY d.name
    """
    with get_connection() as conn:
        rows = conn.execute(query).fetchall()
    return render_template("devices.html", devices=rows)

@app.route("/devices/new", methods=["GET", "POST"])
@login_required
def device_new():
    error = None
    form = {"mac": "", "name": "", "location": ""}

    if request.method == "POST":
        form["mac"] = request.form.get("mac", "")
        form["name"] = request.form.get("name", "").strip()
        form["location"] = request.form.get("location", "").strip()

        mac = normalize_mac(form["mac"])
        if not MAC_RE.match(mac):
            error = "Enter a valid MAC address, e.g. AA:BB:CC:DD:EE:FF"
        elif not form["name"]:
            error = "Name is required"
        else:
            try:
                with get_connection() as conn:
                    conn.execute(
                        "INSERT INTO devices (mac, name, location, active) VALUES (?, ?, ?, 1)",
                        (mac, form["name"], form["location"] or None)
                    )
                    conn.commit()
                return redirect(url_for("devices"))
            except sqlite3.IntegrityError:
                error = f"A device with MAC {mac} already exists"

    return render_template("device_form.html", mode="new", error=error, form=form)

@app.route("/devices/<mac>/edit", methods=["GET", "POST"])
@login_required
def device_edit(mac):
    with get_connection() as conn:
        device = conn.execute("SELECT * FROM devices WHERE mac = ?", (mac,)).fetchone()

    if device is None:
        return redirect(url_for("devices"))

    error = None
    form = {"name": device["name"], "location": device["location"] or ""}

    if request.method == "POST":
        form["name"] = request.form.get("name", "").strip()
        form["location"] = request.form.get("location", "").strip()

        if not form["name"]:
            error = "Name is required"
        else:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE devices SET name = ?, location = ? WHERE mac = ?",
                    (form["name"], form["location"] or None, mac)
                )
                conn.commit()
            return redirect(url_for("devices"))

    return render_template("device_form.html", mode="edit", error=error, form=form, mac=mac)

@app.route("/devices/<mac>/toggle", methods=["POST"])
@login_required
def device_toggle(mac):
    with get_connection() as conn:
        conn.execute("UPDATE devices SET active = NOT active WHERE mac = ?", (mac,))
        conn.commit()
    return redirect(url_for("devices"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
