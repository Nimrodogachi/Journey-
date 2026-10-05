# Project updates

## 2026-10-05: Lifecycle decision QA work sample

Added a second runnable component for a fictional checkout-reminder policy:

- 30 synthetic cases with explicit expected outcomes and reason codes.
- Consent, suppression, purchase timing, event recency, delay, cooldown, and timestamp boundary checks.
- A comparison with a deliberately incomplete consent-and-minimum-delay rule.
- A reproducible JSON report and [case study with a decision log](docs/lifecycle-decision-case-study.md).

The fixture results are 7 eligible, 8 ineligible, and 15 needing review. The incomplete rule marks 5 of the ineligible cases and 9 of the review cases eligible. These examples were intentionally designed to illustrate missed conditions; they are not customer data or evidence of production impact.

An eligible decision is a match to the fictional specification, never send approval. The component has no platform integration and performs no network requests or sends.

## 2026-10-05: Email preflight work sample

Published the offline email checker, fictional before/after email drafts and reports, a reusable [QA handoff](docs/lifecycle-qa-handoff.md), and [buyer use-case hypotheses](docs/buyer-use-cases.md). Added automated tests, an MIT license, and a GitHub Actions test matrix.

The unfinished email fixture has 4 errors and 4 warnings. The reviewed fixture clears the implemented static checks while retaining mandatory manual-review boundaries.
