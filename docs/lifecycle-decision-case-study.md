# Checkout-reminder decision QA: a synthetic case study

**Question:** Would a reminder rule make the intended decision when consent, suppression, purchase timing, data quality, or repeat-message timing changes?

This self-directed work sample adds an inspectable decision-logic component to the email preflight project. It is a **fictional rule**, written in standard-library Python, with deliberately seeded edge cases and explicit expected outcomes. It is not a Klaviyo implementation, a customer case study, a compliance assessment, or send approval. No accounts, customer records, network calls, or email sends are involved.

## Inspect the evidence

1. [Scenario inputs and authored expectations](../examples/lifecycle-scenarios.json)
2. [Deterministic decision report](../examples/lifecycle-scenarios.report.json)
3. [Rule implementation](../lifecycle_demo.py)
4. [Regression and boundary tests](../tests/test_lifecycle_demo.py)

The checked-in suite contains **30 synthetic cases: 7 eligible, 8 ineligible, and 15 requiring review**. All 30 match their authored expected outcomes and reason lists. These are fixture results, not production results, customer outcomes, measured error rates, or time savings. Passing tests means the implementation agrees with this specification and its tests; it does not independently validate the policy.

## Fictional business brief

A fictional shop wants to assess a single checkout reminder at a fixed point in time. Its proposed local rule requires:

- Active consent and an explicitly unsuppressed profile
- A known checkout at least **1 hour** old and no more than **24 hours** old
- No recorded purchase at or after that checkout
- At least **7 days** since the last checkout reminder, if one exists
- Complete, valid input for every required field

The fixture evaluation time is **2026-10-05 12:00:00 UTC**. It never reads the system clock. The thresholds are made-up project choices, not platform defaults or recommended marketing/legal settings.

### Snapshot contract

Each case is one independent fictional profile snapshot. Cases are not a chronological stream or real people. Required fields are:

| Field | Meaning in this demo | Invalid or missing data |
| --- | --- | --- |
| `consent` | Exactly `active` or `inactive` for this hypothetical reminder | Review; no truthiness or guessed consent |
| `suppressed` | A JSON boolean, independently checked even with active consent | Review; strings and integers are rejected |
| `checkout_at` | Timestamp of the checkout being evaluated | Review, including explicit `null` |
| `last_purchase_at` | Latest known purchase as of evaluation, or explicit `null` meaning known absence | Review if omitted, invalid, or in the future |
| `last_reminder_at` | Latest known checkout reminder as of evaluation, or explicit `null` meaning known absence | Review if omitted, invalid, or in the future |

Explicit `null` history values are assertions made by the synthetic fixture author. They must not be interpreted as “the data feed was unavailable.” A real system would need trustworthy evidence of completeness, identity resolution, event scope, and freshness. This program cannot establish any of those facts.

Unknown input fields also require review. This avoids silently ignoring a typo or an attempted extra override. Reports include synthetic case IDs and reason codes, not raw profile values. They still include the suite's evaluation time and configured thresholds. The `synthetic_only` marker is an author declaration, not an anonymization or personal-data detector: do not put real data into these fixtures or commit it publicly.

## Decision order and boundaries

1. **Validate before eligibility.** Missing fields, unsupported values, unknown fields, malformed timestamps, and future events produce `review`. All validation reasons are retained in stable order. Business eligibility is not evaluated until the snapshot is valid.
2. **Collect all business-rule blockers.** Check consent, suppression, purchase, delay, checkout recency, and reminder cooldown in that order. Any blocker produces `ineligible` with every applicable reason.
3. **Otherwise return `eligible` with `ALL_RULES_MET`.** This means only that this fictional snapshot satisfies these local rules. It does not authorize sending.

| Boundary | Explicit decision |
| --- | --- |
| Checkout age exactly the minimum delay | Delay passes |
| Checkout age one microsecond below the minimum | `MINIMUM_DELAY_NOT_MET` |
| Checkout age exactly the maximum window | Recency passes |
| Checkout age one microsecond beyond the window | `CHECKOUT_CONTEXT_EXPIRED` |
| Reminder age exactly the cooldown | Cooldown passes |
| Reminder age one microsecond below the cooldown | `REMINDER_COOLDOWN_ACTIVE` |
| Purchase exactly at checkout time | `PURCHASE_AT_OR_AFTER_CHECKOUT`; a timestamp tie is conservatively blocking |
| Purchase before checkout | Does not block this fictional rule |
| Any event after the evaluation instant | Review; do not silently clamp negative ages |

Policy values are **nonnegative integer seconds**; booleans, floats, negative values, missing keys, and extra keys are invalid. The checkout window must be at least the minimum delay. Zero is allowed explicitly: with a zero window and zero delay, only a checkout at the evaluation instant satisfies the age bounds. A zero cooldown imposes no wait for a non-future reminder.

Timestamps must use `YYYY-MM-DDTHH:MM:SS`, optionally 1–6 fractional digits, followed by `Z` or an explicit `+HH:MM`/`-HH:MM` offset. Naive times, named timezones, `-00:00` (unknown offset), impossible dates, leap seconds, and values outside the supported datetime range are rejected. Instants are normalized to UTC before comparison. Exact integer microseconds preserve boundaries without floating-point rounding. Tests cover equivalent offsets, an offset change across daylight-saving time, and very widely separated dates.

## Seeded failures and fixes

The intentionally incomplete baseline checks only **active consent plus a checkout at least one hour old**. It shares strict checkout timestamp parsing so malformed dates do not crash the comparison, but it omits suppression, purchase history, maximum checkout age, cooldown, and full input validation. It is a teaching baseline, not claimed prior client code.

| Seeded case | Baseline | Corrected result and fix |
| --- | --- | --- |
| `suppressed-profile` | Eligible | Ineligible: check suppression separately from consent |
| `purchase-after-checkout` | Eligible | Ineligible: compare latest purchase against this checkout |
| `purchase-exactly-at-checkout` | Eligible | Ineligible: define the equal-timestamp decision explicitly |
| `checkout-window-one-microsecond-expired` | Eligible | Ineligible: apply an inclusive maximum checkout age |
| `cooldown-one-microsecond-short` | Eligible | Ineligible: apply the repeat-reminder cooldown |

The baseline also labels **9 incomplete or inconsistent snapshots eligible**, whereas the corrected evaluator returns review: missing suppression, string suppression, missing purchase history, missing reminder history, a future purchase, a future reminder, an impossible purchase date, an unknown reminder offset, and an unexpected input field. Unknown data must not silently stand in for a successful eligibility check.

The remaining cases verify permitted behavior, exact boundaries, explicit negatives, equivalent timezones, and the review path. Every individual input, expected outcome, and expected reason list is visible in the scenario file. No random seed or external service is needed.

## Decision log

| Design choice | Why it was made | What remains outside this demo |
| --- | --- | --- |
| Three outcomes instead of a single boolean | Separates a known rule blocker from input that cannot be evaluated safely | Operational owners must define what to do with review cases |
| Review takes precedence over a known blocker | Incomplete data stays visible; it cannot become a positive decision later through a partial fix | Does not override an actual suppression or grant permission |
| Require explicit history fields, allowing known-absence `null` | Distinguishes “none recorded in this complete fixture” from an omitted field | Real ingestion and history completeness |
| Block purchase ties | Avoids assuming an order inside an unresolved same-instant boundary | Event IDs, attribution, deduplication, and finer ordering |
| Return every applicable business reason | Makes a decision inspectable without repeatedly fixing one blocker at a time | A live monitoring or issue-management workflow |
| Use fixed evaluation time and byte-stable reports | Enables repeatable review and detection of report drift | Live reevaluation and race-condition prevention |
| Keep expectations separate from the evaluator | Changing an expectation does not change the actual decision; it fails the CLI check | Independent validation of business requirements |

## Run and reproduce

Requires Python 3.10 or newer. No installation, packages, credentials, or internet are needed. Run from the repository root:

```sh
python3 lifecycle_demo.py examples/lifecycle-scenarios.json
python3 -m unittest discover -s tests -v
python3 -m py_compile emailqa.py lifecycle_demo.py
```

To regenerate the checked-in JSON report:

```sh
python3 lifecycle_demo.py examples/lifecycle-scenarios.json > examples/lifecycle-scenarios.report.json
python3 -m unittest discover -s tests -v
```

The tests compare regenerated report bytes against the committed report, check every authored outcome and exact reason order, deliberately change an expectation to confirm failure, exercise malformed inputs, and block socket/DNS calls during a report test. They also verify that the evaluator does not mutate its inputs or echo raw profile values into reports.

**CLI exit codes:** `0` means every outcome and reason list matches its explicit expectation; `1` means at least one expectation mismatches; `2` means invalid/unreadable suite or CLI usage. Zero does not mean all cases are eligible and never means send approval. A structurally invalid suite or invalid global policy/evaluation time produces no partial report. The lower-level evaluator returns `review` for invalid policy or evaluation time; invalid profile data in a structurally valid suite yields an explicit per-case `review` result.

The loader reads UTF-8 JSON, up to 2 MB, and rejects duplicate keys and non-finite JSON numbers. The CLI writes only to standard output; shell redirection is the explicit local report-writing step.

## Production handoff, not production proof

Real platform controls, consent requirements, and legal duties vary by channel, jurisdiction, business, and platform. A consent flag is not evidence that those duties have been met. Before any real implementation, an accountable owner must verify the actual consent evidence and suppression behavior, event definitions and freshness, filtering/reentry rules, concurrent purchases, message frequency controls, and platform behavior at the time of sending. Any legal interpretation needs appropriate qualified review.

This demo does not implement an event pipeline, queue, scheduler, platform API, consent capture, unsubscribe processing, message rendering, delivery, transactional locking, retries, idempotency, or live send-time reevaluation. A purchase arriving after this fixed snapshot can change the decision. Use the existing [lifecycle QA handoff](lifecycle-qa-handoff.md) for the separate manual testing discussion.

The code, fixtures, and documentation were prepared with AI assistance and checked through executable tests. The deliverable demonstrates a reproducible QA method: state assumptions, make boundaries explicit, seed failures, fix the decision logic, and retain an inspectable decision record.
