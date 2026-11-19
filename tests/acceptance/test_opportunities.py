"""Acceptance tests: the funding calls and opportunities exported for the Tally site.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for opportunities.json. Only public items that are still
open and have a public http(s) link are published. Members-only items are left out
entirely, and nothing about how an item arrived is ever published. Do not edit these
tests to make a build pass; raise the problem instead.
"""

import importlib.util
import json
import re
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CLUSTERS = ROOT / "clusters.json"
OPPORTUNITIES = ROOT / "opportunities.json"
EXPORTER = ROOT / "scripts" / "export_clusters_events.py"
SAMPLE = ROOT / "tests" / "fixtures" / "opportunities_sample"

KEYS = {"kind", "cluster", "deadline", "time", "title", "summary", "link"}
KINDS = {"funding", "opportunity"}
FORBIDDEN = {
    "source", "received", "id", "audience", "also", "post", "date_role", "where", "text", "date",
}
RECEIVED = re.compile(
    r"e-?mail|newsletter|mailing list|inbox|forward(ed|ing)?\b|\breceived\b|bulletin"
    r"|shared (with|for) (cluster )?members|sent to members",
    re.I,
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PERSONAL_LINKEDIN = re.compile(r"linkedin\.com/in/", re.I)
OPEN_ENDED = re.compile(
    r"\brolling\b|\bongoing\b|\balways open\b|\bopen all year\b|\bopen year-round\b"
    r"|\bno (closing date|deadline)\b",
    re.I,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from keys(v)


def exporter():
    spec = importlib.util.spec_from_file_location("export_clusters_events", EXPORTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sort_key(item):
    return (item["deadline"] is None, item["deadline"] or "", item["cluster"], item["title"])


class ExportedFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load(OPPORTUNITIES)
        cls.items = cls.doc["opportunities"]
        cls.clusters = {c["id"] for c in load(CLUSTERS)["clusters"]}

    def test_opportunities_are_well_formed(self):
        self.assertEqual(set(self.doc), {"as_of", "opportunities"})
        self.assertTrue(self.items, "expected at least one opportunity")
        for item in self.items:
            self.assertEqual(set(item), KEYS, item)
            self.assertIn(item["kind"], KINDS, item)
            self.assertIn(item["cluster"], self.clusters, item)
            self.assertTrue(isinstance(item["title"], str) and item["title"].strip(), item)
            self.assertRegex(item["link"], r"^https?://[^\s]+$")
            for k in ("time", "summary"):
                self.assertTrue(item[k] is None or (isinstance(item[k], str) and item[k].strip()), item)
        self.assertEqual(self.items, sorted(self.items, key=sort_key), "sorted by deadline")

    def test_only_open_opportunities(self):
        as_of = date.fromisoformat(self.doc["as_of"])
        self.assertGreaterEqual(as_of, date(2026, 11, 19))
        for item in self.items:
            if item["deadline"] is None:
                text = " ".join(t for t in (item["title"], item["summary"]) if t)
                self.assertRegex(text, OPEN_ENDED, "an undated item must say it is open-ended")
            else:
                self.assertRegex(item["deadline"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertGreaterEqual(date.fromisoformat(item["deadline"]), as_of, item)

    def test_no_forbidden_fields_or_receipt_mentions(self):
        self.assertFalse(FORBIDDEN & set(keys(self.items)))
        for text in strings(self.doc):
            self.assertIsNone(RECEIVED.search(text), text)
            self.assertIsNone(EMAIL.search(text), text)
            self.assertIsNone(PERSONAL_LINKEDIN.search(text), text)


class Exporter(unittest.TestCase):
    """The export rules, proved on a synthetic round-up with planted detail."""

    @classmethod
    def setUpClass(cls):
        cls.doc = exporter().build_opportunities(SAMPLE, "2026-11-19")
        cls.text = json.dumps(cls.doc)

    def test_export_never_copies_members_or_receipt_detail(self):
        for planted in (
            "PLANTED-MEMBERS-TITLE", "PLANTED-MEMBERS-TIME", "PLANTED-MEMBERS-SUMMARY",
            "PLANTED-MEMBERS-LINK", "PLANTED-MEMBERS-UNDATED", "PLANTED-ID-1", "PLANTED-SOURCE",
            "PLANTED-RECEIVED", "PLANTED-POST", "PLANTED-ALSO", "PLANTED-DATE-ROLE",
            "PLANTED-WHERE", "PLANTED-DIRECTORY-NOTE", "Members-only",
        ):
            self.assertNotIn(planted, self.text)
        self.assertEqual(set(self.doc), {"as_of", "opportunities"})
        for item in self.doc["opportunities"]:
            self.assertEqual(set(item), KEYS, item)
        self.assertFalse(FORBIDDEN & set(keys(self.doc["opportunities"])))

    def test_export_filters_opportunities(self):
        for planted in (
            "PLANTED-PAST", "PLANTED-UNDATED-UNCLEAR", "PLANTED-NO-LINK", "PLANTED-UNSAFE-LINK",
            "PLANTED-RECEIVED-MENTION", "PLANTED-UNKNOWN-CLUSTER", "PLANTED-EVENT",
            "PLANTED-SHARED-FOR-MEMBERS", "PLANTED-PERSONAL-EMAIL", "PLANTED-PERSONAL-PROFILE",
            "PLANTED-NO-AUDIENCE", "PLANTED-NEWS",
        ):
            self.assertNotIn(planted, self.text)
        self.assertEqual(self.doc["as_of"], "2026-11-19")
        self.assertEqual(self.doc["opportunities"], [
            {
                "kind": "opportunity",
                "cluster": "SCRDSC",
                "deadline": "2026-11-19",
                "time": None,
                "title": "Closes today",
                "summary": None,
                "link": "http://example.org/today",
            },
            {
                "kind": "funding",
                "cluster": "SCRDSC",
                "deadline": "2026-12-20",
                "time": "12:00",
                "title": "Open grant for SMEs",
                "summary": "A public grant for small firms.",
                "link": "https://example.org/grant",
            },
            {
                "kind": "funding",
                "cluster": "ScotlandDSC",
                "deadline": None,
                "time": None,
                "title": "Rolling innovation fund",
                "summary": "A rolling fund with no closing date.",
                "link": "https://example.org/rolling",
            },
        ])


if __name__ == "__main__":
    unittest.main()
