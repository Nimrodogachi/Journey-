# Contributing

Useful contributions include a reproducible false positive, a missed static check, a clearer synthetic scenario, or a documentation correction.

## Report an issue safely

- Use a small fictional example that reproduces the behavior.
- Include the command, Python version, rule code or decision reason, expected behavior, and actual behavior.
- Remove names, addresses, account exports, recipient-specific URLs, tokens, and other private data before posting.
- Keep business enquiries and private project details out of public issues. The [README](README.md#discuss-a-scoped-review) lists a contact route.

## Propose a change

1. Keep the change focused and explain its scope and limitations.
2. Add a regression test for changed behavior, including a nearby boundary or false-positive case.
3. Run `python3 -m unittest discover -s tests -v` and `python3 -m py_compile emailqa.py lifecycle_demo.py`.
4. Regenerate any affected checked-in report. Do not change expected decisions merely to make a failing test pass; explain the rule change.
5. Open a pull request describing what changed and what was tested.

Keep the tools offline and dependency-free. Do not add telemetry, account connections, customer data, automatic email sends, or claims that a passing check proves consent, compliance, accessibility, deliverability, or send readiness.

For template or platform behavior that cannot be established by these tools, document the manual check instead of guessing a pass. Platform-specific features need separate evidence and a clearly stated scope.
