import math
import random
import unittest

from script.bls.bls import box_least_squares, frequency_periods


class BLSTest(unittest.TestCase):
    def test_frequency_grid_boundaries(self):
        periods = list(frequency_periods(0.5, 10.0, 21))
        self.assertAlmostEqual(periods[0], 0.5)
        self.assertAlmostEqual(periods[-1], 10.0)
        self.assertTrue(all(a < b for a, b in zip(periods, periods[1:])))

    def test_recovers_synthetic_transit(self):
        random.seed(42)
        cadence = 0.02
        period = 2.0
        duration = 0.16
        flux = []
        for index in range(2_000):
            phase = (index * cadence) % period
            transit = phase < duration
            flux.append(1.0 - (0.015 if transit else 0.0) + random.gauss(0, 0.002))

        result = box_least_squares(
            flux,
            cadence_days=cadence,
            min_period_days=1.5,
            max_period_days=2.5,
            n_periods=301,
            durations_days=(duration,),
            phase_bins=200,
        )
        self.assertLess(abs(result.period_days - period), 0.02)
        self.assertGreater(result.depth, 0.01)
        self.assertGreater(result.snr, 7.0)
        self.assertGreater(result.sde, 3.0)

    def test_accepts_irregular_observation_times(self):
        cadence = 0.02
        period = 2.0
        times = [index * cadence for index in range(1_000)]
        times = [time for time in times if not 7.0 < time < 9.0]
        flux = [1.0 - (0.02 if time % period < 0.16 else 0.0) for time in times]

        result = box_least_squares(
            flux,
            times_days=times,
            cadence_days=cadence,
            min_period_days=1.5,
            max_period_days=2.5,
            n_periods=301,
            durations_days=(0.16,),
            phase_bins=200,
        )
        self.assertLess(abs(result.period_days - period), 0.02)


if __name__ == "__main__":
    unittest.main()
