import asyncio
import logging
from ruuvitag_sensor.ruuvi import RuuviTagSensor
from db import init_db, get_allowed_macs, get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("collector")

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

    # 2️⃣ Fetch allowed MAC addresses once into memory
    allowed_macs = get_allowed_macs()
    logger.info(f"Allowed MACs: {allowed_macs}")

    logger.info("Collector running...")

    # 3️⃣ Start receiving RuuviTag data
    async for mac, data in RuuviTagSensor.get_data_async():
        if mac not in allowed_macs:
            logger.warning(f"Unauthorized MAC: {mac} - skipping")
            continue

        try:
            save_to_db(mac, data)
        except Exception:
            logger.exception(f"Failed to save reading from {mac} - skipping")

if __name__ == "__main__":
    asyncio.run(main())
