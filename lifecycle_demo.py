#!/usr/bin/env python3
"""Offline synthetic checkout-reminder decision QA; never sends or approves email."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys


SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 2_000_000
POLICY_FIELDS = (
    "minimum_delay_seconds", "checkout_window_seconds", "cooldown_seconds"
)
INPUT_FIELDS = (
    "consent", "suppressed", "checkout_at", "last_purchase_at", "last_reminder_at"
)
OUTCOMES = ("eligible", "ineligible", "review")
TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)
CASE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
REASON = re.compile(r"[A-Z][A-Z0-9_]*")
SCOPE = "Synthetic decision logic only; not send approval or platform integration."


class InputError(ValueError):
    """The scenario suite cannot be evaluated reliably."""


def parse_timestamp(value):
    """Accept a strict ISO-8601 subset with an explicit, known UTC offset."""
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
        raise ValueError("A timezone-aware timestamp is required.")
    if value.endswith("-00:00"):
        raise ValueError("An unknown local offset is not a known timezone.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid or out-of-range timestamp.") from exc


def valid_policy(policy):
    return (
        isinstance(policy, dict)
        and set(policy) == set(POLICY_FIELDS)
        and all(type(policy[key]) is int and policy[key] >= 0 for key in POLICY_FIELDS)
        and policy["checkout_window_seconds"] >= policy["minimum_delay_seconds"]
    )


def decision(outcome, reasons):
    return {"outcome": outcome, "reasons": reasons}


def elapsed_microseconds(later, earlier):
    """Keep boundary comparisons exact, even for widely separated dates."""
    delta = later - earlier
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def evaluate_case(record, evaluated_at, policy):
    """Return one deterministic outcome. All invalid/missing data goes to review."""
    problems = []
    if not valid_policy(policy):
        problems.append("INVALID_POLICY")
    try:
        now = parse_timestamp(evaluated_at)
    except ValueError:
        now = None
        problems.append("INVALID_EVALUATED_AT")
    if not isinstance(record, dict):
        return decision("review", problems + ["INVALID_INPUT"])
    if set(record) - set(INPUT_FIELDS):
        problems.append("UNEXPECTED_INPUT_FIELDS")

    timestamps = {}
    for field in INPUT_FIELDS:
        if field not in record:
            problems.append("MISSING_" + field.upper())
            continue
        value = record[field]
        if field == "consent":
            if value not in ("active", "inactive"):
                problems.append("INVALID_CONSENT")
        elif field == "suppressed":
            if type(value) is not bool:
                problems.append("INVALID_SUPPRESSED")
        elif value is None:
            if field == "checkout_at":
                problems.append("MISSING_CHECKOUT_AT")
            else:
                # Explicit null means known absence in this synthetic snapshot.
                timestamps[field] = None
        else:
            try:
                timestamps[field] = parse_timestamp(value)
                if now is not None and timestamps[field] > now:
                    problems.append("FUTURE_" + field.upper())
            except ValueError:
                problems.append("INVALID_" + field.upper())
    if problems:
        return decision("review", problems)

    checkout = timestamps["checkout_at"]
    age = elapsed_microseconds(now, checkout)
    reasons = []
    if record["consent"] != "active":
        reasons.append("CONSENT_INACTIVE")
    if record["suppressed"]:
        reasons.append("PROFILE_SUPPRESSED")
    purchase = timestamps["last_purchase_at"]
    if purchase is not None and purchase >= checkout:
        reasons.append("PURCHASE_AT_OR_AFTER_CHECKOUT")
    if age < policy["minimum_delay_seconds"] * 1_000_000:
        reasons.append("MINIMUM_DELAY_NOT_MET")
    if age > policy["checkout_window_seconds"] * 1_000_000:
        reasons.append("CHECKOUT_CONTEXT_EXPIRED")
    reminder = timestamps["last_reminder_at"]
    if reminder is not None and elapsed_microseconds(now, reminder) < policy["cooldown_seconds"] * 1_000_000:
        reasons.append("REMINDER_COOLDOWN_ACTIVE")
    return decision("ineligible", reasons) if reasons else decision("eligible", ["ALL_RULES_MET"])


def naive_outcome(record, evaluated_at, policy):
    """Deliberately incomplete teaching baseline, never a recommended send rule."""
    if not isinstance(record, dict) or record.get("consent") != "active":
        return "ineligible"
    try:
        age = (parse_timestamp(evaluated_at) - parse_timestamp(record.get("checkout_at"))).total_seconds()
    except ValueError:
        return "ineligible"
    return "eligible" if age >= policy["minimum_delay_seconds"] else "ineligible"


def build_report(suite):
    """Evaluate an explicit synthetic suite; expectations never drive decisions."""
    fields = {"schema_version", "synthetic_only", "evaluated_at", "policy", "cases"}
    if not isinstance(suite, dict) or set(suite) != fields:
        raise InputError("Invalid suite fields.")
    if type(suite["schema_version"]) is not int or suite["schema_version"] != SCHEMA_VERSION:
        raise InputError("Unsupported suite schema version.")
    if suite["synthetic_only"] is not True:
        raise InputError("The suite must be explicitly marked synthetic_only.")
    if not valid_policy(suite["policy"]):
        raise InputError("Invalid suite policy; no cases evaluated.")
    try:
        parse_timestamp(suite["evaluated_at"])
    except ValueError as exc:
        raise InputError("Invalid suite evaluation timestamp; no cases evaluated.") from exc
    if not isinstance(suite["cases"], list) or not suite["cases"]:
        raise InputError("A nonempty cases array is required.")

    rows, ids = [], set()
    for case in suite["cases"]:
        if not isinstance(case, dict) or set(case) != {"id", "input", "expected"}:
            raise InputError("Each case requires exactly id, input, and expected.")
        case_id, expected = case["id"], case["expected"]
        if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id) or case_id in ids:
            raise InputError("Case IDs must be unique, short, lowercase synthetic labels.")
        ids.add(case_id)
        if (
            not isinstance(expected, dict) or set(expected) != {"outcome", "reasons"}
            or expected["outcome"] not in OUTCOMES
            or not isinstance(expected["reasons"], list) or not expected["reasons"]
            or not all(isinstance(code, str) and REASON.fullmatch(code) for code in expected["reasons"])
        ):
            raise InputError("Each expected decision needs an outcome and nonempty reason-code list.")
        actual = evaluate_case(case["input"], suite["evaluated_at"], suite["policy"])
        rows.append({
            "case_id": case_id,
            "naive_outcome": naive_outcome(case["input"], suite["evaluated_at"], suite["policy"]),
            **actual,
            "expected_match": actual == expected,
        })

    summary = {"cases": len(rows), "expected_matches": sum(row["expected_match"] for row in rows)}
    summary.update({outcome: sum(row["outcome"] == outcome for row in rows) for outcome in OUTCOMES})
    for outcome in ("ineligible", "review"):
        summary["naive_eligible_but_" + outcome] = sum(
            row["naive_outcome"] == "eligible" and row["outcome"] == outcome for row in rows
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "evaluated_at": suite["evaluated_at"],
        "policy": {key: suite["policy"][key] for key in POLICY_FIELDS},
        "summary": summary,
        "cases": rows,
    }


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("Duplicate JSON keys are not allowed.")
        result[key] = value
    return result


def reject_constant(_value):
    raise InputError("Non-finite JSON numbers are not allowed.")


def load_suite(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise InputError("Input exceeds the 2 MB limit.")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenarios", help="Path to a synthetic JSON scenario suite")
    args = parser.parse_args(argv)
    try:
        report = build_report(load_suite(args.scenarios))
    except (OSError, ValueError, RecursionError):
        print("Input error: invalid or unreadable synthetic scenario suite; no approval produced.", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["summary"]["expected_matches"] == report["summary"]["cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
