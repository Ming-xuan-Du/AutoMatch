
"""Metrics and baselines for AutoMatch anomaly evaluation.

Original held-out listings are assumed-normal controls.
Synthetic anomalies are deliberately altered records.

The snapshot baseline and the paired-change baseline
have different information available to them.
"""

from collections import defaultdict
from dataclasses import dataclass
from types import SimpleNamespace

from ml.rule_baseline import check_vehicle
from ml.change_rules import check_inventory_change


@dataclass(frozen=True)
class DetectionCounts:
    tp: int
    fp: int
    tn: int
    fn: int

    def as_dict(self):
        positive_count = self.tp + self.fn
        control_count = self.fp + self.tn
        predicted_positive = self.tp + self.fp

        return {
            "true_positive": self.tp,
            "false_positive": self.fp,
            "true_negative": self.tn,
            "false_negative": self.fn,
            "synthetic_recall": (
                self.tp / positive_count
                if positive_count else None
            ),
            "assumed_normal_flag_rate": (
                self.fp / control_count
                if control_count else None
            ),
            "balanced_set_precision": (
                self.tp / predicted_positive
                if predicted_positive else None
            ),
        }


def count_detections(cases, flags):
    """Build a confusion matrix from labeled cases."""

    if len(cases) != len(flags):
        raise ValueError("Case and prediction counts differ")

    tp = fp = tn = fn = 0

    for case, flagged in zip(cases, flags):
        if case.label not in (0, 1):
            raise ValueError("Expected binary labels")

        if type(flagged) is not bool:
            raise ValueError("Expected Boolean predictions")

        if case.label == 1:
            if flagged:
                tp += 1
            else:
                fn += 1
        else:
            if flagged:
                fp += 1
            else:
                tn += 1

    return DetectionCounts(tp, fp, tn, fn)


def snapshot_rule_flags(cases, *, reference_year):
    """Evaluate current-value validation rules.

    Every case is treated as a standalone present listing.
    No earlier inventory values are provided.
    """

    flags = []

    for case in cases:
        vehicle = SimpleNamespace(
            source_listing_id=case.source_listing_id,
            title=case.title,
            listing_url="synthetic-evaluation",
            year=case.year,
            price_cash=case.price_cash,
            price_finance=None,
            mileage_km=case.mileage_km,
            missing_streak=0,
        )

        findings = check_vehicle(
            vehicle,
            reference_year=reference_year,
        )

        flags.append(bool(findings))

    return flags


def group_pairs(cases):
    """Require one original and one alteration per ID."""

    groups = defaultdict(list)

    for case in cases:
        groups[case.source_listing_id].append(case)

    for vehicle_id, group in groups.items():
        if (
            len(group) != 2
            or {case.label for case in group} != {0, 1}
        ):
            raise ValueError(
                f"Invalid evaluation pair: {vehicle_id}"
            )

    return {
        vehicle_id: {
            case.label: case
            for case in group
        }
        for vehicle_id, group in groups.items()
    }


def paired_change_rule_flags(cases):
    """Counterfactual before/after rule evaluation.

    Original controls are treated as unchanged.
    Synthetic cases are treated as updates from
    their original values.

    This is NOT equivalent to single-record detection.
    """

    pairs = group_pairs(cases)
    flags = []

    for case in cases:
        if case.label == 0:
            flags.append(False)
            continue

        original = pairs[case.source_listing_id][0]

        changes = {}

        if case.price_cash != original.price_cash:
            changes["price_cash"] = {
                "old": original.price_cash,
                "new": case.price_cash,
            }

        if case.mileage_km != original.mileage_km:
            changes["mileage_km"] = {
                "old": original.mileage_km,
                "new": case.mileage_km,
            }

        synthetic_change = SimpleNamespace(
            id=0,
            snapshot_id=0,
            source_listing_id=case.source_listing_id,
            change_type="updated",
            changes=changes,
        )

        findings = check_inventory_change(
            synthetic_change
        )

        flags.append(bool(findings))

    return flags


def scenario_summary(cases, flags):
    """Detection counts for each synthetic scenario."""

    if len(cases) != len(flags):
        raise ValueError("Case and prediction counts differ")

    results = defaultdict(
        lambda: {"total": 0, "detected": 0}
    )

    for case, flagged in zip(cases, flags):
        if case.label != 1:
            continue

        result = results[case.scenario]
        result["total"] += 1
        result["detected"] += int(flagged)

    return {
        name: {
            **counts,
            "recall": (
                counts["detected"] / counts["total"]
                if counts["total"] else None
            ),
        }
        for name, counts in sorted(results.items())
    }


def paired_score_movement(cases, scores):
    """Check whether altered cases look more anomalous.

    Lower Isolation Forest decision scores mean
    more anomalous observations.
    """

    if len(cases) != len(scores):
        raise ValueError("Case and score counts differ")

    pairs = group_pairs(cases)

    score_lookup = {
        (case.source_listing_id, case.label): score
        for case, score in zip(cases, scores)
    }

    more_anomalous = 0
    less_anomalous = 0
    ties = 0

    for vehicle_id in pairs:
        original_score = score_lookup[(vehicle_id, 0)]
        synthetic_score = score_lookup[(vehicle_id, 1)]

        if synthetic_score < original_score:
            more_anomalous += 1
        elif synthetic_score > original_score:
            less_anomalous += 1
        else:
            ties += 1

    return {
        "pairs": len(pairs),
        "altered_more_anomalous": more_anomalous,
        "altered_less_anomalous": less_anomalous,
        "ties": ties,
    }
