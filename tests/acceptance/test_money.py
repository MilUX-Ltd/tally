"""Acceptance tests: money.json, where UK defence contract money goes.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for money.json (see docs/money-data.md) and for the rules in
scripts/build_money.py. They need no network. Do not edit these tests to make a build pass;
raise the problem instead.
"""

import datetime
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MONEY = ROOT / "money.json"
TALLY = ROOT / "tally-data.json"
BUILDER = ROOT / "scripts" / "build_money.py"

REGIONS = {
    "North East", "North West", "Yorkshire and The Humber", "East Midlands", "West Midlands",
    "East of England", "London", "South East", "South West", "Scotland", "Wales",
    "Northern Ireland",
}
TOP_KEYS = {
    "generated", "attribution", "sources", "period", "years", "regions", "overseas",
    "unplaced", "companies", "excluded",
}
ATTRIBUTION = "Contains public sector information licensed under the Open Government Licence v3.0."


def load_builder():
    spec = importlib.util.spec_from_file_location("build_money", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MoneyJson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = MONEY.read_bytes()
        cls.doc = json.loads(cls.raw)
        cls.names = {c["name"] for c in json.loads(TALLY.read_text(encoding="utf-8"))["companies"]}

    def test_shape(self):
        d = self.doc
        self.assertEqual(set(d), TOP_KEYS)
        self.assertEqual(d["attribution"], ATTRIBUTION)
        # The period starts on 1 January 2023 at the earliest; a build whose fetch was cut
        # short starts later and says so in its period.
        start = datetime.date.fromisoformat(d["period"]["from"])
        end = datetime.date.fromisoformat(d["period"]["to"])
        self.assertGreaterEqual(start, datetime.date(2023, 1, 1))
        self.assertLessEqual(start, end)
        datetime.date.fromisoformat(d["generated"])
        self.assertEqual(d["years"], list(range(start.year, end.year + 1)))
        self.assertTrue(set(d["sources"]) <= {"Contracts Finder", "Find a Tender"})
        self.assertEqual(set(d["excluded"]), {"frameworks", "non_gbp"})

    def test_compact_sorted_and_small(self):
        self.assertLess(len(self.raw), 1_600_000)
        text = self.raw.decode("utf-8").rstrip("\n")
        self.assertEqual(text, json.dumps(self.doc, sort_keys=True, separators=(",", ":"),
                                          ensure_ascii=False))

    def test_regions_and_overseas(self):
        years = {str(y) for y in self.doc["years"]}
        self.assertEqual(set(self.doc["regions"]), years)
        self.assertEqual(set(self.doc["overseas"]), years)
        self.assertEqual(set(self.doc["unplaced"]), years)
        for y, regs in self.doc["regions"].items():
            self.assertTrue(set(regs) <= REGIONS, set(regs) - REGIONS)
            for r in regs.values():
                # Amended under D-96j1u: the four supplier-size fields join the region contract.
                self.assertEqual(set(r), {"value", "count", "tally_value", "tally_count", "top",
                                          "sme_value", "sme_count", "large_value", "large_count"})
                self.assertLessEqual(r["tally_value"], r["value"])
                self.assertLessEqual(r["tally_count"], r["count"])
                self.check_top(r["top"])
        for y, cs in self.doc["overseas"].items():
            for name, c in cs.items():
                self.assertNotIn(name.lower(), {"uk", "united kingdom", "england"})
                self.assertEqual(set(c), {"value", "count", "top"})
                self.check_top(c["top"])
        for u in self.doc["unplaced"].values():
            self.assertEqual(set(u), {"value", "count"})

    def check_top(self, top):
        self.assertLessEqual(len(top), 5)
        for t in top:
            self.assertEqual(set(t), {"name", "value", "count", "tally"})
            self.assertIsInstance(t["value"], int)
            self.assertTrue(t["name"])
            if t["tally"] is not None:
                self.assertIn(t["tally"], self.names)

    def test_companies(self):
        for name, awards in self.doc["companies"].items():
            self.assertIn(name, self.names)
            for a in awards:
                self.assertEqual(set(a), {"date", "value", "buyer", "title", "url"})
                datetime.date.fromisoformat(a["date"])
                self.assertGreaterEqual(a["date"], self.doc["period"]["from"])
                self.assertLessEqual(a["date"], self.doc["period"]["to"])
                self.assertIsInstance(a["value"], int)
                self.assertTrue(a["url"] is None or a["url"].startswith("https://"))

    def test_no_personal_data(self):
        text = self.raw.decode("utf-8")
        self.assertIsNone(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}", text))
        self.assertNotIn("linkedin.com/in/", text.lower())


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load_builder()

    def test_allowlist(self):
        allow = self.b.ALLOW_RE
        for name in ["Ministry of Defence", "MINISTRY OF DEFENCE", "MOD Corsham",
                     "Defence Equipment & Support", "Defence Science and Technology Laboratory",
                     "Submarine Delivery Agency", "UK Hydrographic Office", "Royal Navy",
                     "AWE plc", "Atomic Weapons Establishment", "Single Source Regulations Office",
                     "Defence Infrastructure Organisation", "Dstl"]:
            self.assertTrue(allow.search(name), name)
        for name in ["Ministry of Justice", "Modern Housing Ltd", "Nuclear Restoration Services",
                     "Home Office", "Civil Nuclear Police Authority", "Department for Transport"]:
            self.assertFalse(allow.search(name), name)

    def test_frameworks(self):
        f = self.b.is_framework
        self.assertTrue(f({"tender": {"techniques": {"hasFrameworkAgreement": True}}}))
        self.assertTrue(f({"tender": {"techniques": {"hasDynamicPurchasingSystem": True}}}))
        self.assertFalse(f({"tender": {"procurementMethodDetails": "Call-off from a framework agreement"}}))
        self.assertFalse(f({"tender": {"procurementMethodDetails": "Call-off from a dynamic purchasing system"}}))
        self.assertFalse(f({"tender": {"procurementMethodDetails": "Open procedure"}}))
        self.assertFalse(f({"tender": {"procurementMethodRationale": "The contract is based on a framework agreement"}}))
        self.assertTrue(f({"tender": {"title": "Engineering Services Framework"}}))
        self.assertTrue(f({"tender": {}}, {"suppliers": [{}, {}, {}]}))

    def test_names(self):
        n = self.b.norm_name
        self.assertEqual(n("BAE Systems (UK) Limited"), n("BAE Systems"))
        self.assertEqual(n("AtkinsRéalis UK Ltd"), n("AtkinsRealis"))
        self.assertEqual(n("Smith & Sons Holdings PLC"), "smith and sons")
        self.assertEqual(self.b.norm_ch("1549447"), "01549447")
        self.assertEqual(self.b.norm_ch("SC123456"), "SC123456")
        self.assertIsNone(self.b.norm_ch("n/a"))

    def test_naming_rule(self):
        ok = self.b.nameable
        self.assertTrue(ok("Acme Engineering Ltd", None))
        self.assertTrue(ok("Saab AB", None))
        self.assertTrue(ok("Rheinmetall GmbH", None))
        self.assertTrue(ok("University of Bath", None))
        self.assertTrue(ok("J Smith", "01234567"))
        self.assertFalse(ok("John Smith", None))
        self.assertFalse(ok("J Smith Plumbing", None))

    def test_places(self):
        self.assertEqual(self.b.find_postcode("26 Finsbury Square, London, EC2A 1DS"), "EC2A 1DS")
        self.assertTrue(self.b.is_uk("United Kingdom"))
        self.assertFalse(self.b.is_uk("United States"))
        self.assertEqual(self.b.country_label("USA"), "United States")


if __name__ == "__main__":
    unittest.main()


class SupplierSize(unittest.TestCase):
    """The share to small and medium-sized firms (D-96j1u)."""

    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(MONEY.read_bytes())
        cls.b = load_builder()

    def test_sme_fields(self):
        known = 0
        for regs in self.doc["regions"].values():
            for r in regs.values():
                for k in ("sme_value", "sme_count", "large_value", "large_count"):
                    self.assertIsInstance(r[k], int)
                    self.assertGreaterEqual(r[k], 0)
                self.assertLessEqual(r["sme_value"] + r["large_value"], r["value"] + 1)
                self.assertLessEqual(r["sme_count"] + r["large_count"], r["count"])
                known += r["sme_count"] + r["large_count"]
        self.assertGreater(known, 0, "no supplier size is known anywhere")

    def test_supplier_scale(self):
        rec = self.b.supplier_record
        self.assertEqual(rec({"name": "A Ltd", "details": {"scale": "sme"}})["scale"], "sme")
        self.assertEqual(rec({"name": "A Ltd", "details": {"scale": " Large "}})["scale"], "large")
        self.assertIsNone(rec({"name": "A Ltd", "details": {}})["scale"])
        self.assertIsNone(rec({"name": "A Ltd"})["scale"])
        self.assertIsNone(rec({"name": "A Ltd", "details": {"scale": "micro?"}})["scale"])

    def test_scale_filled_from_same_supplier(self):
        rows = [
            {"name": "Alpha Systems Ltd", "ch": "01234567", "scale": "sme"},
            {"name": "ALPHA SYSTEMS LIMITED", "ch": "01234567", "scale": None},
            {"name": "Beta Engineering Ltd", "ch": None, "scale": "large"},
            {"name": "Beta Engineering Limited", "ch": None, "scale": None},
            {"name": "Gamma Ltd", "ch": None, "scale": None},
        ]
        self.b.fill_scale(rows)
        self.assertEqual([r["scale"] for r in rows], ["sme", "sme", "large", "large", None])
        # A supplier that declared both sizes keeps each notice's own, and fills nothing.
        mixed = [
            {"name": "Delta Ltd", "ch": "07654321", "scale": "sme"},
            {"name": "Delta Ltd", "ch": "07654321", "scale": "large"},
            {"name": "Delta Ltd", "ch": "07654321", "scale": None},
        ]
        self.b.fill_scale(mixed)
        self.assertEqual([r["scale"] for r in mixed], ["sme", "large", None])
