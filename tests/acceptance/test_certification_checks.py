"""Acceptance tests: certification checks on company pages.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

A company page may record a manual check of one of its certifications against a
public register (`certification-checks` in its frontmatter). The gate holds the
field to its rules and tally-data.json carries it. These tests are the contract
for the field. Do not edit them to make a build pass; raise the problem instead.
"""

import datetime
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

_spec = importlib.util.spec_from_file_location("gate", ROOT / ".github" / "scripts" / "check.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

KNOWN = {"accr-ce", "accr-ce-plus", "accr-iso9001", "accr-crest"}
TODAY = datetime.date.today()
PAST = (TODAY - datetime.timedelta(days=30)).isoformat()
FUTURE = (TODAY + datetime.timedelta(days=30)).isoformat()


def page(checks):
    """A minimal company page carrying accr-ce-plus and accr-iso9001, with the given checks block."""
    return (
        "---\n"
        "type: organisation\n"
        "name: Example Checked Ltd\n"
        "tags:\n"
        "  - defence\n"
        "  - accr-ce-plus\n"
        "  - accr-iso9001\n"
        f"{checks}"
        "---\n\n# Example Checked\n"
    )


def check(**fields):
    lines = []
    for i, (key, value) in enumerate(fields.items()):
        lines.append(f"{'  - ' if i == 0 else '    '}{key}: {value}\n")
    return "".join(lines)


GOOD = check(accreditation="accr-ce-plus", register="the IASME register", checked=PAST, link="https://example.org/cert/1")


class GateCheck(unittest.TestCase):
    def test_gate_accepts_well_formed_checks(self):
        """A page with no checks, a check with a link and a check without one all pass."""
        self.assertEqual(gate.certification_check_problems(page(""), KNOWN), [])
        self.assertEqual(gate.certification_check_problems(page("certification-checks:\n" + GOOD), KNOWN), [])
        two = GOOD + check(accreditation="accr-iso9001", register="UKAS CertCheck", checked=PAST)
        self.assertEqual(gate.certification_check_problems(page("certification-checks:\n" + two), KNOWN), [])

    def test_gate_rejects_malformed_checks(self):
        """Each broken rule is a problem."""
        bad = {
            "unheld accreditation": check(accreditation="accr-crest", register="the CREST directory", checked=PAST),
            "unknown accreditation": check(accreditation="accr-made-up", register="a register", checked=PAST),
            "not an accreditation": check(accreditation="defence", register="a register", checked=PAST),
            "missing register": check(accreditation="accr-ce-plus", checked=PAST),
            "empty register": check(accreditation="accr-ce-plus", register="", checked=PAST),
            "long register": check(accreditation="accr-ce-plus", register="r" * 81, checked=PAST),
            "register with a link": check(accreditation="accr-ce-plus", register="see https://example.org", checked=PAST),
            "missing date": check(accreditation="accr-ce-plus", register="the IASME register"),
            "malformed date": check(accreditation="accr-ce-plus", register="the IASME register", checked="2026-13-45"),
            "loose date": check(accreditation="accr-ce-plus", register="the IASME register", checked="1 December 2026"),
            "future date": check(accreditation="accr-ce-plus", register="the IASME register", checked=FUTURE),
            "http link": check(accreditation="accr-ce-plus", register="the IASME register", checked=PAST, link="http://example.org/c"),
            "script link": check(accreditation="accr-ce-plus", register="the IASME register", checked=PAST, link="javascript:alert(1)"),
            "unknown key": check(accreditation="accr-ce-plus", register="the IASME register", checked=PAST, result="not found"),
            "repeated accreditation": GOOD + GOOD,
            "not a list": "  accreditation: accr-ce-plus\n",
        }
        for name, block in bad.items():
            with self.subTest(name):
                problems = gate.certification_check_problems(page("certification-checks:\n" + block), KNOWN)
                self.assertTrue(problems, f"{name}: no problem reported")
                self.assertTrue(all(isinstance(p, str) and p for p in problems))

    def test_template_documents_certification_checks(self):
        template = (ROOT / "Company Page Template.md").read_text(encoding="utf-8")
        for text in ("certification-checks:", "accreditation:", "register:", "checked:", "link:"):
            self.assertIn(text, template)

    def test_every_page_passes_the_gate_check(self):
        taxonomy = json.loads((ROOT / "taxonomy.json").read_text(encoding="utf-8"))
        known = {v["slug"] for v in taxonomy["facets"]["accreditations"]["values"]}
        bad = []
        for path in sorted((ROOT / "Companies").rglob("*.md")):
            problems = gate.certification_check_problems(path.read_text(encoding="utf-8"), known)
            if problems:
                bad.append((path.name, problems))
        self.assertEqual(bad, [], f"{len(bad)} pages with bad checks, e.g. {bad[:3]}")


class ViewerData(unittest.TestCase):
    def test_viewer_data_carries_checks(self):
        data = json.loads((ROOT / "tally-data.json").read_text(encoding="utf-8"))
        by_name = {c["name"]: c for c in data["companies"]}
        bad = []
        for path in sorted((ROOT / "Companies").rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            meta = gate.frontmatter_name(text) or path.stem
            record = by_name.get(meta)
            if record is None:
                continue
            want = gate.certification_checks(text)
            got = record.get("certification_checks")
            if want:
                expected = [
                    {"accreditation": c["accreditation"], "register": c["register"], "checked": c["checked"], "link": c.get("link") or None}
                    for c in want
                ]
                if got != expected:
                    bad.append((path.name, "differs"))
            elif got not in (None, []):
                bad.append((path.name, "record has checks the page does not"))
        self.assertEqual(bad, [], f"{len(bad)} records differ, e.g. {bad[:5]}")


if __name__ == "__main__":
    unittest.main()
