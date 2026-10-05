# Repeat Foundry Email Preflight

Offline email preflight plus a synthetic lifecycle decision case study, with reproducible tests and a practical QA handoff.

**For DTC marketers and agency teams reviewing email before platform testing.** Catch unfinished links, missing tracking fields, image-alt omissions, and selected personalization risks; then give the campaign owner a clear list of what still needs human verification.

This is a self-directed portfolio project by **Nimrod Ogachi, founder of Repeat Foundry**. The examples are fictional, and there are no client-results or revenue claims. The original repository URL, `Journey-`, is retained; this project gives it a concrete purpose.

## Discuss your own email journey

[**Post-purchase email copy review and QA handoff on Contra →**](https://contra.com/s/PqMEQRNZ-post-purchase-email-copy-review-and-qa-handoff)

One journey, up to three emails. Share the journey type, goal, and desired deliverable; scope and pricing are agreed first. You can also [email Nimrod](mailto:ogachi.nimrod@gmail.com). Keep credentials and customer records out of your enquiry.

## Start with a work sample

1. Compare the [unfinished welcome email](examples/welcome-before.html) with the [reviewed static example](examples/welcome-reviewed.html).
2. Read the [before report](examples/welcome-before.report.json) and [reviewed report](examples/welcome-reviewed.report.json).
3. Use the [lifecycle QA handoff](docs/lifecycle-qa-handoff.md) to assign platform tests, evidence, fixes, and release responsibility.
4. Inspect the [lifecycle decision case study](docs/lifecycle-decision-case-study.md): explicit rules, 30 synthetic scenarios, and a reproducible decision report.
5. See [three buyer use-case hypotheses](docs/buyer-use-cases.md). These are possible workflows, not validated customer demand or adoption.

The unfinished fixture has **4 errors and 4 warnings**. The reviewed fixture has **0 errors and 0 warnings in the implemented static checks**. It still requires a real sender footer, platform preview, consent/eligibility checks, live-link tests, and owner approval. It is not a send-ready campaign.

## Run it

Requires Python 3.10 or newer. No packages, accounts, API keys, or customer data are needed. Download this repository using GitHub's **Code → Download ZIP**, extract it, and open a terminal in its folder. If Python is already installed, run:

```sh
python3 emailqa.py examples/welcome-before.json
# Expected exit code: 1, because this fixture deliberately contains errors.

python3 emailqa.py examples/welcome-reviewed.json --strict
# Expected exit code: 0. Manual review is still required.

python3 -m unittest discover -s tests -v
```

On Windows, use `py` in place of `python3` if that is how Python is installed.

Example text output:

```text
BLOCKERS_FOUND: 4 error(s), 4 warning(s)
[ERROR] MISSING_PREHEADER (preheader): Provide non-empty preheader text.
...
Manual review still required:
...
```

## Lifecycle decision case study

A second runnable work sample tests a fictional checkout-reminder policy before it is translated into platform settings. It covers consent, suppression, a purchase after checkout, event recency, minimum delay, reminder cooldown, and invalid or missing timestamps.

```sh
python3 lifecycle_demo.py examples/lifecycle-scenarios.json
```

The [checked-in report](examples/lifecycle-scenarios.report.json) evaluates **30 synthetic scenarios** against explicit expected decisions: **7 eligible, 8 ineligible, and 15 needing review**. A deliberately incomplete comparison rule marks 5 ineligible scenarios and 9 review-needed scenarios eligible. These are intentionally seeded examples, not measured production defects or customer results.

The [case study and decision log](docs/lifecycle-decision-case-study.md) explain the rules, exact time boundaries, assumptions, and limits. An `eligible` result means only that this fictional model's conditions match. It never authorizes a send, establishes legal consent, or verifies a Klaviyo/Shopify configuration. Exit `0` means all expected fixture decisions matched; `1` means a mismatch; `2` means invalid input.

## Check your own draft locally

Put real working files in the ignored `private/` directory. Never commit customer data, credentials, account exports, or recipient-specific links. Use a JSON manifest with exactly these three string fields:

```json
{
  "subject": "Your subject line",
  "preheader": "Your preview text",
  "html_file": "email.html"
}
```

`html_file` is resolved relative to the manifest. The tool reads that local file and the manifest as UTF-8, up to 2 MB each. Only run manifests you trust; the HTML path can point to another readable local file. HTML is parsed as text, never executed or rendered. The subject and preheader are supplied values; the tool does not confirm that the sending platform uses them.

```sh
python3 emailqa.py private/draft.json
python3 emailqa.py private/draft.json --format json
python3 emailqa.py private/draft.json --strict
```

JSON reports have a stable `schema_version`, summary counts, rule codes, severity, location, and manual checks. Reports omit draft copy and URL values by design. Review any report before sharing it because findings still describe aspects of the draft. No network requests, analytics, telemetry, uploads, or sends are performed.

**Exit codes:** `0` = no errors detected; `1` = errors detected, or any warnings with `--strict`; `2` = invalid/unreadable input or CLI usage. A zero exit code is never send approval.

## What is checked

| Check | Result | Boundary |
| --- | --- | --- |
| Empty subject, preheader, or HTML | Error | Supplied files only |
| Subject over 60 characters | Warning | Project review threshold, not a universal platform limit |
| Empty, fragment-only, relative, unsupported, or malformed destinations | Error | Static syntax, not live HTTP status |
| Example, staging, local, or non-public destinations | Error | Recognized host patterns; not DNS validation |
| HTTP links or image sources | Warning | Does not visit or upgrade the destination |
| Missing/blank or duplicate UTM fields; mixed campaign names | Warning | Non-utility links within one message; no platform-added tracking visibility |
| Missing image alt attribute | Warning | Empty `alt=""` is allowed for decorative images; meaning still needs review |
| Recognized unsubscribe hook absent | Error | Limited heuristic, not proof of consent or compliance |
| First-name variable without a recognized quoted fallback | Warning | Klaviyo-style hint; does not evaluate template logic |
| Dynamic destination | Warning | Must be resolved and tested in the platform |
| Script element | Error | Never executed |

Errors are issues to resolve or explicitly review before proceeding. Warnings are review prompts and can be legitimate in context. See the source and tests for the exact implemented rules.

## Important limits

- No Klaviyo, Shopify, CRM, or email-provider integration. No customer profiles or account settings are accessed.
- No email rendering, HTML validation, CSS inspection, accessibility certification, deliverability prediction, or spam score.
- No HTTP requests, redirect following, DNS checks, image downloads, or verification of offers and landing pages.
- Template code is not evaluated. Conditional content, custom unsubscribe implementations, and localization can produce missed issues or false positives.
- A recognized unsubscribe tag/link does not prove a visible or working opt-out. The tool does not verify a postal address, legal requirements, consent, sending permissions, or audience eligibility.
- Previews and live sends can behave differently. Complete the [manual handoff](docs/lifecycle-qa-handoff.md), including the platform's actual flow context.

## Development and verification

See the [project updates](CHANGELOG.md) and [contribution guide](CONTRIBUTING.md) for changes, reproducible bug reports, and privacy-safe contributions.

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile emailqa.py lifecycle_demo.py
```

Tests cover both email fixtures, severity and exit codes, placeholder boundaries, invalid URL handling, UTF-8/size limits, tracking, fallback hints, opt-out detection, and report redaction. The lifecycle suite additionally checks timestamp and delay boundaries, invalid/unknown data, decision reasons, and exact report regeneration. GitHub Actions runs the same checks on Python 3.10, 3.12, and 3.13 when workflows are available. See [test workflow](.github/workflows/tests.yml) for its exact scope.

To reproduce the checked-in reports:

```sh
python3 emailqa.py examples/welcome-before.json --format json > examples/welcome-before.report.json
# Exit 1 is expected for this deliberately broken fixture.
python3 emailqa.py examples/welcome-reviewed.json --format json > examples/welcome-reviewed.report.json
```

The tools and synthetic tests were prepared with AI assistance and reviewed through executable tests. Treat this as an inspectable work sample; it does not establish production deployment or client experience.

## Reference guidance

The design keeps static checks separate from the platform testing described in official Klaviyo guidance:

- [Preview and send test emails](https://help.klaviyo.com/hc/en-us/articles/115005081907)
- [Message personalization reference](https://help.klaviyo.com/hc/en-us/articles/4408802648731)
- [Test and preview flow messages](https://help.klaviyo.com/hc/en-us/articles/115002774972)

References checked on 5 October 2026. This project is independent and is not affiliated with or certified by Klaviyo or Shopify.

## Discuss a scoped review

For lifecycle email copy, a defined QA review, or a practical flow specification:

- [View the retention marketing portfolio](https://nimrod-ogachi-klaviyo.netlify.app/portfolio/)
- [Explore Repeat Foundry](https://nimrod-ogachi-klaviyo.netlify.app/repeat-foundry/)
- [Email Nimrod Ogachi](mailto:ogachi.nimrod@gmail.com)

Share the business question and desired deliverable first. Do not send credentials or customer exports through a public issue.

## License

New code and documentation in this project are provided under the [MIT License](LICENSE). Third-party names and linked guidance remain their owners' property.
