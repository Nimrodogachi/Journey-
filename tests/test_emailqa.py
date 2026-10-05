import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import emailqa


class AuditTests(unittest.TestCase):
    def check(self, body="", subject="Welcome", preheader="Start here"):
        return emailqa.audit(subject, preheader, body)

    def codes(self, body="", **kwargs):
        return [finding["code"] for finding in self.check(body, **kwargs)["findings"]]

    def test_valid_minimal_static_sample(self):
        report = self.check("<p>Hi {{ first_name|default:'there' }}</p>{% unsubscribe %}")
        self.assertEqual(report["summary"], {"errors": 0, "warnings": 0})
        self.assertEqual(report["status"], "STATIC_CHECKS_COMPLETE")
        self.assertTrue(report["manual_checks"])

    def test_missing_metadata_and_html(self):
        codes = self.codes(subject=" ", preheader=" ")
        for code in ("MISSING_SUBJECT", "MISSING_PREHEADER", "EMPTY_HTML", "UNSUBSCRIBE_NOT_DETECTED"):
            self.assertIn(code, codes)

    def test_long_subject_is_review_not_hard_failure(self):
        report = self.check("{% unsubscribe %}", subject="x" * 61)
        self.assertEqual(report["summary"], {"errors": 0, "warnings": 1})

    def test_subscribe_text_and_comment_do_not_count(self):
        for body in ("<p>You can unsubscribe later.</p>", "<!-- {% unsubscribe %} -->", "<style>{% unsubscribe %}</style>"):
            with self.subTest(body=body):
                self.assertIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(body))

    def test_recognized_unsubscribe_variants(self):
        for body in ("{% unsubscribe %}", "{% unsubscribe 'click here' %}", '<a href="{% unsubscribe_link %}">Unsubscribe</a>'):
            with self.subTest(body=body):
                self.assertNotIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(body))

    def test_unsubscribe_attributes_are_not_link_evidence(self):
        for body in (
            '<p title="{% unsubscribe %}">Welcome</p>',
            '<img src="https://shop.com/a.png" alt="{% unsubscribe %}">',
            '<div data-footer="{% unsubscribe %}">Welcome</div>',
            '<a href="#" title="{% unsubscribe %}">Unsubscribe</a>',
            '<img src="{% unsubscribe_link %}" alt="">',
        ):
            with self.subTest(body=body):
                self.assertIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(body))

    def test_unsubscribe_url_directive_needs_a_labelled_anchor(self):
        for body in (
            "{% unsubscribe_link %}",
            '<a href="{% unsubscribe_link %}"></a>',
            '<a href="{% unsubscribe_link %}">   </a>',
            '<a href="{% unsubscribe %}">Unsubscribe</a>',
        ):
            with self.subTest(body=body):
                self.assertIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(body))
        self.assertNotIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(
            '<a href="{% unsubscribe_link %}">Leave this list</a>'
        ))

    def test_malformed_unsubscribe_directive_is_not_recognized(self):
        for body in ("{% unsubscribe nonsense %}", "{% unsubscribe_link 'click' %}"):
            self.assertIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(body))

    def test_non_body_content_and_escaped_directive_are_not_evidence(self):
        for body in (
            "<head><title>{% unsubscribe %}</title></head>",
            "<template><p>{% unsubscribe %}</p></template>",
            "<textarea>{% unsubscribe %}</textarea>",
            "<p>&#123;% unsubscribe %}</p>",
            "<p>{% unsub<!-- comment -->scribe %}</p>",
        ):
            with self.subTest(body=body):
                self.assertIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(body))
        self.assertNotIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(
            '<head><style>p {color:red}</style></head>{% unsubscribe %}'
        ))

    def test_html_entities_preserve_labels_and_template_text(self):
        self.assertNotIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(
            '<a href="https://shop.com/unsubscribe">Unsubscr&#105;be</a>'
        ))
        self.assertNotIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(
            "{% unsubscribe 'Leave &amp; stop updates' %}"
        ))
        self.assertNotIn("FIRST_NAME_FALLBACK", self.codes(
            "{{ first_name|default:'friend &amp; teammate' }}{% unsubscribe %}"
        ))

    def test_plain_unsubscribe_url_is_heuristic_only(self):
        report = self.check('<a href="https://nimrod-ogachi-klaviyo.netlify.app/unsubscribe">Unsubscribe</a>')
        self.assertEqual(report["summary"], {"errors": 0, "warnings": 0})
        self.assertTrue(any("opt-out" in item for item in report["manual_checks"]))

    def test_bad_unsubscribe_url_does_not_count(self):
        for target in ("#", "", "https://example.com/unsubscribe", "http://brand.invalid/unsubscribe", "javascript:alert(1)"):
            with self.subTest(target=target):
                self.assertIn("UNSUBSCRIBE_NOT_DETECTED", self.codes(f'<a href="{target}">Unsubscribe</a>'))

    def test_placeholders_and_relative_links(self):
        for target in ("#", "#section", "", "/products", "products", "//shop.test/products"):
            with self.subTest(target=target):
                report = self.check(f'<a href="{target}">Shop</a>{{% unsubscribe %}}')
                self.assertGreater(report["summary"]["errors"], 0)

    def test_placeholder_host_boundaries(self):
        for host in ("example.com", "shop.example.net", "brand.test", "localhost", "127.0.0.1", "10.0.0.1", "staging.shop.com", "[::1]"):
            with self.subTest(host=host):
                self.assertIn("PLACEHOLDER_HOST", self.codes(f'<a href="https://{host}/">Shop</a>'))
        self.assertFalse(emailqa.placeholder_host("notexample.com"))

    def test_malformed_urls_never_crash(self):
        for target in ("https://[bad", "https://shop.com:bad/", "https:///empty", "https://shop.com:999999/", "https://user:secret@shop.com/", "https://shop.com/bad path"):
            with self.subTest(target=target):
                report = self.check(f'<a href="{target}">Shop</a>{{% unsubscribe %}}')
                self.assertGreater(report["summary"]["errors"], 0)

    def test_malformed_hostname_cannot_count_as_unsubscribe(self):
        for host in (
            "shop.com\\evil", "%65xample.com", "shop.com%5c", "shop..com",
            "shop.com..", "-shop.com", "shop-.com", "shop_.com", "a" * 64 + ".com",
            "127.1", "2130706433", "0177.0.0.1", "0x7f000001",
        ):
            with self.subTest(host=host):
                codes = self.codes(f'<a href="https://{host}/">Unsubscribe</a>')
                self.assertIn("INVALID_URL", codes)
                self.assertIn("UNSUBSCRIBE_NOT_DETECTED", codes)

    def test_internationalized_and_canonical_hosts(self):
        for host in ("bücher.de", "shop.com.", "[2606:4700:4700::1111]"):
            with self.subTest(host=host):
                self.assertNotIn("INVALID_URL", self.codes(f'<a href="https://{host}/">Unsubscribe</a>'))
        self.assertIn("PLACEHOLDER_HOST", self.codes('<a href="https://ｅxample.com/">Unsubscribe</a>'))

    def test_control_characters_are_not_silently_stripped_by_urlsplit(self):
        for target in ("https://shop.com/\x00", "https://shop.com/\x01", "https://shop.com/\x7f", "https://shop.com/a\nb"):
            with self.subTest(target=target):
                self.assertIn("INVALID_URL", self.codes(f'<a href="{target}">Unsubscribe</a>'))

    def test_dynamic_values_do_not_hide_static_url_errors(self):
        for target in (
            "javascript:alert({{ first_name }})", "ftp://shop.com/{{ path }}",
            "https://shop..com/{{ path }}", "https://[bad/{{ path }}",
            "https://user:password@shop.com/{{ path }}", "https://shop.com/bad path/{{ id }}",
        ):
            with self.subTest(target=target):
                report = self.check(f'<a href="{target}">Read</a>{{% unsubscribe %}}')
                self.assertGreater(report["summary"]["errors"], 0)
        for target in ("https://shop.com/{{ path }}", "{{ event.checkout_url }}", "{{ host }}/products"):
            with self.subTest(target=target):
                report = self.check(f'<a href="{target}">Read</a>{{% unsubscribe %}}')
                self.assertEqual(report["summary"]["errors"], 0)
                self.assertIn("DYNAMIC_URL", [item["code"] for item in report["findings"]])

    def test_no_script_execution(self):
        self.assertIn("SCRIPT_ELEMENT", self.codes("<script>alert(1)</script>{% unsubscribe %}"))
        self.assertIn("UNSUBSCRIBE_NOT_DETECTED", self.codes("<script>{% unsubscribe %}</script>"))

    def test_scheme_handling(self):
        for target in ("javascript:alert(1)", "data:text/html,hello", "ftp://shop.com/file"):
            self.assertIn("UNSUPPORTED_URL", self.codes(f'<a href="{target}">Shop</a>'))
        self.assertIn("INSECURE_URL", self.codes('<a href="http://shop.com/">Shop</a>'))

    def test_contact_links_do_not_require_utm(self):
        codes = self.codes('<a href="mailto:demo@example.com">Contact</a><a href="tel:+15555550100">Call</a>{% unsubscribe %}')
        self.assertNotIn("MISSING_UTM", codes)
        self.assertIn("EMPTY_CONTACT_URL", self.codes('<a href="mailto:">Contact</a>'))

    def test_utm_blank_encoded_and_duplicate_values(self):
        base = '<a href="https://shop.com/?{}">Shop</a>{{% unsubscribe %}}'
        complete = "utm_source=demo&amp;utm_medium=email&amp;utm_campaign=welcome"
        self.assertNotIn("MISSING_UTM", self.codes(base.format(complete)))
        self.assertIn("MISSING_UTM", self.codes(base.format(complete.replace("welcome", "%20"))))
        self.assertIn("DUPLICATE_UTM", self.codes(base.format(complete + "&amp;utm_campaign=other")))
        self.assertIn("INCONSISTENT_CAMPAIGN", self.codes(base.format(complete + "&amp;utm_campaign=other")))

    def test_preference_link_is_exempt_from_utm(self):
        self.assertNotIn("MISSING_UTM", self.codes('<a href="https://shop.com/preferences">Manage preferences</a>{% unsubscribe %}'))

    def test_dynamic_destination_is_manual_review(self):
        codes = self.codes('<a href="{{ event.checkout_url }}">Return</a>{% unsubscribe %}')
        self.assertIn("DYNAMIC_URL", codes)
        self.assertNotIn("UNSUPPORTED_URL", codes)
        self.assertNotIn("MISSING_UTM", codes)

    def test_image_alt_and_source(self):
        self.assertIn("MISSING_ALT", self.codes('<img src="https://shop.com/a.png">'))
        self.assertNotIn("MISSING_ALT", self.codes('<img src="https://shop.com/a.png" alt="">'))
        self.assertIn("MISSING_ALT", self.codes('<img src="https://shop.com/a.png" alt>'))
        self.assertIn("PLACEHOLDER_URL", self.codes('<img alt="An item">'))
        self.assertNotIn("MISSING_UTM", self.codes('<img src="https://shop.com/a.png" alt="An item">'))

    def test_first_name_fallback_variations(self):
        for expression in ("first_name", "person.first_name", "first_name|default:''", "first_name|default:' '"):
            with self.subTest(expression=expression):
                self.assertIn("FIRST_NAME_FALLBACK", self.codes("{{ " + expression + " }}"))
        for expression in ("first_name|default:'there'", 'person.first_name | default: "friend"'):
            self.assertNotIn("FIRST_NAME_FALLBACK", self.codes("{{ " + expression + " }}"))
        self.assertIn("FIRST_NAME_FALLBACK", self.codes("{% unsubscribe %}", subject="Hi {{ first_name }}"))

    def test_audit_does_not_access_network(self):
        body = '<a href="https://shop.com/?utm_source=demo&amp;utm_medium=email&amp;utm_campaign=test">Shop</a>{% unsubscribe %}'
        with patch("socket.socket", side_effect=AssertionError("Network access attempted")), patch(
            "socket.getaddrinfo", side_effect=AssertionError("DNS lookup attempted")
        ):
            report = self.check(body)
        self.assertEqual(report["summary"], {"errors": 0, "warnings": 0})

    def test_error_reports_redact_credentials_and_dynamic_values(self):
        body = '<a href="https://private-user:PRIVATE_PASSWORD@shop.com/{{ PRIVATE_VARIABLE }}">Unsubscribe</a>'
        report = self.check(body)
        self.assertGreater(report["summary"]["errors"], 0)
        serialized = json.dumps(report)
        for secret in ("private-user", "PRIVATE_PASSWORD", "PRIVATE_VARIABLE", "shop.com"):
            self.assertNotIn(secret, serialized)

    def test_report_does_not_repeat_draft_or_urls(self):
        report = self.check('<p>PRIVATE SENTENCE</p><a href="https://shop.com/?token=PRIVATE_TOKEN">Read</a>', subject="PRIVATE SUBJECT")
        serialized = json.dumps(report)
        for secret in ("PRIVATE SENTENCE", "PRIVATE_TOKEN", "PRIVATE SUBJECT", "https://shop.com"):
            self.assertNotIn(secret, serialized)


class CLITests(unittest.TestCase):
    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = emailqa.main(list(args))
        return code, output.getvalue(), errors.getvalue()

    def test_checked_in_examples(self):
        root = Path(__file__).resolve().parents[1]
        code, output, _ = self.run_cli(str(root / "examples/welcome-before.json"), "--format", "json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["summary"], {"errors": 4, "warnings": 4})
        code, output, _ = self.run_cli(str(root / "examples/welcome-reviewed.json"), "--strict", "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["summary"], {"errors": 0, "warnings": 0})

    def test_warning_strict_exit_code(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "email.html").write_text("{% unsubscribe %}", encoding="utf-8")
            manifest = path / "email.json"
            manifest.write_text(json.dumps({"subject": "x" * 61, "preheader": "Preview", "html_file": "email.html"}), encoding="utf-8")
            self.assertEqual(self.run_cli(str(manifest))[0], 0)
            self.assertEqual(self.run_cli(str(manifest), "--strict")[0], 1)

    def test_bad_inputs_return_2_without_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            for content in ('PRIVATE invalid JSON', '[]', '{}', '{"subject": 1, "preheader": "x", "html_file": "x"}', '{"subject": "x", "preheader": "x", "html_file": ""}'):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    code, output, errors = self.run_cli(str(path))
                    self.assertEqual(code, 2)
                    self.assertEqual(output, "")
                    self.assertNotIn("PRIVATE", errors)
                    self.assertNotIn(folder, errors)

    def test_size_and_encoding_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            for content in (b"x" * (emailqa.MAX_BYTES + 1), b"\xff"):
                path.write_bytes(content)
                self.assertEqual(self.run_cli(str(path))[0], 2)

    def test_missing_file(self):
        self.assertEqual(self.run_cli("no-such-manifest.json")[0], 2)


if __name__ == "__main__":
    unittest.main()
