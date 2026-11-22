"""Acceptance tests: mod-spend.json, MOD's official spend with UK industry by region.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for mod-spend.json and for scripts/build_mod_spend.py (card 7475,
D-tnpb9). They need no network. Committed failing before the build. Do not edit these tests to
make a build pass; raise the problem instead.
"""

import importlib.util
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "mod-spend.json"
BUILDER = ROOT / "scripts" / "build_mod_spend.py"

REGIONS = [
    "East of England", "East Midlands", "London", "North East", "North West", "South East",
    "South West", "West Midlands", "Yorkshire and The Humber", "Northern Ireland", "Scotland", "Wales",
]
ENGLISH = REGIONS[:9]
TOP_KEYS = {"generated", "attribution", "source", "years", "breaks", "uk", "regions"}
FY = re.compile(r"^\d{4}/\d{2}$")


def load():
    spec = importlib.util.spec_from_file_location("build_mod_spend", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def table(title, unit, years, values, uk):
    """Rows as the ODS gives them: a title, notes, a heading row, England, regions, UK Total."""
    heads = [f"{y} ({unit}) [b] [note 1]" if y == "2020/21" else f"{y} ({unit})  " for y in years]
    rows = [[title], ["This worksheet contains one table."], ["Source: Analysis Directorate."], ["Region   ", *heads]]
    england = [sum(values[r][i] for r in ENGLISH) for i in range(len(years))]
    rows.append(["England", *[f"{v:,}" for v in england]])
    for r in REGIONS:
        rows.append([r, *[f"{v:,}" for v in values[r]]])
    rows.append(["UK Total", *[f"{v:,}" for v in uk]])
    return rows


YEARS = ["2019/20", "2020/21", "2021/22"]
VALUES = {r: [100 + i, 110 + i, 120 + i] for i, r in enumerate(REGIONS)}
UK = [sum(VALUES[r][i] for r in REGIONS) for i in range(3)]
PER = {r: [200 + 10 * i, 210 + 10 * i, 220 + 10 * i] for i, r in enumerate(REGIONS)}


def sheets(values=VALUES, uk=UK, per=PER, years=YEARS):
    return {
        "Table_2": table("Table 2 - MOD Direct Expenditure with UK Industry in Current Prices by Region", "£ million", years, values, uk),
        "Table_4": table("Table 4 - MOD Direct Expenditure per Person with UK Industry in Current Prices by Region", "£", years, per, [300, 310, 320]),
    }


def write_ods(path, tables):
    """A minimal ODS: a zip holding content.xml with one table per sheet."""
    ns = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
          'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
          'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"')
    body = []
    for name, rows in tables.items():
        body.append(f'<table:table table:name="{name}">')
        for row in rows:
            cells = "".join(f"<table:table-cell><text:p>{escape(c)}</text:p></table:table-cell>" for c in row)
            body.append(f"<table:table-row>{cells}</table:table-row>")
        body.append("</table:table>")
    xml = f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {ns}><office:body><office:spreadsheet>{"".join(body)}</office:spreadsheet></office:body></office:document-content>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr("content.xml", xml)


class FindEdition(unittest.TestCase):
    """Criterion 1."""

    def test_latest_edition_and_its_data_tables(self):
        b = load()
        collection = {"links": {"documents": [
            {"base_path": "/government/statistics/mod-regional-expenditure-statistics-with-industry-202425", "public_updated_at": "2026-06-10T09:57:14Z"},
            {"base_path": "/government/statistics/mod-regional-expenditure-statistics-with-industry-202526", "public_updated_at": "2026-09-24T08:30:09Z"},
            {"base_path": "/government/statistics/mod-regional-expenditure-statistics-with-industry-202324", "public_updated_at": "2024-11-21T00:00:00Z"},
        ]}}
        self.assertEqual(b.latest_edition(collection), "/government/statistics/mod-regional-expenditure-statistics-with-industry-202526")
        edition = {"details": {"attachments": [
            {"title": "MOD regional expenditure with industry 2025/26", "url": "/government/statistics/x"},
            {"title": "Data tables relating to MOD regional expenditure with industry 2025/26", "content_type": "application/vnd.oasis.opendocument.spreadsheet", "url": "https://assets.publishing.service.gov.uk/media/abc/Data_tables.ods"},
            {"title": "MOD SIC Groups to ONS SIC Class and Subclass", "content_type": "application/vnd.oasis.opendocument.spreadsheet", "url": "https://assets.publishing.service.gov.uk/media/def/SIC.ods"},
        ]}}
        self.assertEqual(b.data_tables_url(edition), "https://assets.publishing.service.gov.uk/media/abc/Data_tables.ods")

    def test_no_edition_or_no_data_tables_stops(self):
        b = load()
        with self.assertRaises(SystemExit):
            b.latest_edition({"links": {"documents": []}})
        with self.assertRaises(SystemExit):
            b.data_tables_url({"details": {"attachments": [{"title": "Report", "url": "/x"}]}})

    def test_data_tables_only_from_gov_uk_assets(self):
        b = load()
        with self.assertRaises(SystemExit):
            b.data_tables_url({"details": {"attachments": [
                {"title": "Data tables relating to MOD regional expenditure", "content_type": "application/vnd.oasis.opendocument.spreadsheet", "url": "https://example.com/t.ods"}]}})


class ReadTables(unittest.TestCase):
    """Criterion 2."""

    def test_parse_years_breaks_totals_and_regions(self):
        b = load()
        out = b.parse(sheets())
        self.assertEqual(out["years"], YEARS)
        self.assertEqual(out["breaks"], ["2020/21"])
        self.assertEqual(out["uk"]["2021/22"], UK[2] * 1_000_000)
        self.assertEqual(set(out["regions"]["2019/20"]), set(REGIONS))
        self.assertEqual(out["regions"]["2021/22"]["London"], {"value": VALUES["London"][2] * 1_000_000, "per_person": PER["London"][2]})

    def test_reads_a_real_ods_file(self):
        b = load()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.ods"
            write_ods(path, {"Cover_Sheet": [["Cover"]], **sheets()})
            read = b.read_ods(path)
        self.assertIn("Table_2", read)
        out = b.parse(read)
        self.assertEqual(out["regions"]["2020/21"]["Wales"]["value"], VALUES["Wales"][1] * 1_000_000)


class Guards(unittest.TestCase):
    """Criterion 3."""

    def setUp(self):
        self.b = load()

    def test_missing_region_stops(self):
        s = sheets()
        s["Table_2"] = [r for r in s["Table_2"] if r[0] != "Scotland"]
        with self.assertRaises(SystemExit):
            self.b.check(self.b.parse(s), None)

    def test_not_a_number_stops(self):
        s = sheets()
        s["Table_2"] = [[r[0], "[x]", *r[2:]] if r[0] == "London" else r for r in s["Table_2"]]
        with self.assertRaises(SystemExit):
            self.b.check(self.b.parse(s), None)

    def test_english_regions_must_add_to_england(self):
        values = {**VALUES, "London": [v + 50 for v in VALUES["London"]]}
        s = sheets(values=values, uk=[u + 50 for u in UK])
        s["Table_2"] = [[r[0], *[f"{int(x.replace(',', '')) - 50:,}" for x in r[1:]]] if r[0] == "England" else r for r in s["Table_2"]]
        with self.assertRaises(SystemExit):
            self.b.check(self.b.parse(s), None)

    def test_nations_must_add_to_uk_total(self):
        with self.assertRaises(SystemExit):
            self.b.check(self.b.parse(sheets(uk=[u + 20 for u in UK])), None)

    def test_rounding_within_tolerance_passes(self):
        self.b.check(self.b.parse(sheets(uk=[u + 1 for u in UK])), None)

    def test_latest_year_never_goes_backwards(self):
        doc = self.b.parse(sheets())
        previous = {**doc, "years": [*YEARS, "2022/23"]}
        with self.assertRaises(SystemExit):
            self.b.check(doc, previous)

    def test_known_year_moving_more_than_ten_percent_stops(self):
        doc = self.b.parse(sheets())
        previous = json.loads(json.dumps(doc))
        previous["uk"]["2020/21"] = int(doc["uk"]["2020/21"] * 1.2)
        with self.assertRaises(SystemExit):
            self.b.check(doc, previous)
        previous["uk"]["2020/21"] = int(doc["uk"]["2020/21"] * 1.05)
        self.b.check(doc, previous)


class Contract(unittest.TestCase):
    """Criterion 4."""

    def test_file_contract(self):
        self.assertTrue(DATA.exists(), "mod-spend.json is missing")
        d = json.loads(DATA.read_text(encoding="utf-8"))
        self.assertEqual(set(d), TOP_KEYS)
        self.assertIn("Open Government Licence v3.0", d["attribution"])
        self.assertEqual(set(d["source"]), {"title", "url", "published"})
        self.assertTrue(d["source"]["url"].startswith("https://www.gov.uk/government/statistics/"))
        self.assertTrue(d["years"] and all(FY.match(y) for y in d["years"]))
        self.assertEqual(d["years"], sorted(d["years"]))
        self.assertTrue(set(d["breaks"]) <= set(d["years"]))
        self.assertEqual(set(d["uk"]), set(d["years"]))
        self.assertEqual(set(d["regions"]), set(d["years"]))
        for y in d["years"]:
            regions = d["regions"][y]
            self.assertEqual(set(regions), set(REGIONS), y)
            for r, row in regions.items():
                self.assertEqual(set(row), {"value", "per_person"}, (y, r))
                self.assertIsInstance(row["value"], int)
                self.assertGreaterEqual(row["value"], 0)
                self.assertEqual(row["value"] % 1_000_000, 0, "values are published in whole £ million")
            total = sum(row["value"] for row in regions.values())
            self.assertLessEqual(abs(total - d["uk"][y]), 15_000_000, y)
