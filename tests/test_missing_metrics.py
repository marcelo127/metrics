import math
import unittest

import numpy as np

from Aperture_complexity_metrics import compute_metrics
from metrics_runner import metrics_to_dataframe


class MissingMetricTests(unittest.TestCase):
    def make_beam_data(self, dose_rates):
        return {
            "Arc": {
                "n_leaves": 2,
                "n_cp": 2,
                "leaf_widths": np.array([10.0, 20.0]),
                "mlc_positions": [
                    (np.array([0.0, 0.0]), np.array([10.0, 10.0])),
                    (np.array([1.0, 2.0]), np.array([11.0, 12.0])),
                ],
                "mu_per_cp": np.array([100.0]),
                "mu_total": 100.0,
                "gantry_angles": [0.0, 180.0],
                "gantry_rotation_direction": "CW",
                "dose_rates": dose_rates,
            }
        }

    def test_calculates_and_exports_missing_metrics(self):
        metrics = compute_metrics(self.make_beam_data([100.0, 200.0]))
        arc = metrics["Arc"]

        self.assertAlmostEqual(arc["MeanLeafTravel_mm"], 1.5)
        self.assertAlmostEqual(arc["Plan_MLT_mm"], 1.5)
        self.assertEqual(arc["SAS_lt2mm"], 0.0)
        self.assertEqual(arc["SAS_lt5mm"], 0.0)
        self.assertEqual(arc["SAS_lt20mm"], 1.0)
        self.assertAlmostEqual(arc["MeanDoseRateVariation"], 100.0 / 180.0)
        self.assertAlmostEqual(arc["Plan_PI"], 80.0**2 / (4.0 * math.pi * 300.0))

        frame = metrics_to_dataframe(metrics)
        self.assertIn("SAS (<2 mm)", frame.columns)
        self.assertIn("SAS (<5 mm)", frame.columns)
        self.assertIn("SAS (<20 mm)", frame.columns)
        self.assertIn("Mean Leaf Travel (MLT) (mm)", frame.columns)
        self.assertIn("Plan Mean Leaf Travel (MLT) (mm)", frame.columns)
        self.assertIn("Mean Dose Rate Variation ((MU/min)/degree)", frame.columns)
        self.assertIn("Plan Average Beam Irregularity (PI)", frame.columns)
        self.assertAlmostEqual(frame.iloc[0]["Plan Average Beam Irregularity (PI)"], arc["Plan_PI"])

    def test_zero_only_dose_rates_are_unavailable(self):
        metrics = compute_metrics(self.make_beam_data([0.0, 0.0]))
        self.assertTrue(math.isnan(metrics["Arc"]["MeanDoseRateVariation"]))

    def test_missing_gantry_angles_make_dose_rate_variation_unavailable(self):
        beam_data = self.make_beam_data([100.0, 200.0])
        beam_data["Arc"]["gantry_angles"] = [0.0, None]
        metrics = compute_metrics(beam_data)
        self.assertTrue(math.isnan(metrics["Arc"]["MeanDoseRateVariation"]))


if __name__ == "__main__":
    unittest.main()
