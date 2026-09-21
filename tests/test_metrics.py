import unittest

from script.metrics import best_f1_threshold, confusion_matrix


class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.results = [
            {"label": 2, "sde": 12.0},
            {"label": 2, "sde": 8.0},
            {"label": 1, "sde": 9.0},
            {"label": 1, "sde": 3.0},
        ]

    def test_confusion_matrix(self):
        matrix = confusion_matrix(self.results, 10.0)
        self.assertEqual((matrix.true_positive, matrix.false_positive,
                          matrix.true_negative, matrix.false_negative),
                         (1, 0, 2, 1))

    def test_best_f1_threshold(self):
        threshold, matrix = best_f1_threshold(self.results)
        self.assertEqual(threshold, 8.0)
        self.assertEqual(matrix.true_positive, 2)
        self.assertEqual(matrix.false_positive, 1)


if __name__ == "__main__":
    unittest.main()
