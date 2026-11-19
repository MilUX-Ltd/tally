"""Acceptance tests: the clusters and events exported for the Tally site.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for clusters.json and events.json. Members-only cluster
events are signposts and nothing more: cluster, date, a fixed line of text and the
cluster's own website. Do not edit these tests to make a build pass; raise the problem
instead.
"""

import importlib.util
import json
import re
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CLUSTERS = ROOT / "clusters.json"
EVENTS = ROOT / "events.json"
EXPORTER = ROOT / "scripts" / "export_clusters_events.py"
SAMPLE = ROOT / "tests" / "fixtures" / "round_up_sample"

SIGNPOST = "Members' event: join the cluster for details"
PUBLIC_KEYS = {"audience", "cluster", "date", "time", "where", "title", "summary", "link"}
MEMBERS_KEYS = {"audience", "cluster", "date", "text", "link"}
CLUSTER_KEYS = {
    "id", "name", "full", "region", "regions", "status", "web", "linkedin", "colour", "membership",
}
FORBIDDEN = {"source", "received", "id", "also", "post", "date_role", "kind", "since", "logo", "map"}
STATUSES = {"live", "pre-launch", "proposed"}
# ONS codes: county (E10), unitary (E06), metropolitan district (E08), London borough
# (E09), English region (E12), country (E92, W92, S92, N92), Welsh, Scottish and
# Northern Irish unitary or council areas (W06, S12, N09).
ONS_CODE = re.compile(r"^(E06|E08|E09|E10|E12|E92|W92|S92|N92|W06|S12|N09)\d{6}$")
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
RECEIVED = re.compile(
    r"e-?mail|newsletter|mailing list|inbox|forward(ed|ing)?\b|\breceived\b|bulletin"
    r"|shared (with|for) (cluster )?members|sent to members",
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


class ExportedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clusters = load(CLUSTERS)
        cls.events = load(EVENTS)
        cls.by_id = {c["id"]: c for c in cls.clusters["clusters"]}
        cls.taxonomy = load(ROOT / "taxonomy.json")

    def test_members_events_are_signposts_only(self):
        members = [e for e in self.events["events"] if e.get("audience") == "members"]
        self.assertTrue(members, "expected at least one members-only signpost")
        for event in self.events["events"]:
            self.assertIn(event.get("audience"), {"public", "members"}, event)
        for event in members:
            self.assertEqual(set(event), MEMBERS_KEYS, event)
            self.assertEqual(event["text"], SIGNPOST)
            web = self.by_id[event["cluster"]]["web"]
            self.assertTrue(web and web.startswith("https://"), event)
            self.assertEqual(event["link"], web, "a members-only event links only to its cluster's website")

    def test_no_past_events(self):
        as_of = date.fromisoformat(self.events["as_of"])
        self.assertGreaterEqual(as_of, date(2026, 11, 19))
        dates = [e["date"] for e in self.events["events"]]
        self.assertEqual(dates, sorted(dates), "events are sorted by date")
        for event in self.events["events"]:
            self.assertRegex(event["date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertGreaterEqual(date.fromisoformat(event["date"]), as_of, event)

    def test_no_forbidden_fields(self):
        self.assertEqual(set(self.events), {"as_of", "events"})
        for event in self.events["events"]:
            allowed = PUBLIC_KEYS if event["audience"] == "public" else MEMBERS_KEYS
            self.assertEqual(set(event), allowed, event)
            self.assertFalse(FORBIDDEN & set(event), event)
            if event["audience"] == "public":
                self.assertTrue(event["title"], event)
                link = event["link"]
                self.assertTrue(link is None or link.startswith(("https://", "http://")), event)
        self.assertEqual(set(self.clusters), {"as_of", "source", "clusters"})
        for cluster in self.clusters["clusters"]:
            self.assertEqual(set(cluster), CLUSTER_KEYS, cluster["id"])
        self.assertFalse(FORBIDDEN & set(keys(self.events["events"])))
        self.assertFalse((FORBIDDEN - {"id"}) & set(keys(self.clusters["clusters"])))

    def test_no_mention_of_how_items_were_received(self):
        for text in strings(self.events):
            self.assertIsNone(RECEIVED.search(text), text)

    def test_every_event_cluster_exists(self):
        for event in self.events["events"]:
            self.assertIn(event["cluster"], self.by_id, event)

    def test_clusters_describe_their_areas(self):
        clusters = self.clusters["clusters"]
        self.assertEqual(len(clusters), 16)
        self.assertEqual(len(self.by_id), 16, "cluster ids are unique")
        memberships = {v["slug"] for v in self.taxonomy["facets"]["memberships"]["values"]}
        for c in clusters:
            self.assertTrue(c["name"] and c["full"] and c["region"], c["id"])
            self.assertRegex(c["colour"], HEX)
            self.assertIn(c["status"], STATUSES)
            for link in (c["web"], c["linkedin"]):
                self.assertTrue(link is None or link.startswith("https://"), c["id"])
            self.assertTrue(c["membership"] is None or c["membership"] in memberships, c["id"])
            self.assertTrue(c["regions"], f"{c['id']} has no regions")
            codes = [r["code"] for r in c["regions"]]
            self.assertEqual(len(codes), len(set(codes)), c["id"])
            for r in c["regions"]:
                self.assertEqual(set(r), {"code", "name"}, c["id"])
                self.assertRegex(r["code"], ONS_CODE)
                self.assertTrue(r["name"], c["id"])
        self.assertEqual(self.by_id["SCRDSC"]["membership"], "mbr-scrdsc")
        self.assertEqual(self.by_id["GLRDSC"]["membership"], "mbr-glrdsc")
        self.assertEqual(self.by_id["WalesDSC"]["membership"], "mbr-walesdsc")


class Exporter(unittest.TestCase):
    """The export rules, proved on a synthetic round-up with planted detail."""

    @classmethod
    def setUpClass(cls):
        cls.clusters, cls.events = exporter().build(SAMPLE, "2026-11-19")
        cls.text = json.dumps([cls.clusters, cls.events])

    def test_export_never_copies_members_detail(self):
        for planted in (
            "PLANTED-MEMBERS-TITLE", "PLANTED-MEMBERS-TIME", "PLANTED-MEMBERS-PLACE",
            "PLANTED-MEMBERS-SUMMARY", "PLANTED-MEMBERS-LINK",
            "PLANTED-NO-WEBSITE", "PLANTED-SOURCE", "PLANTED-POST", "PLANTED-DIRECTORY-NOTE",
        ):
            self.assertNotIn(planted, self.text)
        members = [e for e in self.events["events"] if e["audience"] == "members"]
        self.assertEqual(members, [{
            "audience": "members",
            "cluster": "SCRDSC",
            "date": "2026-12-05",
            "text": SIGNPOST,
            "link": "https://www.southcentralrdsc.co.uk/",
        }])

    def test_export_filters_items(self):
        for planted in (
            "PLANTED-PAST-EVENT", "PLANTED-UNDATED-EVENT", "PLANTED-FUNDING-CALL",
            "PLANTED-RECEIVED-MENTION", "PLANTED-UNKNOWN-CLUSTER",
        ):
            self.assertNotIn(planted, self.text)
        self.assertEqual(self.events["as_of"], "2026-11-19")
        public = [e for e in self.events["events"] if e["audience"] == "public"]
        self.assertEqual([e["title"] for e in public], ["Today's open day", "Public showcase"])
        self.assertEqual(public[0]["link"], None, "unsafe links are dropped")
        self.assertEqual(public[1], {
            "audience": "public",
            "cluster": "SCRDSC",
            "date": "2026-12-01",
            "time": "10:00",
            "where": "Portsmouth",
            "title": "Public showcase",
            "summary": "An open showcase for SMEs.",
            "link": "https://example.org/showcase",
        })
        ids = [c["id"] for c in self.clusters["clusters"]]
        self.assertEqual(ids, ["SCRDSC", "ScotlandDSC"])
        for cluster in self.clusters["clusters"]:
            self.assertEqual(set(cluster), CLUSTER_KEYS)
            self.assertTrue(cluster["regions"])


if __name__ == "__main__":
    unittest.main()
