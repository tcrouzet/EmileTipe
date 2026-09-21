import unittest

from script.dataset.build import (
    DATASET_PROFILES,
    System,
    TCE,
    confirmed_systems,
    manifest_rows,
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

    def test_training_profile_is_balanced_and_has_no_test_split(self):
        profile = DATASET_PROFILES["training"]
        self.assertEqual(
            profile.class_counts,
            {"CONFIRMED": 1_500, "CONTROL": 1_500},
        )
        self.assertEqual(
            profile.class_splits,
            {
                "CONFIRMED": {"train": 1_200, "validation": 300},
                "CONTROL": {"train": 1_200, "validation": 300},
            },
        )

    def test_manifest_rows_uses_the_requested_splits(self):
        systems = [
            System(kepid, "CONFIRMED", ()) for kepid in range(1, 5)
        ] + [
            System(kepid, "CONTROL", ()) for kepid in range(101, 105)
        ]
        rows = manifest_rows(
            systems,
            seed=727,
            class_splits={
                "CONFIRMED": {"train": 3, "validation": 1},
                "CONTROL": {"train": 3, "validation": 1},
            },
        )
        self.assertEqual(sum(row["split"] == "train" for row in rows), 6)
        self.assertEqual(sum(row["split"] == "validation" for row in rows), 2)
        self.assertNotIn("test", {row["split"] for row in rows})


if __name__ == "__main__":
    unittest.main()
