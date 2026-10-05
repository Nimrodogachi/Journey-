#!/usr/bin/env python3
"""Offline static checks for marketing-email drafts. Python standard library only."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from html import unescape
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlsplit

VERSION = "1.0.0"
MAX_BYTES = 2_000_000
UNSUBSCRIBE_ELEMENT = re.compile(r"{%\s*unsubscribe(?:\s+(?:'[^']*'|\"[^\"]*\"))?\s*%}", re.I)
UNSUBSCRIBE_URL = re.compile(r"{%\s*unsubscribe_link\s*%}", re.I)
VARIABLE = re.compile(r"{{\s*(.*?)\s*}}", re.S)
TEMPLATE = re.compile(r"{{.*?}}|{%.*?%}", re.S)
FIRST_NAME = re.compile(r"^(?:person\.)?first_name\s*(?:\||$)")
FALLBACK = re.compile(r"\|\s*default(?:_if_none)?\s*:\s*(['\"])(.*?)\1")
MANUAL_CHECKS = [
    "Verify consent, audience exclusions, flow triggers, filters, delays, and purchase suppression in the sending platform.",
    "Preview real profile/event variants and missing values; test conditional blocks and dynamic URLs.",
    "Open every destination, verify offers and dates, and review mobile/desktop rendering in actual inboxes.",
    "Confirm sender/reply-to, required footer details, and working opt-out behavior in an authorized live test.",
    "Record reviewer approval before any real audience send. This report does not approve a send.",
]


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    location: str
    message: str


class EmailParser(HTMLParser):
    """Extract authored HTML; comments and script/style content are not evidence."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.links = []
        self.images = []
        self.parts = []
        self.text_parts = []
        self.active_link = None
        self.ignored = []
        self.continue_text = False
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        self.continue_text = False
        if tag in {"head", "script", "style", "template", "textarea", "title"}:
            self.ignored.append(tag)
            self.scripts += tag == "script"
            return
        if self.ignored:
            return
        data = dict(attrs)
        line = self.getpos()[0]
        if tag == "a":
            self.links.append({"href": data.get("href") or "", "line": line, "text": ""})
            self.active_link = len(self.links) - 1
        elif tag == "img":
            self.images.append({"attrs": data, "line": line})
            if self.active_link is not None:
                self.links[self.active_link]["text"] += data.get("alt") or ""
        self.parts.extend(value for _, value in attrs if value is not None)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        self.continue_text = False
        if self.ignored and tag == self.ignored[-1]:
            self.ignored.pop()
        if tag == "a":
            self.active_link = None

    def append_text(self, raw, decoded):
        if not self.ignored:
            if self.continue_text:
                self.parts[-1] += decoded
                self.text_parts[-1] += raw
            else:
                self.parts.append(decoded)
                self.text_parts.append(raw)
            self.continue_text = True
            if self.active_link is not None:
                self.links[self.active_link]["text"] += decoded

    def handle_data(self, data):
        self.append_text(data, data)

    def handle_entityref(self, name):
        raw = "&" + name + ";"
        self.append_text(raw, unescape(raw))

    def handle_charref(self, name):
        raw = "&#" + name + ";"
        self.append_text(raw, unescape(raw))

    def handle_comment(self, data):
        self.continue_text = False


def normalize_host(host):
    """Reject malformed host syntax without DNS lookups or URL fetches."""
    if "%" in host:
        raise ValueError("Encoded hostnames and scoped IP addresses are unsupported.")
    host = host.removesuffix(".")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    # Browsers may reinterpret abbreviated, octal, or hexadecimal IPv4 forms.
    if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*", host, re.I):
        raise ValueError("Use a canonical IP address.")
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise ValueError("Invalid internationalized hostname.") from error
    if len(host) > 253 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in host.split(".")
    ):
        raise ValueError("Invalid hostname labels.")
    return host


def placeholder_host(host):
    host = host.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".test", ".invalid", ".example", ".local")):
        return True
    if any(host == domain or host.endswith("." + domain) for domain in ("example.com", "example.net", "example.org")):
        return True
    if "staging" in host.split("."):
        return True
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False


def audit(subject, preheader, html):
    """Return deterministic findings without rendering, executing, or fetching HTML."""
    findings = []

    def add(severity, code, location, message):
        findings.append(Finding(severity, code, location, message))

    for field, value in (("subject", subject), ("preheader", preheader)):
        if not value.strip():
            add("error", "MISSING_" + field.upper(), field, "Provide non-empty " + field + " text.")
    if len(subject) > 60:
        add("warning", "LONG_SUBJECT", "subject", "Subject exceeds the project's 60-character review threshold; preview truncation on target devices.")
    if not html.strip():
        add("error", "EMPTY_HTML", "html", "Provide an email HTML draft.")

    parser = EmailParser()
    parser.feed(html)
    parser.close()
    authored = "\n".join(parser.parts)
    if parser.scripts:
        add("error", "SCRIPT_ELEMENT", "html", "Remove script elements; this tool never executes them.")

    # Only the link-generating directive in body text counts on its own.
    # Attributes and the URL-only directive are not evidence of a usable link.
    unsubscribe_found = any(UNSUBSCRIBE_ELEMENT.search(text) for text in parser.text_parts)
    campaigns = set()

    def check_url(value, location, is_image=False, utility=False):
        value = value.strip()
        if not value or value.startswith("#"):
            add("error", "PLACEHOLDER_URL", location, "Replace the empty or fragment-only destination.")
            return False
        if UNSUBSCRIBE_URL.fullmatch(value) and not is_image:
            return True
        dynamic = bool(TEMPLATE.search(value))
        if dynamic:
            add("warning", "DYNAMIC_URL", location, "Dynamic destination requires a platform preview and an authorized live test.")
        # Validate the static URL structure even when it contains a template.
        # Mask expressions so their internal whitespace is not treated as a URL error.
        candidate = TEMPLATE.sub("dynamic-value", value) if dynamic else value
        if re.search(r"[\s\x00-\x1f\x7f\\]", candidate):
            add("error", "INVALID_URL", location, "Remove whitespace, control characters, or backslashes from the URL.")
            return False
        try:
            parts = urlsplit(candidate)
            host = parts.hostname
            _ = parts.port
        except ValueError:
            add("error", "INVALID_URL", location, "Repair the malformed URL.")
            return False
        scheme = parts.scheme.lower()
        # A wholly dynamic destination may produce a complete URL at render time.
        if dynamic and not scheme and TEMPLATE.match(value):
            return False
        if scheme in {"mailto", "tel"} and not is_image:
            if not parts.path.strip():
                add("error", "EMPTY_CONTACT_URL", location, "Provide a contact destination.")
            return False
        if scheme not in {"https", "http"} or not host:
            add("error", "UNSUPPORTED_URL", location, "Use an absolute HTTP(S) destination; scripts, relative paths, and unsupported schemes are not accepted.")
            return False
        if parts.username is not None or parts.password is not None:
            add("error", "INVALID_URL", location, "Remove embedded credentials from the URL.")
            return False
        try:
            host = normalize_host(host)
        except ValueError:
            add("error", "INVALID_URL", location, "Repair the malformed hostname or use a canonical IP address.")
            return False
        placeholder = placeholder_host(host)
        if placeholder:
            add("error", "PLACEHOLDER_HOST", location, "Replace the example, staging, local, or non-public destination before a real send.")
        if scheme == "http":
            add("warning", "INSECURE_URL", location, "Use HTTPS when supported and verify the final destination manually.")
        if dynamic:
            return False
        if not is_image and not utility:
            query = parse_qs(parts.query, keep_blank_values=True)
            missing = [key for key in ("utm_source", "utm_medium", "utm_campaign") if not query.get(key) or not all(value.strip() for value in query[key])]
            if missing:
                add("warning", "MISSING_UTM", location, "Review tracking parameters: " + ", ".join(missing) + ". Platform-added tracking is not visible here.")
            if any(len(query.get(key, [])) > 1 for key in ("utm_source", "utm_medium", "utm_campaign")):
                add("warning", "DUPLICATE_UTM", location, "Use a single value per tracking parameter.")
            campaigns.update(value for value in query.get("utm_campaign", []) if value.strip())
        return not placeholder and scheme == "https"

    for index, link in enumerate(parser.links, start=1):
        utility = bool(re.search(r"\bunsubscribe\b|\bmanage preferences\b", link["text"], re.I))
        valid = check_url(link["href"], f"link {index}, line {link['line']}", utility=utility)
        if valid and link["text"].strip() and (UNSUBSCRIBE_URL.fullmatch(link["href"].strip()) or re.search(r"\bunsubscribe\b", link["text"], re.I)):
            unsubscribe_found = True
    if not unsubscribe_found:
        add("error", "UNSUBSCRIBE_NOT_DETECTED", "html", "No recognized unsubscribe hook was detected. Add one or manually review an unsupported implementation; this heuristic is not compliance validation.")
    if len(campaigns) > 1:
        add("warning", "INCONSISTENT_CAMPAIGN", "links", "Multiple non-empty utm_campaign values found; confirm this is intentional.")
    for index, image in enumerate(parser.images, start=1):
        location = f"image {index}, line {image['line']}"
        if "alt" not in image["attrs"] or image["attrs"]["alt"] is None:
            add("warning", "MISSING_ALT", location, "Add meaningful alt text, or alt=\"\" for a deliberately decorative image.")
        check_url(image["attrs"].get("src") or "", location, is_image=True)
    for location, content in (("subject", subject), ("preheader", preheader), ("html", authored)):
        for expression in VARIABLE.findall(content):
            if FIRST_NAME.match(expression):
                fallback = FALLBACK.search(expression)
                if not fallback or not fallback.group(2).strip():
                    add("warning", "FIRST_NAME_FALLBACK", location, "A first-name variable has no recognized non-empty quoted default. Confirm missing-name behavior in the platform.")

    errors = sum(item.severity == "error" for item in findings)
    warnings = sum(item.severity == "warning" for item in findings)
    return {
        "schema_version": 1,
        "tool_version": VERSION,
        "status": "BLOCKERS_FOUND" if errors else "STATIC_CHECKS_COMPLETE",
        "summary": {"errors": errors, "warnings": warnings},
        "findings": [asdict(item) for item in findings],
        "manual_checks": MANUAL_CHECKS,
    }


def read_text(path):
    with path.open("rb") as source:
        data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Input exceeds the 2 MB limit.")
    return data.decode("utf-8")


def load_manifest(path):
    data = json.loads(read_text(path))
    required = {"subject", "preheader", "html_file"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Manifest must contain exactly subject, preheader, and html_file.")
    if any(not isinstance(data[key], str) for key in required):
        raise ValueError("All manifest fields must be strings.")
    if not data["html_file"].strip():
        raise ValueError("html_file cannot be empty.")
    html_path = path.parent / data["html_file"]
    return data["subject"], data["preheader"], read_text(html_path)


def main(argv=None):
    cli = argparse.ArgumentParser(description="Offline email preflight. No network calls. Never send approval.")
    cli.add_argument("manifest", type=Path, help="UTF-8 JSON with subject, preheader, html_file (relative to manifest)")
    cli.add_argument("--format", choices=("text", "json"), default="text")
    cli.add_argument("--strict", action="store_true", help="Exit 1 for warnings as well as errors")
    cli.add_argument("--version", action="version", version=VERSION)
    args = cli.parse_args(argv)
    try:
        report = audit(*load_manifest(args.manifest))
    except (OSError, ValueError, UnicodeError, RecursionError):
        # Do not echo potentially sensitive input, paths, URLs, or JSON bodies.
        print("Input error: use readable UTF-8 files up to 2 MB and the documented JSON schema.", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        counts = report["summary"]
        print(f"{report['status']}: {counts['errors']} error(s), {counts['warnings']} warning(s)")
        for item in report["findings"]:
            print(f"[{item['severity'].upper()}] {item['code']} ({item['location']}): {item['message']}")
        print("\nManual review still required:")
        for check in report["manual_checks"]:
            print("- " + check)
    return int(bool(report["summary"]["errors"] or (args.strict and report["summary"]["warnings"])))


if __name__ == "__main__":
    raise SystemExit(main())
