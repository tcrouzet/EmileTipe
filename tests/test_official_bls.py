import random
import unittest

from script.bls.official import official_box_least_squares


class OfficialBLSTest(unittest.TestCase):
    def test_recovers_synthetic_transit_with_gap(self):
        random.seed(727)
        times = [index * 0.02 for index in range(2_000)]
        times = [time for time in times if not 12.0 < time < 14.0]
        flux = [
            1.0
            - (0.02 if time % 2.0 < 0.16 else 0.0)
            + random.gauss(0.0, 0.002)
            for time in times
        ]
        result = official_box_least_squares(times, flux, n_periods=3_000)
        self.assertLess(abs(result.period_days - 2.0), 0.02)
        self.assertGreater(result.depth_snr, 7.0)


if __name__ == "__main__":
    unittest.main()
