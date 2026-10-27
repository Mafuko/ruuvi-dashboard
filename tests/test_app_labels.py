import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import db
from app import app


class DeviceLabelTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(db, "DATABASE", Path(tmp.name) / "test.db")
        patcher.start()
        self.addCleanup(patcher.stop)

        db.init_db()
        with db.get_connection() as conn:
            conn.executemany(
                "INSERT INTO devices (mac, name, location, active) VALUES (?, ?, ?, 1)",
                [
                    ("AA:00:00:00:00:01", "Ruuvi 1", "Sauna"),
                    ("AA:00:00:00:00:02", "Ruuvi 2", None),
                    ("AA:00:00:00:00:03", "Ruuvi 3", "Balcony"),
                ],
            )
            conn.executemany(
                "INSERT INTO measurements (mac, temperature) VALUES (?, ?)",
                [("AA:00:00:00:00:01", 80.0), ("AA:00:00:00:00:02", 20.0), ("AA:00:00:00:00:03", -4.0)],
            )

        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True

    def test_overview_cards_sorted_by_location_or_name(self):
        macs = [r["mac"] for r in self.client.get("/api/latest").get_json()]
        self.assertEqual(macs, ["AA:00:00:00:00:03", "AA:00:00:00:00:02", "AA:00:00:00:00:01"])

    def test_sensor_page_leads_with_location_and_shows_name(self):
        html = self.client.get("/sensor/AA:00:00:00:00:03").get_data(as_text=True)
        self.assertRegex(html, r"<h1[^>]*>\s*Balcony\s*</h1>")
        self.assertIn("Ruuvi 3", html)
        self.assertIn("<title>Balcony</title>", html)

    def test_sensor_page_without_location_uses_name_as_heading(self):
        html = self.client.get("/sensor/AA:00:00:00:00:02").get_data(as_text=True)
        self.assertRegex(html, r"<h1[^>]*>\s*Ruuvi 2\s*</h1>")
        self.assertEqual(len(re.findall("Ruuvi 2", html)), 2)  # heading + <title>, no subtitle

    def test_sensor_page_for_unknown_device_uses_mac(self):
        html = self.client.get("/sensor/FF:00:00:00:00:99").get_data(as_text=True)
        self.assertRegex(html, r"<h1[^>]*>\s*FF:00:00:00:00:99\s*</h1>")


if __name__ == "__main__":
    unittest.main()
