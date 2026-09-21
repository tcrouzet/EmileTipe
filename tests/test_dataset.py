import unittest

from script.dataset.build import (
    System,
    TCE,
    confirmed_systems,
    select_systems,
    unambiguous_systems,
)


class DatasetTest(unittest.TestCase):
    def test_mixed_system_is_excluded(self):
        events = [
            TCE(1, 1, 2.0, 100.0, 2.0, "NTP"),
            TCE(1, 2, 3.0, 100.0, 2.0, "AFP"),
            TCE(2, 1, 4.0, 100.0, 2.0, "NTP"),
        ]
        systems = unambiguous_systems(events, max_period_days=30)
        self.assertEqual(len(systems["AFP"]), 0)
        self.assertEqual([system.kepid for system in systems["NTP"]], [2])

    def test_selection_is_deterministic(self):
        confirmed_events = [
            TCE(kepid, 1, 2.0, 100.0, 2.0, "CONFIRMED")
            for kepid in range(1, 5)
        ]
        candidates = {
            "CONFIRMED": confirmed_systems(confirmed_events, max_period_days=30),
            "CONTROL": [
                System(kepid, "CONTROL", ())
                for kepid in range(101, 105)
            ],
        }
        counts = {"CONFIRMED": 3, "CONTROL": 3}
        first = select_systems(candidates, class_counts=counts, seed=727)
        second = select_systems(candidates, class_counts=counts, seed=727)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)


if __name__ == "__main__":
    unittest.main()
