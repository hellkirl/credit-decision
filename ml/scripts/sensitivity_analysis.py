#!/usr/bin/env python3
"""One-feature-at-a-time sensitivity of calibrated ML API predictions.

From the repository root (with ML dependencies installed):
  ml/venv/bin/python ml/scripts/sensitivity_analysis.py --ml-url http://localhost/ml

Only POST /predict/batch is called; no applications are written to the database.
SENSITIVITY_ML_ROOT can point to /app when executing in the ML container.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

ROOT = Path(os.environ.get("SENSITIVITY_ML_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "src"))

from credit.config import (  # noqa: E402
    CALIBRATOR_PATH,
    FEATURE_COLUMNS,
    METADATA_PATH,
    MODEL_PATH,
    NUMERIC_FEATURES,
    PROCESSED_DATA_PATH,
    RANDOM_STATE,
    TEST_SIZE,
)
from credit.data import load_processed  # noqa: E402
from credit.features import train_test  # noqa: E402
from credit.schemas import BatchPredictionResponse, CreditApplication  # noqa: E402

APPROVE = 0.083
REJECT = 0.285
RESULT_FIELDS = [
    "base_id",
    "variant_id",
    "feature",
    "strategy",
    "base_value",
    "variant_value",
    "base_pd",
    "variant_pd",
    "delta_pd",
    "abs_delta_pd",
    "base_pd_zone",
    "variant_pd_zone",
    "pd_zone_changed",
    "base_recommendation",
    "variant_recommendation",
    "recommendation_changed",
    "base_reasons",
    "variant_reasons",
    "scoring_status",
    "http_status",
    "error",
]
SUMMARY_FIELDS = [
    "feature",
    "variant_count",
    "valid_pd_pair_count",
    "successful_response_count",
    "mean_abs_delta_pd",
    "max_abs_delta_pd",
    "pd_zone_change_count",
    "pd_zone_change_share",
    "recommendation_change_count",
    "recommendation_change_share",
    "baselines_with_any_recommendation_change",
    "baselines_with_any_recommendation_change_share",
    "null_pd_count",
    "http_error_count",
    "response_error_count",
]


def pd_zone(pd):
    if pd is None:
        return None
    return "approve" if pd < APPROVE else "review" if pd <= REJECT else "reject"


def score_batch(applications, url, batch_size, timeout):
    """Keep positional alignment, including failed HTTP/transport/response batches."""
    results = []
    for offset in range(0, len(applications), batch_size):
        batch = applications[offset : offset + batch_size]
        body = {"applications": [CreditApplication(**a).model_dump() for a in batch]}
        request = urllib.request.Request(
            url.rstrip("/") + "/predict/batch",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        status = None
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.status
                payload = json.loads(response.read())
            if not isinstance(payload, dict) or "predictions" not in payload:
                raise ValueError("Response is missing predictions")
            # Require explicit pd: the schema's default None must not hide a broken API.
            if any("pd" not in p for p in payload["predictions"]):
                raise ValueError("Prediction is missing calibrated pd")
            predictions = BatchPredictionResponse.model_validate(payload).predictions
            if len(predictions) != len(batch):
                raise ValueError("Prediction count does not match request count")
            for prediction in predictions:
                results.append(
                    {
                        "pd": prediction.pd,
                        "recommendation": (
                            "review"
                            if prediction.decision == "manual_review"
                            else prediction.decision
                        ),
                        "reasons": prediction.reasons,
                        "scoring_status": "null_pd" if prediction.pd is None else "ok",
                        "http_status": status,
                        "error": "",
                    }
                )
        except urllib.error.HTTPError as exc:
            error = exc.read().decode(errors="replace")[:4000]
            results.extend(failure("http_error", exc.code, error) for _ in batch)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            results.extend(failure("http_error", status, str(exc)) for _ in batch)
        except (ValueError, TypeError, KeyError) as exc:
            results.extend(failure("response_error", status, str(exc)) for _ in batch)
        print(
            f"Scored {min(offset + batch_size, len(applications))}/{len(applications)}",
            flush=True,
        )
    return results


def failure(kind, status, error):
    return {
        "pd": None,
        "recommendation": None,
        "reasons": [],
        "scoring_status": kind,
        "http_status": status,
        "error": error,
    }


def select_baselines(candidates, count, seed):
    """Cover zones, both thresholds, ages 25/26, then seeded random coverage."""
    rng = random.Random(seed)
    shuffled = rng.sample(candidates, len(candidates))
    groups = []
    for zone in ("approve", "review", "reject"):
        groups.append([b for b in shuffled if pd_zone(b["score"]["pd"]) == zone])
    for threshold in (APPROVE, REJECT):
        groups.append(sorted(shuffled, key=lambda b: abs(b["score"]["pd"] - threshold)))
    for age in (25, 26):
        groups.append(sorted(shuffled, key=lambda b: abs(b["features"]["age"] - age)))
    # Round robin gives every selection criterion a place in small samples.
    groups.append(shuffled)
    selected, seen = [], set()
    for _ in range(2):
        for group in groups:
            candidate = next((b for b in group if b["base_id"] not in seen), None)
            if candidate is not None and len(selected) < count:
                selected.append(candidate)
                seen.add(candidate["base_id"])
    for candidate in shuffled:
        if len(selected) >= count:
            break
        if candidate["base_id"] not in seen:
            selected.append(candidate)
            seen.add(candidate["base_id"])
    return selected


def allowed_categories(metadata, X_train):
    properties = CreditApplication.model_json_schema()["properties"]
    allowed = {}
    for feature in FEATURE_COLUMNS:
        if feature in NUMERIC_FEATURES:
            continue
        if feature in metadata["categorical_values"]:
            values = metadata["categorical_values"][feature]
        else:
            field = properties[feature]
            if "minimum" not in field or "maximum" not in field:
                raise ValueError(
                    f"No category metadata or bounded schema for {feature}"
                )
            values = list(range(int(field["minimum"]), int(field["maximum"]) + 1))
        observed = set(int(v) for v in X_train[feature].unique())
        if set(values) != observed:
            raise ValueError(
                f"Metadata/schema and training categories disagree: {feature}"
            )
        allowed[feature] = sorted(values)
    return allowed


def generate_variants(baselines, metadata, allowed, config):
    variants = []
    for base in baselines:
        original = base["features"]
        for feature in FEATURE_COLUMNS:
            old = original[feature]
            proposals = []
            if feature in NUMERIC_FEATURES:
                bounds = metadata["numeric_ranges"][feature]
                for fraction in config["numeric_relative_changes"]:
                    # Non-negative values: round halves upward, avoiding banker's rounding.
                    value = math.floor(old * (1 + fraction) + 0.5)
                    value = max(bounds["min"], min(bounds["max"], value))
                    proposals.append((value, f"relative_{fraction:+.0%}"))
                if feature == "age":
                    proposals.extend(
                        (age, "age_boundary")
                        for age in config["age_values"]
                        if bounds["min"] <= age <= bounds["max"]
                    )
            else:
                proposals = [(value, "category") for value in allowed[feature]]
            unique = {}
            for value, strategy in proposals:
                if value != old:
                    unique.setdefault(int(value), []).append(strategy)
            for value, strategies in unique.items():
                changed = {**original, feature: value}
                differences = [f for f in FEATURE_COLUMNS if changed[f] != original[f]]
                if differences != [feature]:
                    raise ValueError("A variant must change exactly one ML feature")
                CreditApplication(**changed)
                variants.append(
                    {
                        "base_id": base["base_id"],
                        "variant_id": f"{base['base_id']}:{feature}:{value}",
                        "feature": feature,
                        "strategy": "|".join(strategies),
                        "base_value": old,
                        "variant_value": value,
                        "features": changed,
                    }
                )
    return variants


def comparison(variant, base_score, score):
    base_pd, new_pd = base_score["pd"], score["pd"]
    delta = None if base_pd is None or new_pd is None else new_pd - base_pd
    old_zone, new_zone = pd_zone(base_pd), pd_zone(new_pd)
    old_rec, new_rec = base_score["recommendation"], score["recommendation"]
    return {
        **{key: variant[key] for key in RESULT_FIELDS if key in variant},
        "base_pd": base_pd,
        "variant_pd": new_pd,
        "delta_pd": delta,
        "abs_delta_pd": None if delta is None else abs(delta),
        "base_pd_zone": old_zone,
        "variant_pd_zone": new_zone,
        "pd_zone_changed": None if delta is None else old_zone != new_zone,
        "base_recommendation": old_rec,
        "variant_recommendation": new_rec,
        "recommendation_changed": None
        if old_rec is None or new_rec is None
        else old_rec != new_rec,
        "base_reasons": base_score["reasons"],
        "variant_reasons": score["reasons"],
        "scoring_status": score["scoring_status"],
        "http_status": score["http_status"],
        "error": score["error"],
    }


def summarize(rows):
    summaries = []
    for feature in FEATURE_COLUMNS:
        group = [r for r in rows if r["feature"] == feature]
        by_base = defaultdict(list)
        for row in group:
            by_base[row["base_id"]].append(row)
        valid = [r for r in group if r["abs_delta_pd"] is not None]
        rec_valid = [r for r in group if r["recommendation_changed"] is not None]
        base_means = [
            mean(r["abs_delta_pd"] for r in rs if r["abs_delta_pd"] is not None)
            for rs in by_base.values()
            if any(r["abs_delta_pd"] is not None for r in rs)
        ]
        rec_bases = {r["base_id"] for r in rec_valid}
        changed_bases = {r["base_id"] for r in rec_valid if r["recommendation_changed"]}
        zone_count = sum(bool(r["pd_zone_changed"]) for r in valid)
        rec_count = sum(bool(r["recommendation_changed"]) for r in rec_valid)
        summaries.append(
            {
                "feature": feature,
                "variant_count": len(group),
                "valid_pd_pair_count": len(valid),
                "successful_response_count": len(rec_valid),
                "mean_abs_delta_pd": mean(base_means) if base_means else None,
                "max_abs_delta_pd": max(
                    (r["abs_delta_pd"] for r in valid), default=None
                ),
                "pd_zone_change_count": zone_count,
                "pd_zone_change_share": zone_count / len(valid) if valid else None,
                "recommendation_change_count": rec_count,
                "recommendation_change_share": rec_count / len(rec_valid)
                if rec_valid
                else None,
                "baselines_with_any_recommendation_change": len(changed_bases),
                "baselines_with_any_recommendation_change_share": len(changed_bases)
                / len(rec_bases)
                if rec_bases
                else None,
                "null_pd_count": sum(r["scoring_status"] == "null_pd" for r in group),
                "http_error_count": sum(
                    r["scoring_status"] == "http_error" for r in group
                ),
                "response_error_count": sum(
                    r["scoring_status"] == "response_error" for r in group
                ),
            }
        )
    return summaries


def transition_cases(rows, variants, baselines, limit):
    variant_inputs = {v["variant_id"]: v["features"] for v in variants}
    base_inputs = {b["base_id"]: b["features"] for b in baselines}

    def examples(candidates):
        chosen = sorted(candidates, key=lambda r: r["abs_delta_pd"] or 0, reverse=True)[
            :limit
        ]
        return [
            {
                **r,
                "base_features": base_inputs[r["base_id"]],
                "variant_features": variant_inputs[r["variant_id"]],
            }
            for r in chosen
        ]

    transitions = {}
    for source, target in (
        ("approve", "review"),
        ("review", "reject"),
        ("reject", "review"),
        ("review", "approve"),
    ):
        matches = [
            r
            for r in rows
            if r["base_recommendation"] == source
            and r["variant_recommendation"] == target
        ]
        transitions[f"{source}->{target}"] = {
            "count": len(matches),
            "cases": examples(matches),
        }
    rule_matches = [
        r
        for r in rows
        if any(
            r[f"{prefix}_pd_zone"] is not None
            and r[f"{prefix}_pd_zone"] != r[f"{prefix}_recommendation"]
            and r[f"{prefix}_reasons"]
            for prefix in ("base", "variant")
        )
    ]
    return {
        "recommendation_transitions": transitions,
        "business_rule_overrides": {
            "count": len(rule_matches),
            "cases": examples(rule_matches),
        },
    }


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ml-url", default="http://localhost:8000")
    parser.add_argument(
        "--config", type=Path, default=ROOT / "experiments/sensitivity_config.json"
    )
    parser.add_argument("--n-baselines", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--run-id")
    parser.add_argument(
        "--output-dir", type=Path, help="Exact run directory; must not exist"
    )
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    for key in ("n_baselines", "seed", "batch_size"):
        if getattr(args, key) is not None:
            config[key] = getattr(args, key)
    if not 1 <= config["n_baselines"] <= 30:
        parser.error("n_baselines must be between 1 and 30")
    if not 1 <= config["batch_size"] <= 100:
        parser.error("batch_size must be between 1 and 100")
    if config["timeout_seconds"] <= 0 or config["cases_per_transition"] < 1:
        parser.error("timeout_seconds and cases_per_transition must be positive")
    if any(not math.isfinite(f) or f <= -1 for f in config["numeric_relative_changes"]):
        parser.error("numeric_relative_changes must be finite and greater than -1")
    if any(not isinstance(age, int) for age in config["age_values"]):
        parser.error("age_values must be integers")
    started = datetime.now(timezone.utc)
    run_id = args.run_id or started.strftime("%Y%m%dT%H%M%S%fZ")
    if Path(run_id).name != run_id or run_id in (".", ".."):
        parser.error("run-id must be a single directory name")
    output = args.output_dir or ROOT / "reports/sensitivity" / run_id
    if output.exists():
        parser.error(f"Output directory already exists: {output}")

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    X_train, X_test, _, _ = train_test(load_processed())
    allowed = allowed_categories(metadata, X_train)
    for feature in NUMERIC_FEATURES:
        expected = {
            "min": int(X_train[feature].min()),
            "max": int(X_train[feature].max()),
        }
        if metadata["numeric_ranges"][feature] != expected:
            raise ValueError(f"Numeric metadata differs from training split: {feature}")
    inputs = [{f: int(row[f]) for f in FEATURE_COLUMNS} for _, row in X_test.iterrows()]
    scores = score_batch(
        inputs, args.ml_url, config["batch_size"], config["timeout_seconds"]
    )
    candidates = [
        {"base_id": f"test-{int(index)}", "features": features, "score": score}
        for index, features, score in zip(X_test.index, inputs, scores)
    ]
    eligible = [b for b in candidates if b["score"]["scoring_status"] == "ok"]
    baselines = select_baselines(eligible, config["n_baselines"], config["seed"])
    if not baselines:
        raise RuntimeError(f"No valid baselines. First response: {scores[0]}")
    variants = generate_variants(baselines, metadata, allowed, config)
    print(
        f"Selected {len(baselines)} baselines; generated {len(variants)} variants",
        flush=True,
    )
    predictions = score_batch(
        [v["features"] for v in variants],
        args.ml_url,
        config["batch_size"],
        config["timeout_seconds"],
    )
    base_scores = {b["base_id"]: b["score"] for b in baselines}
    rows = [
        comparison(v, base_scores[v["base_id"]], score)
        for v, score in zip(variants, predictions)
    ]
    summaries = summarize(rows)
    cases = transition_cases(rows, variants, baselines, config["cases_per_transition"])
    baseline_rows = []
    for base in baselines:
        score = base["score"]
        baseline_rows.append(
            {
                "base_id": base["base_id"],
                **base["features"],
                "base_pd": score["pd"],
                "base_pd_zone": pd_zone(score["pd"]),
                "base_recommendation": score["recommendation"],
                "base_reasons": score["reasons"],
                "scoring_status": score["scoring_status"],
                "http_status": score["http_status"],
                "error": score["error"],
            }
        )
    metadata_out = {
        "run_id": run_id,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "ml_url": args.ml_url,
        "endpoint": "/predict/batch",
        "thresholds": {"approve": APPROVE, "reject": REJECT},
        "dataset": str(PROCESSED_DATA_PATH),
        "split_random_state": RANDOM_STATE,
        "test_size": TEST_SIZE,
        "train_count": len(X_train),
        "test_count": len(X_test),
        "baseline_count": len(baselines),
        "variant_count": len(variants),
        "baseline_ids": [b["base_id"] for b in baselines],
        "baseline_zone_counts": dict(Counter(b["base_pd_zone"] for b in baseline_rows)),
        "selection": "two round-robin passes over zones, thresholds, ages 25/26, random; seeded random fill",
        "excluded_test_applications": [
            {"base_id": b["base_id"], **b["score"]}
            for b in candidates
            if b["score"]["scoring_status"] != "ok"
        ],
        "category_values": allowed,
        "numeric_ranges": metadata["numeric_ranges"],
        "local_artifact_sha256": {
            path.name: sha256(path)
            for path in (
                MODEL_PATH,
                CALIBRATOR_PATH,
                METADATA_PATH,
                PROCESSED_DATA_PATH,
            )
        },
        "artifact_note": "Hashes describe local artifacts; API does not expose model identity. Use the same deployment/artifacts.",
        "summary_denominators": {
            "mean_abs_delta_pd": "mean of per-baseline means over valid PD pairs",
            "pd_zone_change_share": "valid PD pairs",
            "recommendation_change_share": "successful recommendation pairs, including null PD",
            "baselines_with_any_recommendation_change_share": "baselines with at least one successful recommendation pair per feature",
        },
        "rounding": "nearest integer, half up; clip to training range; deduplicate identical variants",
        "pd_zone_changes": sum(bool(r["pd_zone_changed"]) for r in rows),
        "recommendation_changes": sum(bool(r["recommendation_changed"]) for r in rows),
        "scoring_status_counts": dict(Counter(r["scoring_status"] for r in rows)),
    }
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "baselines.csv", baseline_rows, list(baseline_rows[0]))
    write_csv(output / "sensitivity_results.csv", rows, RESULT_FIELDS)
    write_csv(output / "sensitivity_summary.csv", summaries, SUMMARY_FIELDS)
    write_json(output / "transition_cases.json", cases)
    write_json(output / "run_metadata.json", metadata_out)
    top = sorted(summaries, key=lambda s: s["mean_abs_delta_pd"] or 0, reverse=True)[:5]
    print(
        json.dumps(
            {
                "output": str(output),
                "baselines": len(baselines),
                "variants": len(variants),
                "pd_zone_changes": metadata_out["pd_zone_changes"],
                "recommendation_changes": metadata_out["recommendation_changes"],
                "scoring_status_counts": metadata_out["scoring_status_counts"],
                "most_sensitive": [
                    {
                        "feature": s["feature"],
                        "mean_abs_delta_pd": s["mean_abs_delta_pd"],
                    }
                    for s in top
                ],
                "transitions": {
                    k: v["count"]
                    for k, v in cases["recommendation_transitions"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if any(
        s["scoring_status"] in ("http_error", "response_error")
        for s in scores + predictions
    ):
        print(
            "Run is incomplete: request/response errors were recorded in reports",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
