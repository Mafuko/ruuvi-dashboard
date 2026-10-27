import unittest

from collector import AllowedMacs, UnregisteredLogThrottle


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeLoader:
    def __init__(self, macs):
        self.macs = set(macs)
        self.calls = 0
        self.fail = False

    def __call__(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("database is locked")
        return set(self.macs)


class AllowedMacsTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.loader = FakeLoader({"AA:AA:AA:AA:AA:01"})
        self.allowed = AllowedMacs(self.loader, refresh_seconds=30, clock=self.clock)

    def test_loads_macs_on_creation(self):
        self.assertEqual(self.allowed.get(), {"AA:AA:AA:AA:AA:01"})

    def test_does_not_reload_before_interval(self):
        self.loader.macs.add("AA:AA:AA:AA:AA:02")
        self.clock.now = 29
        self.assertEqual(self.allowed.get(), {"AA:AA:AA:AA:AA:01"})
        self.assertEqual(self.loader.calls, 1)

    def test_picks_up_added_device_after_interval(self):
        self.loader.macs.add("AA:AA:AA:AA:AA:02")
        self.clock.now = 30
        with self.assertLogs("collector", level="INFO") as logs:
            self.assertEqual(self.allowed.get(), {"AA:AA:AA:AA:AA:01", "AA:AA:AA:AA:AA:02"})
        self.assertIn("added ['AA:AA:AA:AA:AA:02']", logs.output[0])

    def test_drops_deactivated_device_after_interval(self):
        self.loader.macs.clear()
        self.clock.now = 30
        with self.assertLogs("collector", level="INFO") as logs:
            self.assertEqual(self.allowed.get(), set())
        self.assertIn("removed ['AA:AA:AA:AA:AA:01']", logs.output[0])

    def test_failed_reload_keeps_previous_macs(self):
        self.loader.fail = True
        self.clock.now = 30
        with self.assertLogs("collector", level="ERROR"):
            self.assertEqual(self.allowed.get(), {"AA:AA:AA:AA:AA:01"})

    def test_failed_reload_retries_after_next_interval(self):
        self.loader.fail = True
        self.clock.now = 30
        with self.assertLogs("collector", level="ERROR"):
            self.allowed.get()
        self.loader.fail = False
        self.loader.macs.add("AA:AA:AA:AA:AA:02")
        self.clock.now = 60
        with self.assertLogs("collector", level="INFO"):
            self.assertIn("AA:AA:AA:AA:AA:02", self.allowed.get())


class UnregisteredLogThrottleTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.throttle = UnregisteredLogThrottle(interval_seconds=3600, clock=self.clock)

    def test_logs_first_sighting(self):
        self.assertTrue(self.throttle.should_log("AA:AA:AA:AA:AA:01"))

    def test_suppresses_repeats_within_interval(self):
        self.throttle.should_log("AA:AA:AA:AA:AA:01")
        self.clock.now = 3599
        self.assertFalse(self.throttle.should_log("AA:AA:AA:AA:AA:01"))

    def test_logs_again_after_interval(self):
        self.throttle.should_log("AA:AA:AA:AA:AA:01")
        self.clock.now = 3600
        self.assertTrue(self.throttle.should_log("AA:AA:AA:AA:AA:01"))
        self.clock.now = 3601
        self.assertFalse(self.throttle.should_log("AA:AA:AA:AA:AA:01"))

    def test_tracks_each_mac_separately(self):
        self.throttle.should_log("AA:AA:AA:AA:AA:01")
        self.clock.now = 10
        self.assertTrue(self.throttle.should_log("AA:AA:AA:AA:AA:02"))


if __name__ == "__main__":
    unittest.main()
