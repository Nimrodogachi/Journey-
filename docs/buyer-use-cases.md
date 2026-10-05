# Buyer use case hypotheses

Repeat Foundry Email Preflight · Nimrod Ogachi, Repeat Foundry

These three scenarios explain where a local email preflight check might fit into a Shopify/DTC team's work. They are **use-case hypotheses**, not customer stories, buyer validation, paid engagements, or measured results. This self-directed portfolio project uses no client data and has no Shopify or Klaviyo integration.

The tool examines supplied content locally with Python's standard library. It makes no network calls, follows no links, and never approves a send. The proposed value is a clearer starting point for review; whether it improves a team's workflow still needs to be tested.

## 1 A DTC marketer reuses a launch email

**Situation.** A brand marketer duplicates last month's product-launch email. The copy is updated, but a secondary link could still carry the old campaign name, an image could lack alt text, or the preheader could still be a placeholder.

**Inputs.** A local HTML draft plus its subject and preheader. A synthetic draft is enough to evaluate the workflow; no customer export or account access is required.

**Proposed use.** Run the CLI before platform testing. Review the flagged links and fields against the campaign brief, fix relevant issues, and rerun on the revised file. Save the input version and report together.

**Handoff.** Give the campaign owner the revised draft, remaining findings, and a short list of manual checks. They still verify the offer, actual destinations, platform-added tracking, rendering, and intended audience.

**Hypothesis to test.** Does this surface overlooked carry-over content before the final review? Evaluate with intentionally seeded synthetic defects, missed defects, and false positives. No time saving or revenue effect has been measured.

## 2 A lifecycle marketer reviews a checkout reminder

**Situation.** A Shopify/DTC marketer prepares an abandoned-checkout message with a first-name greeting and product details. The content can look reasonable while the selected event data or purchaser exclusion is wrong.

**Inputs.** A sanitized local email draft and the intended journey rules in plain language. Use synthetic names and product data; keep live profile and order data out of the repository.

**Proposed use.** Review static link issues, image alt attributes, recognized unsubscribe hooks, and first-name fallback hints. Carry unresolved personalization questions into the [QA handoff](lifecycle-qa-handoff.md).

**Handoff.** The flow owner tests the matching event context, missing data, opted-out identities, eligibility changes, a purchase before the reminder, and repeated checkout events. The CLI cannot inspect the integration, event history, filters, or actual recipients. Klaviyo provides separate content and flow-logic testing tools. [Official flow testing guidance](https://help.klaviyo.com/hc/en-us/articles/115002774972).

**Hypothesis to test.** Does the combined report and handoff make content questions and flow questions easier to assign? Evaluate whether another reviewer can reproduce each finding and identify the remaining platform test without explanation.

## 3 An agency hands email work to a brand team

**Situation.** An agency finishes several lifecycle email drafts. The brand needs to know which versions were reviewed, what changed, and which questions still need its decision before platform work continues.

**Inputs.** Approved local drafts, subject/preheader values, the campaign naming plan, and a version reference for each file. Account credentials and customer lists are unnecessary for the static review.

**Proposed use.** Run each email through the CLI separately. Review reports with the brief, then manually reconcile campaign naming across messages. Record each meaningful issue with evidence, risk, owner, and retest status using the handoff template.

**Handoff.** Deliver the reviewed versions and reports, unresolved assumptions, named manual-test owners, and the brand's separate release-decision reference when available. The template does not assume an agency has permission to edit settings or send tests.

**Hypothesis to test.** Can a reviewer pick up the work without asking which file is current or whether a warning was resolved? Check traceability and unresolved-owner questions in a synthetic handoff exercise. No agency adoption or client outcomes are claimed.

## What this portfolio demonstrates

The project offers a small, inspectable static-checking workflow and an explicit boundary between its findings and manual platform QA. The source, synthetic examples, tests, and handoff template can be reviewed directly. Platform implementation, commercial impact, and production use would each require separate evidence.
