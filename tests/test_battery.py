import unittest

from battery import is_battery_low


class IsBatteryLowTests(unittest.TestCase):
    def test_above_freezing_low_below_2500_mv(self):
        self.assertTrue(is_battery_low(2499, 20.0))
        self.assertFalse(is_battery_low(2500, 20.0))

    def test_zero_degrees_uses_above_freezing_threshold(self):
        self.assertTrue(is_battery_low(2400, 0.0))

    def test_below_freezing_low_below_2300_mv(self):
        self.assertFalse(is_battery_low(2400, -5.0))
        self.assertTrue(is_battery_low(2299, -5.0))
        self.assertFalse(is_battery_low(2300, -5.0))

    def test_minus_twenty_uses_below_freezing_threshold(self):
        self.assertTrue(is_battery_low(2200, -20.0))

    def test_below_minus_twenty_low_below_2000_mv(self):
        self.assertFalse(is_battery_low(2200, -25.0))
        self.assertTrue(is_battery_low(1999, -25.0))

    def test_missing_battery_is_not_low(self):
        self.assertFalse(is_battery_low(None, 20.0))

    def test_missing_temperature_uses_strictest_threshold(self):
        self.assertTrue(is_battery_low(2499, None))
        self.assertFalse(is_battery_low(2500, None))


if __name__ == "__main__":
    unittest.main()
