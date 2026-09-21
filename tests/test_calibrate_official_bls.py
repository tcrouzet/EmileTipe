import unittest

from script.calibrate_official_bls import calibrate


class CalibrateOfficialBLSTest(unittest.TestCase):
    def test_selects_threshold_maximizing_f1(self):
        results = [
            {"label": 2, "score": 10.0},
            {"label": 1, "score": 8.0},
            {"label": 2, "score": 7.0},
            {"label": 1, "score": 1.0},
        ]
        result = calibrate(results)
        self.assertEqual(result["threshold"], 7.0)
        self.assertEqual(result["true_positive"], 2)
        self.assertEqual(result["false_positive"], 1)


if __name__ == "__main__":
    unittest.main()
