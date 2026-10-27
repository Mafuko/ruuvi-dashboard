import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import db
from app import app


class HistoryLabelTests(unittest.TestCase):
    def setUp(self):
        # db.get_connection()'s `with` block commits but doesn't close, so on Windows
        # the temp DB can still be open at cleanup time.
        tmp = TemporaryDirectory(ignore_cleanup_errors=True)
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
            conn.commit()

        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True

    def test_sensor_picker_shows_location_or_name_in_label_order(self):
        html = self.client.get("/history").get_data(as_text=True)
        balcony, ruuvi2, sauna = html.find(">Balcony<"), html.find(">Ruuvi 2<"), html.find(">Sauna<")
        self.assertTrue(-1 < balcony < ruuvi2 < sauna, "expected Balcony, Ruuvi 2, Sauna in that order")
        self.assertNotIn(">Ruuvi 1<", html)
        self.assertNotIn(">Ruuvi 3<", html)

    def test_api_history_labels_series_with_location_or_name(self):
        macs = "AA:00:00:00:00:01,AA:00:00:00:00:02,AA:00:00:00:00:03"
        series = self.client.get(f"/api/history?macs={macs}&metric=temperature&range=1h").get_json()["series"]
        self.assertEqual([s["label"] for s in series], ["Balcony", "Ruuvi 2", "Sauna"])


if __name__ == "__main__":
    unittest.main()
