"""Acceptance tests: companies-house.json, closed Tally companies and the formed and closed trend.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for companies-house.json (see docs/companies-house-data.md) and
for the rules in scripts/build_companies_house.py. They need no network. Do not edit these tests
to make a build pass; raise the problem instead.
"""

import datetime
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "companies-house.json"
TALLY = ROOT / "tally-data.json"
BUILDER = ROOT / "scripts" / "build_companies_house.py"

TOP_KEYS = {"generated", "attribution", "source", "checked", "closed", "flagged", "not_found", "trend"}
ATTRIBUTION = "Contains public sector information licensed under the Open Government Licence v3.0."
CODES = {"25400", "30400", "84220"}
CLOSED = {"dissolved", "converted-closed", "removed", "closed"}
FLAGGED = {"liquidation", "administration", "receivership", "insolvency-proceedings", "voluntary-arrangement"}
CH_NUMBER = re.compile(r"^(?:[0-9]{8}|[A-Z]{2}[0-9]{6}|R[0-9]{7})$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PERSONAL = {"officers", "address", "registered_office_address", "date_of_birth", "email", "persons"}


def load_builder():
    spec = importlib.util.spec_from_file_location("build_companies_house", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def keys_in(value):
    """Every dictionary key anywhere in a JSON value."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from keys_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from keys_in(v)


class StatusSort(unittest.TestCase):
    """Criterion 1: a company profile is sorted into closed, flagged or active; a 404 into not found."""

    def setUp(self):
        self.b = load_builder()

    def test_dissolved_is_closed(self):
        kind, rec = self.b.sort_profile({"company_status": "dissolved", "date_of_cessation": "2024-05-14"})
        self.assertEqual(kind, "closed")
        self.assertEqual(rec, {"status": "dissolved", "date": "2024-05-14"})

    def test_every_closed_status(self):
        for status in CLOSED:
            self.assertEqual(self.b.sort_profile({"company_status": status})[0], "closed", status)

    def test_insolvency_is_flagged(self):
        for status in FLAGGED:
            kind, rec = self.b.sort_profile({"company_status": status})
            self.assertEqual(kind, "flagged", status)
            self.assertEqual(rec["status"], status)

    def test_strike_off_proposal_is_flagged(self):
        kind, rec = self.b.sort_profile({
            "company_status": "active", "company_status_detail": "active-proposal-to-strike-off"})
        self.assertEqual(kind, "flagged")
        self.assertEqual(rec, {"status": "active", "detail": "active-proposal-to-strike-off"})

    def test_other_detail_is_not_flagged(self):
        self.assertEqual(self.b.sort_profile({"company_status": "active", "company_status_detail": "something-else"})[0], "active")

    def test_northern_ireland_numbers(self):
        self.assertEqual(self.b.norm_ch("R0000401"), "R0000401")
        self.assertEqual(self.b.norm_ch("NI 012345"), "NI012345")
        self.assertEqual(self.b.norm_ch("1234"), "00001234")

    def test_active_is_active(self):
        self.assertEqual(self.b.sort_profile({"company_status": "active"})[0], "active")
        self.assertEqual(self.b.sort_profile({"company_status": "open"})[0], "active")

    def test_unknown_profile_is_not_found(self):
        self.assertEqual(self.b.sort_profile(None)[0], "not_found")

    def test_bad_date_dropped(self):
        _, rec = self.b.sort_profile({"company_status": "dissolved", "date_of_cessation": "14/05/2024"})
        self.assertEqual(rec, {"status": "dissolved"})


class TrendRules(unittest.TestCase):
    """Criterion 3: the trend's totals are consistent and the current year is partial."""

    def setUp(self):
        self.b = load_builder()

    def test_total_within_bounds(self):
        self.b.check_total(5, {"25400": 3, "30400": 2, "84220": 0})
        self.b.check_total(3, {"25400": 3, "30400": 2, "84220": 0})

    def test_total_below_largest_refused(self):
        with self.assertRaises(SystemExit):
            self.b.check_total(2, {"25400": 3, "30400": 2, "84220": 0})

    def test_total_above_sum_refused(self):
        with self.assertRaises(SystemExit):
            self.b.check_total(6, {"25400": 3, "30400": 2, "84220": 0})

    def test_years_and_partial(self):
        years = self.b.trend_years(datetime.date(2026, 11, 20))
        self.assertEqual(years[0], (2010, False))
        self.assertEqual(years[-1], (2026, True))
        self.assertEqual(len(years), 17)

    def test_new_years_day(self):
        years = self.b.trend_years(datetime.date(2029, 1, 1))
        self.assertEqual(years[-1], (2028, True))
        self.assertEqual(self.b.year_range(2028, datetime.date(2029, 1, 1)), ("2028-01-01", "2028-12-31"))

    def test_year_ranges(self):
        self.assertEqual(self.b.year_range(2024, datetime.date(2026, 11, 20)), ("2024-01-01", "2024-12-31"))
        self.assertEqual(self.b.year_range(2026, datetime.date(2026, 11, 20)), ("2026-01-01", "2026-11-19"))


class Guards(unittest.TestCase):
    """Criterion 4: a run with too many failed lookups, or with closed companies doubling, stops."""

    def setUp(self):
        self.b = load_builder()

    def test_failures_within_limit(self):
        self.b.check_failures(2, 1000)

    def test_too_many_failures_refused(self):
        with self.assertRaises(SystemExit):
            self.b.check_failures(21, 1000)

    def test_closed_jump_refused(self):
        with self.assertRaises(SystemExit):
            self.b.check_closed_jump(previous=10, now=21)

    def test_closed_growth_allowed(self):
        self.b.check_closed_jump(previous=10, now=20)
        self.b.check_closed_jump(previous=None, now=300)
        self.b.check_closed_jump(previous=0, now=5)
        self.b.check_closed_jump(previous=4, now=9)

    def test_closed_jump_from_few_refused(self):
        with self.assertRaises(SystemExit):
            self.b.check_closed_jump(previous=0, now=11)

    def year(self, n, formed, dissolved, partial=False):
        return {"year": n, "partial": partial, "formed": {"total": formed}, "dissolved": {"total": dissolved}}

    def test_zero_year_refused(self):
        with self.assertRaises(SystemExit):
            self.b.check_trend_against(None, [self.year(2024, 0, 0), self.year(2025, 5, 5, True)])

    def test_trend_halving_refused(self):
        previous = {"trend": {"years": [self.year(2024, 150, 150)]}}
        with self.assertRaises(SystemExit):
            self.b.check_trend_against(previous, [self.year(2024, 150, 60)])

    def test_trend_steady_allowed(self):
        previous = {"trend": {"years": [self.year(2024, 150, 150)]}}
        self.b.check_trend_against(previous, [self.year(2024, 152, 149), self.year(2025, 0, 0, True)])


class Contract(unittest.TestCase):
    """Criteria 2 and 3: the published file."""

    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(DATA.read_text(encoding="utf-8"))
        cls.tally = {c["name"] for c in json.loads(TALLY.read_text(encoding="utf-8"))["companies"]}

    def test_contract(self):
        d = self.doc
        self.assertEqual(set(d), TOP_KEYS)
        self.assertEqual(d["attribution"], ATTRIBUTION)
        self.assertRegex(d["generated"], DATE)
        self.assertEqual(set(d["checked"]), {"companies", "found", "not_found", "failed"})
        self.assertEqual(d["checked"]["not_found"], len(d["not_found"]))

    def test_only_tally_companies(self):
        for section in ("closed", "flagged", "not_found"):
            for row in self.doc[section]:
                self.assertIn(row["name"], self.tally, row)
                self.assertRegex(row["ch"], CH_NUMBER)

    def test_statuses(self):
        for row in self.doc["closed"]:
            self.assertIn(row["status"], CLOSED)
            if "date" in row:
                self.assertRegex(row["date"], DATE)
        for row in self.doc["flagged"]:
            self.assertTrue(row["status"] in FLAGGED or row.get("detail") == "active-proposal-to-strike-off", row)

    def test_no_personal_fields(self):
        self.assertFalse(PERSONAL & set(keys_in(self.doc)))

    def test_trend(self):
        t = self.doc["trend"]
        self.assertEqual(set(t["codes"]), CODES)
        years = [y["year"] for y in t["years"]]
        self.assertEqual(years, sorted(years))
        self.assertEqual(years[0], 2010)
        for y in t["years"]:
            self.assertEqual(y["partial"], y is t["years"][-1])
            for kind in ("formed", "dissolved"):
                per = [y[kind][c] for c in CODES]
                self.assertTrue(max(per) <= y[kind]["total"] <= sum(per), y)


if __name__ == "__main__":
    unittest.main()
