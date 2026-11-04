
"""Evaluate local AI extraction against labeled synthetic cases."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from evaluation.requirement_cases import CASES, FIELDS


NUMERIC_FIELDS = {
    "max_budget",
    "min_year",
    "max_mileage_km",
}


def normalize(field, value):
    if value is None:
        return None

    if field in NUMERIC_FIELDS:
        return value if type(value) is int else str(value)

    if not isinstance(value, str):
        return value

    cleaned = " ".join(
        value.casefold().strip().replace("-", " ").split()
    )

    if field == "drivetrain":
        return {
            "all wheel drive": "awd",
            "front wheel drive": "fwd",
            "rear wheel drive": "rwd",
            "four wheel drive": "4wd",
            "4x4": "4wd",
        }.get(cleaned, cleaned)

    if field == "body_style":
        return {
            "sport utility vehicle": "suv",
            "pickup": "truck",
            "pickup truck": "truck",
        }.get(cleaned, cleaned)

    if field == "make" and cleaned == "vw":
        return "volkswagen"

    return cleaned


def ratio(numerator, denominator):
    return (
        round(numerator / denominator, 4)
        if denominator
        else None
    )


def summarize(cases, predictions):
    if len(cases) != len(predictions):
        raise ValueError(
            "Each case must have exactly one prediction"
        )

    totals = {
        "total_cases": len(cases),
        "total_field_decisions": len(cases) * len(FIELDS),
        "failed_calls": 0,
        "correct_states": 0,
        "correct_field_decisions": 0,
        "perfect_cases": 0,
        "gold_explicit_fields": 0,
        "predicted_explicit_fields": 0,
        "correct_explicit_values": 0,
        "omitted_explicit_fields": 0,
        "incorrect_explicit_values": 0,
        "gold_nonexplicit_fields": 0,
        "hallucinated_constraints": 0,
        "gold_ambiguous_or_preference_fields": 0,
        "correct_ambiguous_or_preference_fields": 0,
    }

    errors = []

    for case, prediction in zip(cases, predictions):
        if prediction.get("error"):
            totals["failed_calls"] += 1

        predicted_values = prediction.get("requirements") or {}
        predicted_states = prediction.get("field_states") or {}

        all_correct = True

        for field in FIELDS:
            gold_status = case["field_states"][field]
            gold_value = case["requirements"][field]

            status = predicted_states.get(field, "error")
            value = predicted_values.get(field)

            status_ok = status == gold_status

            value_ok = (
                normalize(field, value)
                == normalize(field, gold_value)
            )

            decision_ok = status_ok and value_ok

            if status_ok:
                totals["correct_states"] += 1

            if decision_ok:
                totals["correct_field_decisions"] += 1
            else:
                all_correct = False
                errors.append({
                    "case_id": case["id"],
                    "field": field,
                    "expected": {
                        "status": gold_status,
                        "value": gold_value,
                    },
                    "predicted": {
                        "status": status,
                        "value": value,
                    },
                })

            if status == "explicit":
                totals["predicted_explicit_fields"] += 1

            if gold_status == "explicit":
                totals["gold_explicit_fields"] += 1

                if status == "explicit" and value_ok:
                    totals["correct_explicit_values"] += 1

                elif status != "explicit" or value is None:
                    totals["omitted_explicit_fields"] += 1

                else:
                    totals["incorrect_explicit_values"] += 1

            else:
                totals["gold_nonexplicit_fields"] += 1

                if status == "explicit" or value is not None:
                    totals["hallucinated_constraints"] += 1

            if gold_status in {"ambiguous", "preference"}:
                totals[
                    "gold_ambiguous_or_preference_fields"
                ] += 1

                if status_ok and value is None:
                    totals[
                        "correct_ambiguous_or_preference_fields"
                    ] += 1

        if all_correct:
            totals["perfect_cases"] += 1

    return {
        **totals,

        "status_accuracy": ratio(
            totals["correct_states"],
            totals["total_field_decisions"],
        ),

        "field_decision_accuracy": ratio(
            totals["correct_field_decisions"],
            totals["total_field_decisions"],
        ),

        "perfect_case_rate": ratio(
            totals["perfect_cases"],
            totals["total_cases"],
        ),

        "explicit_value_recall": ratio(
            totals["correct_explicit_values"],
            totals["gold_explicit_fields"],
        ),

        "explicit_value_precision": ratio(
            totals["correct_explicit_values"],
            totals["predicted_explicit_fields"],
        ),

        "omission_rate": ratio(
            totals["omitted_explicit_fields"],
            totals["gold_explicit_fields"],
        ),

        "incorrect_explicit_value_rate": ratio(
            totals["incorrect_explicit_values"],
            totals["gold_explicit_fields"],
        ),

        "hallucination_rate": ratio(
            totals["hallucinated_constraints"],
            totals["gold_nonexplicit_fields"],
        ),

        "ambiguity_preference_accuracy": ratio(
            totals["correct_ambiguous_or_preference_fields"],
            totals["gold_ambiguous_or_preference_fields"],
        ),

        "per_field_accuracy": {
            field: ratio(
                len(cases) - sum(
                    error["field"] == field
                    for error in errors
                ),
                len(cases),
            )
            for field in FIELDS
        },

        "mismatches": errors,
    }


async def run_one(case):
    from backend.ai.extractor import extract_requirements

    try:
        result = await extract_requirements(
            case["text"]
        )

        return {
            "case_id": case["id"],
            "requirements": (
                result.requirements.model_dump()
            ),
            "field_states": result.field_states,
            "review_notes": result.review_notes,
            "error": None,
        }

    except Exception as exc:
        return {
            "case_id": case["id"],
            "requirements": {},
            "field_states": {},
            "review_notes": [],
            "error": type(exc).__name__,
        }


async def run_evaluation(cases):
    predictions = []

    for index, case in enumerate(cases, start=1):
        print(
            f"[{index}/{len(cases)}] {case['id']}",
            flush=True,
        )

        prediction = await run_one(case)
        predictions.append(prediction)

    return predictions


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--output",
        default="evaluation/results/ollama_extraction.json",
    )

    args = parser.parse_args()

    if not 1 <= args.limit <= len(CASES):
        parser.error(
            f"--limit must be between 1 and {len(CASES)}"
        )

    if (
        os.getenv("AI_PROVIDER", "").strip().lower()
        != "ollama"
    ):
        parser.error(
            "Set AI_PROVIDER=ollama so evaluation "
            "cannot use a paid API"
        )

    cases = CASES[:args.limit]

    predictions = asyncio.run(
        run_evaluation(cases)
    )

    report = {
        "provider": "ollama",
        "model": os.getenv(
            "OLLAMA_MODEL",
            "qwen3:4b-instruct",
        ),
        "complete_dataset": len(cases) == len(CASES),
        "summary": summarize(
            cases,
            predictions,
        ),
        "predictions": predictions,
    }

    output = Path(args.output)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary_without_details = {
        key: value
        for key, value in report["summary"].items()
        if key != "mismatches"
    }

    print(
        json.dumps(
            summary_without_details,
            indent=2,
            ensure_ascii=False,
        )
    )

    print(f"Detailed results saved to {output}")


if __name__ == "__main__":
    main()
