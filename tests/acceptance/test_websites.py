"""Acceptance tests: websites.json, Tally company websites that are dead or have moved.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for websites.json (see docs/websites-data.md) and for the rules in
scripts/check_websites.py. They need no network. Do not edit these tests to make a build pass;
raise the problem instead.
"""

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "websites.json"
TALLY = ROOT / "tally-data.json"
CHECKER = ROOT / "scripts" / "check_websites.py"

TOP_KEYS = {"generated", "checked", "dead", "moved", "pending"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REASONS = {"no-such-host", "refused", "not-found"}


def load():
    spec = importlib.util.spec_from_file_location("check_websites", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Classify(unittest.TestCase):
    """Criteria 1 and 2."""

    def setUp(self):
        self.c = load()

    def test_ok(self):
        self.assertEqual(self.c.classify({"status": 200}), ("ok", None))
        self.assertEqual(self.c.classify({"status": 301}), ("ok", None))

    def test_gone(self):
        self.assertEqual(self.c.classify({"status": 404}), ("gone", "not-found"))
        self.assertEqual(self.c.classify({"status": 410}), ("gone", "not-found"))
        self.assertEqual(self.c.classify({"error": "dns"}), ("gone", "no-such-host"))
        self.assertEqual(self.c.classify({"error": "refused"}), ("gone", "refused"))

    def test_uncertain(self):
        for o in ({"status": 403}, {"status": 429}, {"status": 500}, {"status": 503}, {"status": 520},
                  {"error": "timeout"}, {"error": "tls"}, {"error": "other"}, {"status": 401}):
            self.assertEqual(self.c.classify(o)[0], "uncertain", o)

    def test_home(self):
        self.assertEqual(self.c.home_of("https://www.wincanton.co.uk/sectors/defence/"), "https://www.wincanton.co.uk/")
        self.assertTrue(self.c.is_home("https://www.example.com"))
        self.assertTrue(self.c.is_home("https://www.example.com/"))
        self.assertTrue(self.c.is_home("https://www.example.com/index.html"))
        self.assertFalse(self.c.is_home("https://www.example.com/en/uk"))

    def test_settle(self):
        s = self.c.settle
        self.assertEqual(s("https://a.com/x", ("gone", "not-found"), ("ok", None)), ("moved", "https://a.com/"))
        self.assertEqual(s("https://a.com/x", ("gone", "not-found"), ("gone", "not-found")), ("dead", "not-found"))
        self.assertEqual(s("https://a.com/x", ("gone", "not-found"), ("uncertain", None)), ("uncertain", None))
        self.assertEqual(s("https://a.com/", ("gone", "no-such-host"), None), ("dead", "no-such-host"))
        self.assertEqual(s("https://a.com/", ("ok", None), None), ("ok", None))


class Confirm(unittest.TestCase):
    """Criterion 3: published only when the same URL fails the same way in two runs in a row."""

    def setUp(self):
        self.c = load()
        self.dead = {"name": "Acme", "url": "https://acme.example/", "result": "dead", "reason": "no-such-host"}
        self.moved = {"name": "Beta", "url": "https://beta.example/x", "result": "moved", "home": "https://beta.example/"}

    def test_first_failure_is_pending(self):
        dead, moved, pending = self.c.confirm(None, [self.dead, self.moved], "2026-11-23")
        self.assertEqual((dead, moved), ([], []))
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending[0]["since"], "2026-11-23")

    def test_second_failure_is_published(self):
        _, _, pending = self.c.confirm(None, [self.dead, self.moved], "2026-11-23")
        previous = {"dead": [], "moved": [], "pending": pending}
        dead, moved, pending2 = self.c.confirm(previous, [self.dead, self.moved], "2026-11-30")
        self.assertEqual(dead, [{"name": "Acme", "url": "https://acme.example/", "reason": "no-such-host", "since": "2026-11-23"}])
        self.assertEqual(moved, [{"name": "Beta", "url": "https://beta.example/x", "home": "https://beta.example/", "since": "2026-11-23"}])
        self.assertEqual(pending2, [])
        # Still failing a week later: stays published with its first date.
        dead3, _, _ = self.c.confirm({"dead": dead, "moved": moved, "pending": []}, [self.dead], "2026-12-07")
        self.assertEqual(dead3[0]["since"], "2026-11-23")

    def test_changed_url_starts_again(self):
        previous = {"dead": [{"name": "Acme", "url": "https://old.example/", "reason": "no-such-host", "since": "2026-11-23"}], "moved": [], "pending": []}
        dead, _, pending = self.c.confirm(previous, [self.dead], "2026-11-30")
        self.assertEqual(dead, [])
        self.assertEqual(len(pending), 1)

    def test_recovery_clears(self):
        previous = {"dead": [{"name": "Acme", "url": "https://acme.example/", "reason": "no-such-host", "since": "2026-11-23"}], "moved": [], "pending": []}
        self.assertEqual(self.c.confirm(previous, [], "2026-11-30"), ([], [], []))


class Guards(unittest.TestCase):
    """Criterion 4."""

    def test_gone_share(self):
        c = load()
        c.check_gone_share(100, 2000)
        with self.assertRaises(SystemExit):
            c.check_gone_share(201, 2000)


class Contract(unittest.TestCase):
    """Criterion 5."""

    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(DATA.read_text(encoding="utf-8"))
        cls.tally = {c["name"]: c.get("website", "") for c in json.loads(TALLY.read_text(encoding="utf-8"))["companies"]}

    def test_shape(self):
        self.assertEqual(set(self.doc), TOP_KEYS)
        self.assertRegex(self.doc["generated"], DATE)
        self.assertEqual(set(self.doc["checked"]), {"websites", "ok", "gone", "uncertain"})

    def test_rows(self):
        for row in self.doc["dead"] + self.doc["pending"]:
            self.assertIn(row["name"], self.tally)
            self.assertRegex(row["since"], DATE)
        for row in self.doc["dead"]:
            self.assertEqual(set(row), {"name", "url", "reason", "since"})
            self.assertIn(row["reason"], REASONS)
        for row in self.doc["moved"]:
            self.assertEqual(set(row), {"name", "url", "home", "since"})
            self.assertIn(row["name"], self.tally)
            self.assertTrue(row["home"].startswith("http") and row["home"].endswith("/"))


if __name__ == "__main__":
    unittest.main()
