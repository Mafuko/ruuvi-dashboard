import asyncio
import logging
import time
from ruuvitag_sensor.ruuvi import RuuviTagSensor
from db import init_db, get_allowed_macs, get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("collector")

ALLOWED_MACS_REFRESH_SECONDS = 30


class AllowedMacs:
    """Allowed-MAC set re-read from the devices table periodically, so devices
    added or deactivated in the dashboard take effect without a restart."""

    def __init__(self, loader, refresh_seconds, clock=time.monotonic):
        self._loader = loader
        self._refresh_seconds = refresh_seconds
        self._clock = clock
        self._macs = loader()
        self._loaded_at = clock()

    def get(self):
        if self._clock() - self._loaded_at >= self._refresh_seconds:
            self._reload()
        return self._macs

    def _reload(self):
        self._loaded_at = self._clock()
        try:
            macs = self._loader()
        except Exception:
            logger.exception("Failed to reload allowed MACs - keeping previous list")
            return
        added, removed = macs - self._macs, self._macs - macs
        if added or removed:
            logger.info(f"Allowed MACs changed: added {sorted(added)}, removed {sorted(removed)}")
        self._macs = macs

def save_to_db(mac, data):
    """Saves a measurement to the database."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO measurements
            (mac, temperature, humidity, pressure, battery)
            VALUES (?, ?, ?, ?, ?)
        """, (
            mac,
            data.get("temperature"),
            data.get("humidity"),
            data.get("pressure"),
            data.get("battery")
        ))
        conn.commit()

async def main():
    # 1️⃣ Ensure tables are created
    init_db()

    # 2️⃣ Load allowed MAC addresses (refreshed periodically from the devices table)
    allowed_macs = AllowedMacs(get_allowed_macs, ALLOWED_MACS_REFRESH_SECONDS)
    logger.info(f"Allowed MACs: {allowed_macs.get()}")

    logger.info("Collector running...")

    # 3️⃣ Start receiving RuuviTag data
    async for mac, data in RuuviTagSensor.get_data_async():
        if mac not in allowed_macs.get():
            logger.warning(f"Unauthorized MAC: {mac} - skipping")
            continue

        try:
            save_to_db(mac, data)
        except Exception:
            logger.exception(f"Failed to save reading from {mac} - skipping")

if __name__ == "__main__":
    asyncio.run(main())
