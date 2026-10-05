# Lifecycle email QA handoff template

Repeat Foundry Email Preflight · Nimrod Ogachi, Repeat Foundry

Use this template to hand a reviewed email and its remaining questions to the person responsible for the campaign or flow. This is a reusable template from a self-directed portfolio project. Blank fields and the test cases below are not evidence that a review has happened.

The Python CLI runs locally, without network calls, external dependencies, or platform integration. It checks supplied content for subject/preheader issues, placeholder or malformed links, missing UTMs, inconsistent campaign names, missing image alt attributes, recognized unsubscribe hooks, and first-name fallback hints. Its output never constitutes send approval. It cannot establish live link behavior, audience eligibility, consent, rendering, deliverability, or business results.

## Record the exact version

- Message and purpose: [name, campaign or flow, intended action]
- Intended audience and exclusions: [approved brief reference]
- Platform draft reference: [private link or ID]
- Local input and version: [filename, commit or content hash]
- CLI invocation and report: [exact command, report location, run time and timezone]
- Platform version checked against that input: [reference and check time]
- Prepared by: [name]
- Campaign or flow owner: [name; leave unassigned if unknown]
- Current handoff status: [changes needed / manual testing needed / ready for owner review]

Keep customer records, event payloads, credentials, and recipient-specific links out of public repositories. Use synthetic fixtures here. Keep any authorized platform evidence in the team's approved private location and reference it without copying personal data into this template.

## Findings and unresolved assumptions

Repeat this record for each meaningful finding or unknown. A clean CLI report means only that its implemented checks found no issues in those inputs.

- Finding ID and location: [rule, field, or element]
- Observed evidence: [report excerpt or private evidence reference]
- Specific risk: [what could happen to which recipient or part of the journey]
- Severity and reason: [high / medium / low, with context]
- Proposed correction or question: [specific next step]
- Owner: [named person]
- State: [open / fixed awaiting retest / verified / accepted exception]
- Retest evidence: [version, observed result, tester, timestamp]
- Exception decision, if any: [decision owner and rationale]

Suggested triage: **High** covers a suspected opt-out failure, wrong audience, duplicate message, or wrong primary offer/destination. **Medium** covers attribution gaps, awkward fallback copy, or information lost when images are unavailable. **Low** covers a minor cosmetic issue with no known effect on the action. These are review priorities, not automatic release rules; record the actual consequence.

Keep assumptions visible. For example: “Platform-added UTMs have not been checked on a received test”; “The purchaser exclusion window has no approved definition”; or “This empty alt attribute may be deliberate because the image is decorative.” Assign an owner and the evidence needed to resolve each one. Do not quietly turn an assumption into a pass.

## Manual platform tests

Assign a named tester before starting. For every case, record: **expected result, observed result, pass/fail/not run/not applicable, evidence, tested version, tester, and timestamp**. Explain any not-applicable result.

These are proposed tests for this handoff, not findings about an account. Use approved internal test identities and an isolated test setup. Obtain the account owner's authorization before changing settings, creating events, placing test orders, or sending live tests. Never add customers to a test audience.

1. **Opt-outs and suppression.** Test an eligible internal subscriber and an internal identity already opted out. Confirm the latter is excluded as intended. For the eligible identity, exercise the unsubscribe journey in an authorized live test, then inspect its resulting status and future eligibility. Save the outcome, not just a screenshot of a footer. Owner: [name].

2. **Entry and send-time eligibility.** Write the intended trigger, filters, exclusions, and timing in plain language. Check a qualifying identity and one that fails each important condition, including a status change during a delay. Compare actual inclusion, exclusion, and branch behavior with the brief. Owner: [name].

3. **Purchasers and duplicate events.** For a recovery message, test someone who purchases before the reminder is due. Separately test repeated checkout events and a repeat purchaser. Agree first whether each scenario should suppress, re-enter, or receive another message; verify the configured behavior rather than assuming deduplication. Owner: [name].

4. **Event variables and fallback copy.** Check the correct trigger event, missing first name, missing optional event fields, and multiple products. Inspect names, prices, quantities, images, and conditional blocks. A syntactically plausible tag or detected fallback does not prove correct output. Owner: [name].

5. **Destinations and attribution.** Open every actionable link in an authorized received test. Verify the final destination after redirects, product or variant, offer, and expected query parameters. Compare received UTMs with the agreed naming plan, including any platform-added values. The CLI never visits URLs. Owner: [name].

6. **Device and inbox rendering.** Inspect desktop and mobile previews and the agreed inbox/device set. Check subject/preheader truncation, spacing, readable text, tappable actions, and images-off behavior. Review alt text for meaning, including whether an empty value is deliberate. The CLI does not render email or audit accessibility. Owner: [name].

7. **Final version and release responsibility.** Confirm that the platform draft matches the reviewed content and that relevant tests were repeated after fixes. Record unresolved exceptions, the person responsible for the release decision, and the separate decision reference. Owner: [name].

## Klaviyo testing notes

Klaviyo separates content preview from flow-logic testing. Its trigger preview helps inspect entry/filter behavior; Manual mode can queue messages for review instead of sending automatically. Plan changes with the account owner before using those controls. [Flow testing guidance](https://help.klaviyo.com/hc/en-us/articles/115002774972).

Preview unsubscribe links can lead to placeholder pages. Klaviyo documents unsubscribe tags and a `default` filter for missing profile values; neither tag presence nor fallback detection verifies the recipient's live experience. [Personalization reference](https://help.klaviyo.com/hc/en-us/articles/4408802648731).

Use desktop/mobile previews and inbox tests for rendering. Validate send-time behavior with an authorized live test. A campaign test does not reproduce metric-triggered flow event content; that requires the corresponding flow trigger. [Email preview and test guidance](https://help.klaviyo.com/hc/en-us/articles/115005081907).

Official references checked on 5 October 2026. Account features and guidance can change. This template provides operational review prompts, not legal advice, a compliance assessment, or guarantees of delivery or performance.
