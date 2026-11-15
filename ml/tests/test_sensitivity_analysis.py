"""Behavior checks for sensitivity boundaries, metrics, and batch failures."""

import importlib.util
import io
import json
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/sensitivity_analysis.py"
SPEC = importlib.util.spec_from_file_location("sensitivity_analysis", SCRIPT)
sensitivity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sensitivity)


class SensitivityTests(unittest.TestCase):
    def test_zone_boundaries(self):
        for pd, expected in [
            (None, None),
            (0, "approve"),
            (0.082999, "approve"),
            (0.083, "review"),
            (0.285, "review"),
            (0.285001, "reject"),
        ]:
            with self.subTest(pd=pd):
                self.assertEqual(sensitivity.pd_zone(pd), expected)

    def test_null_pd_preserves_rule_and_does_not_become_zero(self):
        base = {"pd": 0.05, "recommendation": "approve", "reasons": []}
        result = {
            "pd": None,
            "recommendation": "review",
            "reasons": [{"code": "UNSEEN_CATEGORY", "field": "purpose"}],
            "scoring_status": "null_pd",
            "http_status": 200,
            "error": "",
        }
        row = sensitivity.comparison({"feature": "purpose"}, base, result)
        self.assertIsNone(row["delta_pd"])
        self.assertIsNone(row["abs_delta_pd"])
        self.assertIsNone(row["pd_zone_changed"])
        self.assertTrue(row["recommendation_changed"])
        self.assertEqual(row["variant_reasons"], result["reasons"])

    def test_summary_weights_baselines_equally_and_excludes_errors(self):
        def row(base, delta, changed=False, status="ok"):
            return {
                "base_id": base,
                "feature": "age",
                "abs_delta_pd": delta,
                "pd_zone_changed": changed if delta is not None else None,
                "recommendation_changed": None if status == "http_error" else changed,
                "scoring_status": status,
            }

        rows = [
            row("a", 0.1),
            row("a", 0.3, True),
            row("b", 0.8, True),
            row("c", None, True, "null_pd"),
            row("d", None, status="http_error"),
        ]
        summary = next(s for s in sensitivity.summarize(rows) if s["feature"] == "age")
        self.assertAlmostEqual(summary["mean_abs_delta_pd"], 0.5)
        self.assertEqual(summary["max_abs_delta_pd"], 0.8)
        self.assertAlmostEqual(summary["pd_zone_change_share"], 2 / 3)
        self.assertAlmostEqual(summary["recommendation_change_share"], 3 / 4)
        self.assertEqual(summary["baselines_with_any_recommendation_change"], 3)
        self.assertEqual(summary["null_pd_count"], 1)
        self.assertEqual(summary["http_error_count"], 1)

    def test_generated_variants_change_one_feature_and_stay_in_domain(self):
        X_train, X_test, _, _ = sensitivity.train_test(sensitivity.load_processed())
        metadata = json.loads(sensitivity.METADATA_PATH.read_text())
        allowed = sensitivity.allowed_categories(metadata, X_train)
        features = {f: int(X_test.iloc[0][f]) for f in sensitivity.FEATURE_COLUMNS}
        features["age"] = 25
        bases = [{"base_id": "test", "features": features}]
        config = {
            "numeric_relative_changes": [-0.2, -0.1, 0.1, 0.2],
            "age_values": [24, 25, 26, 27],
        }
        variants = sensitivity.generate_variants(bases, metadata, allowed, config)
        self.assertEqual(len(variants), len({v["variant_id"] for v in variants}))
        for variant in variants:
            changed = [f for f in features if features[f] != variant["features"][f]]
            self.assertEqual(changed, [variant["feature"]])
            if variant["feature"] in sensitivity.NUMERIC_FEATURES:
                bounds = metadata["numeric_ranges"][variant["feature"]]
                self.assertTrue(
                    bounds["min"] <= variant["variant_value"] <= bounds["max"]
                )
        age_values = {v["variant_value"] for v in variants if v["feature"] == "age"}
        self.assertTrue({24, 26, 27}.issubset(age_values))
        self.assertNotIn(25, age_values)

    def test_selection_is_seeded_unique_and_covers_zones(self):
        candidates = [
            {
                "base_id": str(i),
                "features": {"age": 19 + i},
                "score": {"pd": (0.05, 0.2, 0.6)[i % 3]},
            }
            for i in range(40)
        ]
        selected = sensitivity.select_baselines(candidates, 30, 42)
        self.assertEqual(selected, sensitivity.select_baselines(candidates, 30, 42))
        self.assertEqual(len({b["base_id"] for b in selected}), 30)
        self.assertEqual(
            {sensitivity.pd_zone(b["score"]["pd"]) for b in selected},
            {"approve", "review", "reject"},
        )

    def test_http_error_keeps_each_request_position(self):
        application = sensitivity.CreditApplication.model_config["json_schema_extra"][
            "examples"
        ][0]
        error = urllib.error.HTTPError(
            "http://ml/predict/batch", 422, "invalid", {}, io.BytesIO(b"bad batch")
        )
        with patch.object(sensitivity.urllib.request, "urlopen", side_effect=error):
            scores = sensitivity.score_batch(
                [application, application], "http://ml", 100, 1
            )
        self.assertEqual(len(scores), 2)
        self.assertTrue(
            all(s["http_status"] == 422 and s["pd"] is None for s in scores)
        )

    def test_batch_response_count_mismatch_is_not_silently_zipped(self):
        application = sensitivity.CreditApplication.model_config["json_schema_extra"][
            "examples"
        ][0]
        response = io.BytesIO(b'{"predictions": []}')
        response.status = 200
        with patch.object(sensitivity.urllib.request, "urlopen", return_value=response):
            scores = sensitivity.score_batch([application], "http://ml", 100, 1)
        self.assertEqual(scores[0]["scoring_status"], "response_error")


if __name__ == "__main__":
    unittest.main()
