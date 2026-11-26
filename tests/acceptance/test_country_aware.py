"""Acceptance tests: country-aware data (card 7479).

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for countries in the data: an ISO country code on
every company, countries.json with a per-country live flag, the region model of
country plus first-level region, and the guard that keeps Russia out. Committed
failing before the build. Do not edit them to make a build pass; raise the
problem instead.
"""

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

_spec = importlib.util.spec_from_file_location("gate", ROOT / ".github" / "scripts" / "check.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

CODE = re.compile(r"^[A-Z]{2}$")
BLOCS = {"europe", "north-america", "other"}
UK_BOUNDS = [-8.7, 49.8, 1.9, 60.9]

# Europe as decided on 26 November 2026 (D-bp4c1): the EU, the EEA, the UK,
# Switzerland, the Western Balkans, Ukraine, Moldova and Türkiye. ZZ is the ISO
# code for a country not known (one company is "Europe (country not stated)").
EU = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split())
EEA = {"IS", "LI", "NO"}
WESTERN_BALKANS = {"AL", "BA", "ME", "MK", "RS", "XK"}
EUROPE = EU | EEA | WESTERN_BALKANS | {"GB", "CH", "UA", "MD", "TR", "ZZ"}
NORTH_AMERICA = {"US", "CA", "MX"}


def frontmatter(text):
    end = text.index("\n---", 3)
    meta = {}
    for key, value in re.findall(r"^([a-z-]+):[ \t]*(.*)$", text[:end], re.M):
        meta[key] = value.strip().strip("'\"")
    return meta


def load_countries():
    return json.loads((ROOT / "countries.json").read_text(encoding="utf-8"))


def page_text(**fields):
    lines = ["---", "type: organisation"] + [f"{k}: {v}" for k, v in fields.items()] + ["tags:", "  - defence", "---", "# Example", ""]
    return "\n".join(lines)


SAMPLE_COUNTRIES = {
    "countries": [
        {"code": "GB", "name": "United Kingdom", "bloc": "europe", "live": True, "bounds": UK_BOUNDS, "regions": ["London", "Wales"]},
        {"code": "NO", "name": "Norway", "bloc": "europe", "live": False},
    ]
}


class CountriesFile(unittest.TestCase):
    """countries.json: one entry per country Tally knows, with its live flag."""

    @classmethod
    def setUpClass(cls):
        cls.data = load_countries()
        cls.countries = cls.data["countries"]
        cls.by_code = {c["code"]: c for c in cls.countries}

    def test_contract(self):
        """Every entry has a unique ISO code, a name, a bloc and a live flag; a live country has bounds and regions."""
        self.assertEqual(set(self.data) - {"generated", "note", "countries"}, set(), "countries.json carries unknown top-level keys")
        codes = [c["code"] for c in self.countries]
        self.assertEqual(len(codes), len(set(codes)), "a country code appears twice")
        for c in self.countries:
            self.assertTrue(set(c) <= {"code", "name", "aliases", "bloc", "live", "bounds", "regions"}, f"{c.get('code')}: unknown keys")
            self.assertRegex(c["code"], CODE)
            self.assertTrue(isinstance(c["name"], str) and 2 <= len(c["name"]) <= 60, f"{c['code']}: bad name")
            self.assertIn(c["bloc"], BLOCS, f"{c['code']}: bad bloc")
            self.assertIsInstance(c["live"], bool, f"{c['code']}: live must be true or false")
            for alias in c.get("aliases", []):
                self.assertTrue(isinstance(alias, str) and alias.strip(), f"{c['code']}: bad alias")
            if c["live"]:
                w, s, e, n = c["bounds"]
                self.assertTrue(-180 <= w < e <= 180 and -90 <= s < n <= 90, f"{c['code']}: bad bounds")
                regions = c["regions"]
                self.assertTrue(regions and len(regions) == len(set(regions)), f"{c['code']}: regions must be a non-empty list without repeats")

    def test_only_the_uk_is_live(self):
        """At this card only the UK is live, with today's bounds and its 12 regions."""
        live = sorted(c["code"] for c in self.countries if c["live"])
        self.assertEqual(live, ["GB"])
        gb = self.by_code["GB"]
        self.assertEqual(gb["name"], "United Kingdom")
        self.assertEqual(gb["bloc"], "europe")
        self.assertEqual(gb["bounds"], UK_BOUNDS)
        taxonomy = json.loads((ROOT / "taxonomy.json").read_text(encoding="utf-8"))
        uk_regions = [v["value"] for v in taxonomy["facets"]["region"]["values"] if v["value"] != "Overseas"]
        self.assertEqual(gb["regions"], uk_regions)

    def test_blocs_are_as_decided(self):
        """Europe is the EU, EEA, UK, Switzerland, Western Balkans, Ukraine, Moldova and Türkiye; Belarus and Russia are never Europe."""
        for c in self.countries:
            if c["bloc"] == "europe":
                self.assertIn(c["code"], EUROPE, f"{c['code']} is not in Europe as decided")
            if c["bloc"] == "north-america":
                self.assertIn(c["code"], NORTH_AMERICA)
            if c["code"] in EUROPE:
                self.assertEqual(c["bloc"], "europe", f"{c['code']} should be in the Europe bloc")
        for code in ("BY", "RU"):
            if code in self.by_code:
                self.assertNotEqual(self.by_code[code]["bloc"], "europe")


class CompanyCountry(unittest.TestCase):
    """Every company page and every tally-data.json entry carries its ISO country code."""

    @classmethod
    def setUpClass(cls):
        cls.countries = {c["code"]: c for c in load_countries()["countries"]}
        cls.pages = {}
        for path in sorted((ROOT / "Companies").rglob("*.md")):
            cls.pages[path] = frontmatter(path.read_text(encoding="utf-8"))
        cls.data = json.loads((ROOT / "tally-data.json").read_text(encoding="utf-8"))["companies"]

    def test_every_page_has_a_known_country_code(self):
        bad = [p.name for p, m in self.pages.items() if m.get("country-code") not in self.countries]
        self.assertEqual(bad, [], f"{len(bad)} pages without a known country-code, e.g. {bad[:5]}")

    def test_uk_companies_are_gb(self):
        """The UK is a value, not the absence of one: every page outside Overseas is GB, every Overseas page is not."""
        bad = []
        for path, meta in self.pages.items():
            overseas = meta.get("uk-region") == "Overseas"
            if overseas and meta.get("country-code") == "GB":
                bad.append((path.name, "overseas page marked GB"))
            if not overseas and meta.get("country-code") != "GB":
                bad.append((path.name, "UK page not marked GB"))
        self.assertEqual(bad, [], f"{len(bad)} pages, e.g. {bad[:5]}")

    def test_overseas_codes_match_country_names(self):
        """Each overseas company's code is the country its page names (by name or alias)."""
        bad = []
        for path, meta in self.pages.items():
            if meta.get("uk-region") != "Overseas":
                continue
            entry = self.countries.get(meta.get("country-code"))
            names = {entry["name"], *entry.get("aliases", [])} if entry else set()
            if meta.get("country", "") not in names:
                bad.append((path.name, meta.get("country"), meta.get("country-code")))
        self.assertEqual(bad, [], f"{len(bad)} overseas pages whose code does not match the country, e.g. {bad[:5]}")

    def test_country_not_stated_is_zz(self):
        """A company whose country is not stated carries ZZ, the ISO code for an unknown country, and is never live."""
        for path, meta in self.pages.items():
            if "country not stated" in meta.get("country", "").lower():
                self.assertEqual(meta.get("country-code"), "ZZ", path.name)
        if "ZZ" in self.countries:
            self.assertFalse(self.countries["ZZ"]["live"])

    def test_tally_data_carries_country_code(self):
        """tally-data.json carries country_code for every company, matching its page; country (the name) is unchanged."""
        by_name = {m.get("name"): m for m in self.pages.values()}
        bad = []
        for c in self.data:
            page = by_name.get(c["name"])
            if c.get("country_code") not in self.countries:
                bad.append((c["name"], "unknown country_code"))
            elif page and page.get("country-code") != c["country_code"]:
                bad.append((c["name"], "differs from its page"))
            if c.get("country_code") == "GB" and c.get("country"):
                bad.append((c["name"], "a UK company keeps country empty, so older readers still see it as UK"))
        self.assertEqual(bad, [], f"{len(bad)} companies, e.g. {bad[:5]}")


class RegionModel(unittest.TestCase):
    """A company's region is a first-level region of its own country, or Overseas while its country is not live."""

    def test_region_belongs_to_country(self):
        countries = {c["code"]: c for c in load_countries()["countries"]}
        data = json.loads((ROOT / "tally-data.json").read_text(encoding="utf-8"))["companies"]
        bad = []
        for c in data:
            entry = countries.get(c.get("country_code"))
            if not entry:
                continue
            if entry["live"]:
                if c.get("region") and c["region"] not in entry["regions"]:
                    bad.append((c["name"], c["region"], entry["code"]))
            elif c.get("region") != "Overseas":
                bad.append((c["name"], c.get("region"), f"{entry['code']} is not live, so the region is Overseas"))
        self.assertEqual(bad, [], f"{len(bad)} companies, e.g. {bad[:5]}")


class Russia(unittest.TestCase):
    """Russia never reaches the live site (D-ba3h3)."""

    def test_russia_is_never_live_and_no_company_is_in_russia(self):
        countries = {c["code"]: c for c in load_countries()["countries"]}
        if "RU" in countries:
            self.assertFalse(countries["RU"]["live"])
        data = json.loads((ROOT / "tally-data.json").read_text(encoding="utf-8"))["companies"]
        self.assertEqual([c["name"] for c in data if c.get("country_code") == "RU"], [])
        pages = [p.name for p in (ROOT / "Companies").rglob("*.md") if frontmatter(p.read_text(encoding="utf-8")).get("country-code") == "RU"]
        self.assertEqual(pages, [])
        self.assertFalse((ROOT / "Companies" / "Russia").exists())

    def test_gate_refuses_russia(self):
        """The gate refuses a page in Russia, and a countries file that makes Russia live."""
        page = page_text(name="Example", **{"uk-region": "Overseas", "country": "Russia", "country-code": "RU"})
        self.assertTrue(gate.country_problems(page, SAMPLE_COUNTRIES), "a page in Russia must fail the gate")
        bad = {"countries": SAMPLE_COUNTRIES["countries"] + [{"code": "RU", "name": "Russia", "bloc": "other", "live": True, "bounds": [19, 41, 180, 82], "regions": ["Moscow"]}]}
        self.assertTrue(gate.countries_problems(bad), "a live Russia must fail the gate")


class Gate(unittest.TestCase):
    """The gate checks country codes on every page and the shape of countries.json."""

    def test_gate_accepts_good_pages(self):
        uk = page_text(name="Example", **{"uk-region": "London", "country-code": "GB"})
        abroad = page_text(name="Example", **{"uk-region": "Overseas", "country": "Norway", "country-code": "NO"})
        self.assertEqual(gate.country_problems(uk, SAMPLE_COUNTRIES), [])
        self.assertEqual(gate.country_problems(abroad, SAMPLE_COUNTRIES), [])
        self.assertEqual(gate.countries_problems(SAMPLE_COUNTRIES), [])

    def test_gate_refuses_bad_pages(self):
        cases = {
            "no code": page_text(name="Example", **{"uk-region": "London"}),
            "unknown code": page_text(name="Example", **{"uk-region": "Overseas", "country": "Atlantis", "country-code": "QQ"}),
            "lower case": page_text(name="Example", **{"uk-region": "London", "country-code": "gb"}),
            "UK region outside GB": page_text(name="Example", **{"uk-region": "London", "country-code": "NO"}),
            "overseas marked GB": page_text(name="Example", **{"uk-region": "Overseas", "country": "Norway", "country-code": "GB"}),
            "region not in a live country": page_text(name="Example", **{"uk-region": "Atlantis", "country-code": "GB"}),
        }
        for label, text in cases.items():
            with self.subTest(label):
                self.assertTrue(gate.country_problems(text, SAMPLE_COUNTRIES), label)

    def test_gate_refuses_bad_countries_files(self):
        gb = SAMPLE_COUNTRIES["countries"][0]
        cases = {
            "repeated code": [gb, gb],
            "live without bounds": [{**gb, "bounds": None}],
            "live without regions": [{**gb, "regions": []}],
            "bad bloc": [{**gb, "bloc": "atlantis"}],
            "live not a boolean": [{**gb, "live": "yes"}],
            "unknown key": [{**gb, "contact": "x"}],
            "Belarus in Europe": [gb, {"code": "BY", "name": "Belarus", "bloc": "europe", "live": False}],
        }
        for label, countries in cases.items():
            with self.subTest(label):
                self.assertTrue(gate.countries_problems({"countries": countries}), label)


if __name__ == "__main__":
    unittest.main()
