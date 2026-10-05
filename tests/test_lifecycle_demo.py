import contextlib
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lifecycle_demo as demo


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/lifecycle-scenarios.json"
REPORT = ROOT / "examples/lifecycle-scenarios.report.json"
NOW = "2026-10-05T12:00:00Z"
POLICY = {"minimum_delay_seconds": 3600, "checkout_window_seconds": 86400, "cooldown_seconds": 604800}
BASE = {
    "consent": "active", "suppressed": False, "checkout_at": "2026-10-05T10:00:00Z",
    "last_purchase_at": None, "last_reminder_at": None,
}


class TimestampTests(unittest.TestCase):
    def test_offsets_are_normalized_before_comparison(self):
        expected = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)
        for stamp in ("2026-10-05T10:00:00Z", "2026-10-05T13:00:00+03:00", "2026-10-05T06:00:00-04:00"):
            with self.subTest(stamp=stamp):
                self.assertEqual(demo.parse_timestamp(stamp), expected)

    def test_invalid_ambiguous_or_unsupported_timestamps(self):
        for stamp in (
            None, 0, False, [], {}, "", "2026-10-05", "2026-10-05T10:00:00",
            "2026-10-05 10:00:00Z", "2026-10-05T10:00Z", "20261005T100000Z",
            "2026-10-05T10:00:00-00:00", "2026-10-05T10:00:00+00:60",
            "2026-10-05T10:00:00+24:00", "2026-10-05T10:00:00+0300",
            "2026-02-30T10:00:00Z", "2026-10-05T24:00:00Z", "2026-10-05T10:00:60Z",
            "2026-10-05T10:00:00.0000001Z", "2026-10-05T10:00:00Z\n",
            "0000-01-01T00:00:00Z", "0001-01-01T00:00:00+01:00",
            "9999-12-31T23:59:59-01:00",
        ):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                demo.parse_timestamp(stamp)

    def test_microseconds_and_leap_date_are_supported(self):
        self.assertEqual(demo.parse_timestamp("2024-02-29T10:00:00.1Z").microsecond, 100000)


class DecisionTests(unittest.TestCase):
    def evaluate(self, updates=None, now=NOW, policy=None):
        return demo.evaluate_case({**BASE, **(updates or {})}, now, POLICY if policy is None else policy)

    def test_all_authored_scenarios_and_reason_order(self):
        suite = demo.load_suite(FIXTURE)
        for case in suite["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(demo.evaluate_case(case["input"], suite["evaluated_at"], suite["policy"]), case["expected"])

    def test_every_required_field_missing_requires_review(self):
        for field in demo.INPUT_FIELDS:
            record = dict(BASE)
            del record[field]
            with self.subTest(field=field):
                self.assertEqual(demo.evaluate_case(record, NOW, POLICY), demo.decision("review", ["MISSING_" + field.upper()]))

    def test_null_history_is_explicit_absence_not_missing(self):
        self.assertEqual(self.evaluate(), demo.decision("eligible", ["ALL_RULES_MET"]))
        self.assertEqual(self.evaluate({"checkout_at": None}), demo.decision("review", ["MISSING_CHECKOUT_AT"]))

    def test_consent_is_a_closed_vocabulary(self):
        for value in (None, True, False, 0, 1, "yes", "ACTIVE", " active", [], {}):
            with self.subTest(value=value):
                self.assertEqual(self.evaluate({"consent": value}), demo.decision("review", ["INVALID_CONSENT"]))

    def test_suppression_requires_an_actual_boolean(self):
        for value in (None, "false", "true", 0, 1, [], {}):
            with self.subTest(value=value):
                self.assertEqual(self.evaluate({"suppressed": value}), demo.decision("review", ["INVALID_SUPPRESSED"]))

    def test_every_timestamp_rejects_invalid_data(self):
        for field in ("checkout_at", "last_purchase_at", "last_reminder_at"):
            for value in ("bad", False, 0, [], {}, "2026-10-05T10:00:00"):
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.evaluate({field: value}), demo.decision("review", ["INVALID_" + field.upper()]))

    def test_every_future_timestamp_requires_review(self):
        for field in ("checkout_at", "last_purchase_at", "last_reminder_at"):
            with self.subTest(field=field):
                self.assertEqual(self.evaluate({field: "2026-10-05T12:00:00.000001Z"}), demo.decision("review", ["FUTURE_" + field.upper()]))

    def test_invalid_input_and_evaluation_time_require_review(self):
        for record in (None, [], "active", True):
            with self.subTest(record=record):
                self.assertEqual(demo.evaluate_case(record, NOW, POLICY), demo.decision("review", ["INVALID_INPUT"]))
        self.assertEqual(self.evaluate(now="bad"), demo.decision("review", ["INVALID_EVALUATED_AT"]))

    def test_policy_is_nonnegative_integer_data_not_boolean(self):
        for field in demo.POLICY_FIELDS:
            for value in (-1, 1.5, True, False, "3600", None, float("nan"), float("inf")):
                policy = {**POLICY, field: value}
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.evaluate(policy=policy), demo.decision("review", ["INVALID_POLICY"]))
            policy = dict(POLICY)
            del policy[field]
            self.assertEqual(self.evaluate(policy=policy), demo.decision("review", ["INVALID_POLICY"]))
        self.assertEqual(self.evaluate(policy={**POLICY, "unknown": 1}), demo.decision("review", ["INVALID_POLICY"]))

    def test_checkout_window_cannot_be_shorter_than_delay(self):
        self.assertEqual(self.evaluate(policy={**POLICY, "checkout_window_seconds": 3599}), demo.decision("review", ["INVALID_POLICY"]))

    def test_zero_delay_window_and_cooldown_are_explicitly_allowed(self):
        policy = dict.fromkeys(demo.POLICY_FIELDS, 0)
        self.assertEqual(self.evaluate({"checkout_at": NOW, "last_reminder_at": NOW}, policy=policy), demo.decision("eligible", ["ALL_RULES_MET"]))
        self.assertEqual(self.evaluate({"checkout_at": "2026-10-05T11:59:59.999999Z"}, policy=policy), demo.decision("ineligible", ["CHECKOUT_CONTEXT_EXPIRED"]))

    def test_negative_age_never_passes_even_with_zero_delay(self):
        self.assertEqual(self.evaluate({"checkout_at": "2026-10-05T12:00:00.000001Z"}, policy={**POLICY, "minimum_delay_seconds": 0}), demo.decision("review", ["FUTURE_CHECKOUT_AT"]))

    def test_equal_window_and_delay_have_one_valid_instant(self):
        policy = {**POLICY, "checkout_window_seconds": 3600}
        self.assertEqual(self.evaluate({"checkout_at": "2026-10-05T11:00:00Z"}, policy=policy)["outcome"], "eligible")
        self.assertEqual(self.evaluate({"checkout_at": "2026-10-05T10:59:59.999999Z"}, policy=policy)["reasons"], ["CHECKOUT_CONTEXT_EXPIRED"])

    def test_policy_can_exceed_datetime_range_without_overflow(self):
        policy = dict.fromkeys(demo.POLICY_FIELDS, 10 ** 100)
        self.assertEqual(self.evaluate(policy=policy), demo.decision("ineligible", ["MINIMUM_DELAY_NOT_MET"]))

    def test_wide_date_ranges_preserve_microsecond_boundaries(self):
        now = "9000-01-01T00:00:00Z"
        start = "1000-01-01T00:00:00Z"
        delay = demo.elapsed_microseconds(demo.parse_timestamp(now), demo.parse_timestamp(start)) // 1_000_000
        policy = {"minimum_delay_seconds": delay, "checkout_window_seconds": delay, "cooldown_seconds": 0}
        self.assertEqual(self.evaluate({"checkout_at": start}, now=now, policy=policy)["outcome"], "eligible")
        self.assertEqual(self.evaluate({"checkout_at": "1000-01-01T00:00:00.000001Z"}, now=now, policy=policy)["reasons"], ["MINIMUM_DELAY_NOT_MET"])

    def test_purchase_comparison_uses_instant_not_wall_clock_or_string(self):
        self.assertEqual(self.evaluate({"last_purchase_at": "2026-10-05T12:00:00+03:00"})["outcome"], "eligible")
        self.assertEqual(self.evaluate({"last_purchase_at": "2026-10-05T05:00:00-05:00"})["reasons"], ["PURCHASE_AT_OR_AFTER_CHECKOUT"])

    def test_dst_offset_change_uses_elapsed_time(self):
        self.assertEqual(self.evaluate({"checkout_at": "2026-11-01T01:30:00-04:00"}, now="2026-11-01T01:30:00-05:00"), demo.decision("eligible", ["ALL_RULES_MET"]))

    def test_review_precedence_retains_all_validation_reasons(self):
        record = {"consent": "inactive", "suppressed": "false", "checkout_at": "bad"}
        self.assertEqual(demo.evaluate_case(record, NOW, POLICY), demo.decision("review", ["INVALID_SUPPRESSED", "INVALID_CHECKOUT_AT", "MISSING_LAST_PURCHASE_AT", "MISSING_LAST_REMINDER_AT"]))

    def test_inputs_are_not_mutated(self):
        record, policy = copy.deepcopy(BASE), copy.deepcopy(POLICY)
        demo.evaluate_case(record, NOW, policy)
        self.assertEqual(record, BASE)
        self.assertEqual(policy, POLICY)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.suite = demo.load_suite(FIXTURE)

    def test_summary_matches_authored_case_set(self):
        self.assertEqual(demo.build_report(self.suite)["summary"], {
            "cases": 30, "expected_matches": 30, "eligible": 7, "ineligible": 8, "review": 15,
            "naive_eligible_but_ineligible": 5, "naive_eligible_but_review": 9,
        })

    def test_naive_rule_misses_seeded_business_failures(self):
        report = demo.build_report(self.suite)
        self.assertEqual({row["case_id"] for row in report["cases"] if row["naive_outcome"] == "eligible" and row["outcome"] == "ineligible"}, {
            "suppressed-profile", "purchase-after-checkout", "purchase-exactly-at-checkout",
            "checkout-window-one-microsecond-expired", "cooldown-one-microsecond-short",
        })

    def test_expectations_do_not_control_decision(self):
        self.suite["cases"][0]["expected"] = demo.decision("ineligible", ["CONSENT_INACTIVE"])
        row = demo.build_report(self.suite)["cases"][0]
        self.assertEqual(row["outcome"], "eligible")
        self.assertFalse(row["expected_match"])

    def test_deterministic_exact_report_regeneration(self):
        first = json.dumps(demo.build_report(self.suite), indent=2, ensure_ascii=True) + "\n"
        self.assertEqual(first.encode("utf-8"), REPORT.read_bytes())
        self.assertEqual(first, json.dumps(demo.build_report(copy.deepcopy(self.suite)), indent=2, ensure_ascii=True) + "\n")

    def test_schema_rejects_unusable_suites(self):
        for update in (
            {"schema_version": True}, {"schema_version": 2}, {"synthetic_only": False},
            {"synthetic_only": 1}, {"evaluated_at": "bad"}, {"policy": {}}, {"cases": []},
            {"cases": None}, {"unknown": "field"},
        ):
            with self.subTest(update=update), self.assertRaises(demo.InputError):
                demo.build_report({**self.suite, **update})
        for value in (None, [], "", {}):
            with self.subTest(value=value), self.assertRaises(demo.InputError):
                demo.build_report(value)

    def test_case_schema_rejects_duplicate_or_invalid_ids(self):
        self.suite["cases"].append(copy.deepcopy(self.suite["cases"][0]))
        with self.assertRaises(demo.InputError):
            demo.build_report(self.suite)
        self.suite["cases"].pop()
        for value in (None, 1, "", "Synthetic@example.com", "bad label", "a" * 65):
            self.suite["cases"][0]["id"] = value
            with self.subTest(value=value), self.assertRaises(demo.InputError):
                demo.build_report(self.suite)

    def test_case_schema_rejects_missing_fields_or_invalid_expectations(self):
        for case in (None, {}, {**self.suite["cases"][0], "unknown": True}):
            with self.subTest(case=case), self.assertRaises(demo.InputError):
                demo.build_report({**self.suite, "cases": [case]})
        for expected in (None, {}, demo.decision("send", ["ALL_RULES_MET"]), demo.decision("eligible", []), demo.decision("eligible", [None]), demo.decision("eligible", ["arbitrary sentence"])):
            case = {**self.suite["cases"][0], "expected": expected}
            with self.subTest(expected=expected), self.assertRaises(demo.InputError):
                demo.build_report({**self.suite, "cases": [case]})

    def test_report_has_no_raw_profile_values_and_never_accesses_network(self):
        self.suite["cases"][0]["input"]["last_purchase_at"] = "PRIVATE_RAW_VALUE"
        with patch("socket.socket", side_effect=AssertionError("Network accessed")), patch("socket.getaddrinfo", side_effect=AssertionError("DNS accessed")):
            report = demo.build_report(self.suite)
        self.assertNotIn("PRIVATE_RAW_VALUE", json.dumps(report))
        self.assertEqual(report["cases"][0]["outcome"], "review")


class CLITests(unittest.TestCase):
    def run_cli(self, path):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = demo.main([str(path)])
        return code, output.getvalue(), errors.getvalue()

    def test_success_is_expected_decision_match_never_send_approval(self):
        code, output, errors = self.run_cli(FIXTURE)
        self.assertEqual(code, 0)
        self.assertEqual(output.encode("utf-8"), REPORT.read_bytes())
        self.assertEqual(errors, "")
        self.assertIn("not send approval", output)

    def test_expectation_mismatch_exits_one_with_actual_report(self):
        suite = demo.load_suite(FIXTURE)
        suite["cases"][0]["expected"]["reasons"] = ["WRONG_EXPECTATION"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(json.dumps(suite), encoding="utf-8")
            code, output, errors = self.run_cli(path)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["summary"]["expected_matches"], 29)
        self.assertEqual(errors, "")

    def test_invalid_input_exits_two_without_a_partial_report(self):
        for content in (b"not json", b"\xff", b"{}", b"[]", b"{\"schema_version\":1,\"schema_version\":1}", b"{\"x\":NaN}", b"{\"x\":Infinity}"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "cases.json"
                path.write_bytes(content)
                code, output, errors = self.run_cli(path)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("Input error", errors)

    def test_unreadable_missing_or_oversized_input(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in (Path(directory), Path(directory) / "absent.json"):
                self.assertEqual(self.run_cli(path)[0], 2)
            path = Path(directory) / "large.json"
            path.write_bytes(b" " * (demo.MAX_INPUT_BYTES + 1))
            self.assertEqual(self.run_cli(path)[0], 2)

    def test_duplicate_keys_and_nonfinite_json_rejected_by_loader(self):
        with self.assertRaises(demo.InputError):
            demo.unique_object([("consent", "active"), ("consent", "inactive")])
        with self.assertRaises(demo.InputError):
            demo.reject_constant("NaN")


if __name__ == "__main__":
    unittest.main()
