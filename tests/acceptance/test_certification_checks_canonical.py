"""Acceptance tests: certification checks are held to one canonical form.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

The gate reads `certification-checks` line by line, without a YAML parser. A
YAML reader could see a check the gate never read if the block were written in
any other form, so the gate accepts only the form in the company page template
and rejects every other way of writing it. The register may not carry negative
or status wording. Regression tests from the independent review of card 7418.
Do not edit them to make a build pass; raise the problem instead.
"""

import datetime
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

_spec = importlib.util.spec_from_file_location("gate", ROOT / ".github" / "scripts" / "check.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

KNOWN = {"accr-ce", "accr-ce-plus", "accr-iso9001", "accr-crest"}
HEAD = "---\ntype: organisation\nname: Example Checked Ltd\ntags:\n  - defence\n  - accr-ce-plus\n  - accr-iso9001\n"
GOOD = "  - accreditation: accr-ce-plus\n    register: the IASME register\n    checked: 2020-01-01\n"


def problems(block, tail=""):
    return gate.certification_check_problems(HEAD + block + tail + "---\n\n# Example\n", KNOWN)


class CanonicalForm(unittest.TestCase):
    def assertRejected(self, block, tail=""):
        found = problems(block, tail)
        self.assertTrue(found, "no problem reported")
        self.assertTrue(all(isinstance(p, str) and p for p in found))

    def test_canonical_form_passes(self):
        self.assertEqual(problems("certification-checks:\n" + GOOD), [])
        self.assertEqual(problems("certification-checks:\n" + GOOD, "size: small\n"), [])
        quoted = "  - accreditation: accr-ce-plus\n    register: 'the company''s register'\n    checked: '2020-01-01'\n"
        self.assertEqual(problems("certification-checks:\n" + quoted), [])

    def test_rejects_a_comment_inside_the_block(self):
        self.assertRejected("certification-checks:\n" + GOOD + "# note\n    link: javascript:alert(1)\n")
        self.assertRejected("certification-checks:\n" + GOOD + "    # note\n")
        self.assertRejected("certification-checks:\n  - accreditation: accr-ce-plus\n    register: the IASME register\n    checked: 2020-01-01 # x\n")
        self.assertRejected("certification-checks:\n" + GOOD + "    link: https://example.org #javascript\n")

    def test_rejects_any_other_spelling_of_the_key(self):
        self.assertRejected('"certification-checks":\n' + GOOD)
        self.assertRejected("'certification-checks':\n" + GOOD)
        self.assertRejected("certification-checks :\n" + GOOD)
        self.assertRejected("certification-checks: &c\n" + GOOD)
        self.assertRejected("certification-checks: []\n")
        self.assertRejected("Certification-Checks:\n" + GOOD)
        self.assertRejected("? certification-checks\n:\n" + GOOD)

    def test_rejects_the_key_written_twice(self):
        again = "certification-checks:\n  - accreditation: accr-crest\n    register: the CREST directory\n    checked: 2999-01-01\n"
        self.assertRejected("certification-checks:\n" + GOOD + again)
        self.assertRejected("certification-checks:\n" + GOOD, "size: small\n" + again)

    def test_rejects_block_scalars(self):
        for marker in (">-", "|", ">", "|-", "|+", ">2"):
            with self.subTest(marker):
                self.assertRejected(
                    f"certification-checks:\n  - accreditation: accr-ce-plus\n    register: {marker}\n      the IASME register\n    checked: 2020-01-01\n"
                )

    def test_rejects_flow_style(self):
        self.assertRejected("certification-checks:\n  - {accreditation: accr-crest, register: x, checked: 2999-01-01}\n")
        self.assertRejected("certification-checks:\n  - accreditation: [accr-ce-plus]\n    register: the IASME register\n    checked: 2020-01-01\n")
        self.assertRejected("certification-checks:\n  - accreditation: accr-ce-plus\n    register: {the IASME register}\n    checked: 2020-01-01\n")

    def test_rejects_backslashes_and_escapes(self):
        self.assertRejected('certification-checks:\n  - accreditation: accr-ce-plus\n    register: "the IASME\\nregister"\n    checked: 2020-01-01\n')
        self.assertRejected(
            'certification-checks:\n  - accreditation: accr-ce-plus\n    register: the IASME register\n    checked: 2020-01-01\n'
            '    link: "https://x.org/\\u0022\\u003e\\u003cscript\\u003e"\n'
        )
        self.assertRejected("certification-checks:\n  - accreditation: accr-ce-plus\n    register: the IASME\\register\n    checked: 2020-01-01\n")

    def test_rejects_anchors_aliases_and_tags(self):
        for value in ("&a the IASME register", "*a", "!!str the IASME register"):
            with self.subTest(value):
                self.assertRejected(f"certification-checks:\n  - accreditation: accr-ce-plus\n    register: {value}\n    checked: 2020-01-01\n")

    def test_rejects_other_indentation(self):
        self.assertRejected("certification-checks:\n- accreditation: accr-ce-plus\n  register: the IASME register\n  checked: 2020-01-01\n")
        self.assertRejected("certification-checks:\n    - accreditation: accr-ce-plus\n      register: the IASME register\n      checked: 2020-01-01\n")
        self.assertRejected("certification-checks:\n  - accreditation: accr-ce-plus\n    register:the IASME register\n    checked: 2020-01-01\n")

    def test_rejects_broken_quoting(self):
        self.assertRejected("certification-checks:\n  - accreditation: accr-ce-plus\n    register: 'the company's register'\n    checked: 2020-01-01\n")
        self.assertRejected('certification-checks:\n  - accreditation: accr-ce-plus\n    register: "the "IASME" register"\n    checked: 2020-01-01\n')
        self.assertRejected('certification-checks:\n  - accreditation: accr-ce-plus\n    register: "the IASME register\n    checked: 2020-01-01\n')


class RegisterWording(unittest.TestCase):
    def test_register_rejects_negative_or_status_wording(self):
        words = [
            "not", "no", "none", "unverified", "expired", "revoked", "lapsed", "withdrawn",
            "suspended", "failed", "invalid", "removed", "found",
        ]
        for word in words:
            for register in (f"the IASME register {word}", f"{word.upper()} on the IASME register", f"the {word.capitalize()} register"):
                with self.subTest(register):
                    block = f"certification-checks:\n  - accreditation: accr-ce-plus\n    register: {register}\n    checked: 2020-01-01\n"
                    self.assertTrue(problems(block), f"{register!r} passed")
        block = "certification-checks:\n  - accreditation: accr-ce-plus\n    register: the IASME register (isn't listed)\n    checked: 2020-01-01\n"
        self.assertTrue(problems(block))

    def test_register_allows_plain_register_names(self):
        for register in ("the IASME register", "UKAS CertCheck", "the CREST directory", "the Northern register", "the Nottingham register"):
            with self.subTest(register):
                block = f"certification-checks:\n  - accreditation: accr-ce-plus\n    register: {register}\n    checked: 2020-01-01\n"
                self.assertEqual(problems(block), [])


class AlignedWithTheSite(unittest.TestCase):
    def test_future_dates_use_the_utc_date(self):
        tomorrow = (datetime.datetime.now(datetime.timezone.utc).date() + datetime.timedelta(days=1)).isoformat()
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        block = "certification-checks:\n  - accreditation: accr-ce-plus\n    register: the IASME register\n    checked: {}\n"
        self.assertTrue(problems(block.format(tomorrow)))
        self.assertEqual(problems(block.format(today)), [])

    def test_https_check_ignores_case(self):
        block = "certification-checks:\n  - accreditation: accr-ce-plus\n    register: the IASME register\n    checked: 2020-01-01\n    link: {}\n"
        self.assertEqual(problems(block.format("HTTPS://example.org/cert/1")), [])
        self.assertTrue(problems(block.format("HTTP://example.org/cert/1")))

    def test_single_quoted_values_unescape_doubled_quotes(self):
        text = HEAD + "certification-checks:\n  - accreditation: accr-ce-plus\n    register: 'the company''s register'\n    checked: 2020-01-01\n---\n"
        self.assertEqual(gate.certification_checks(text)[0]["register"], "the company's register")


if __name__ == "__main__":
    unittest.main()
