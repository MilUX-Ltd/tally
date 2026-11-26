"""Acceptance tests: Norway (card 7480).

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

The contract for Norwegian companies: the status check against the Brønnøysund
Register Centre's Central Coordinating Register for Legal Entities (open data,
NLOD), the county each company is in, its point from its registered business
postcode, legal persons only, no personal fields, the weekly guards, and the
gate's check on Norwegian pages. Committed failing before the build. Do not
edit them to make a build pass; raise the problem instead.
"""

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BUILDER = ROOT / "scripts" / "build_norway_register.py"
OUT = ROOT / "norway-register.json"

_gate_spec = importlib.util.spec_from_file_location("gate", ROOT / ".github" / "scripts" / "check.py")
gate = importlib.util.module_from_spec(_gate_spec)
_gate_spec.loader.exec_module(gate)

# Norway's 15 counties from 1 January 2024, by the first two digits of the municipality number.
COUNTIES = {
    "03": "Oslo", "11": "Rogaland", "15": "Møre og Romsdal", "18": "Nordland", "31": "Østfold",
    "32": "Akershus", "33": "Buskerud", "34": "Innlandet", "39": "Vestfold", "40": "Telemark",
    "42": "Agder", "46": "Vestland", "50": "Trøndelag", "55": "Troms", "56": "Finnmark",
}
NORWAY_BOUNDS = [4.5, 57.9, 31.2, 71.2]
NLOD = (
    "Contains data under the Norwegian licence for Open Government data (NLOD) "
    "distributed by the Brønnøysund Register Centre."
)
# Fields the register returns that Tally must never keep: contacts and free text about the entity.
PERSONAL = {"epostadresse", "telefon", "mobil", "aktivitet", "vedtektsfestetFormaal", "postadresse", "adresse"}


def load_builder():
    spec = importlib.util.spec_from_file_location("build_norway_register", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unit(**overrides):
    """A register unit shaped as the open API returns it, with contact fields that must be dropped."""
    u = {
        "organisasjonsnummer": "943753709",
        "navn": "EXAMPLE FORSVAR AS",
        "organisasjonsform": {"kode": "AS", "beskrivelse": "Aksjeselskap"},
        "naeringskode1": {"kode": "25.400", "beskrivelse": "Produksjon av våpen og ammunisjon"},
        "forretningsadresse": {
            "adresse": ["Example gate 1"], "postnummer": "3616", "poststed": "KONGSBERG",
            "kommune": "KONGSBERG", "kommunenummer": "3303", "land": "Norge", "landkode": "NO",
        },
        "epostadresse": "post@example.no",
        "telefon": "+47 00 00 00 00",
        "aktivitet": ["Free text the company wrote about itself."],
        "hjemmeside": "www.example.no",
        "konkurs": False,
        "underAvvikling": False,
        "underTvangsavviklingEllerTvangsopplosning": False,
        "stiftelsesdato": "1990-01-01",
    }
    u.update(overrides)
    return u


GEONAMES = "\n".join(
    [
        "NO\t3616\tKongsberg\tBuskerud\t33\tKongsberg\t3303\t\t\t59.6689\t9.6502\t4",
        "NO\t7010\tTrondheim\tTrøndelag\t50\tTrondheim\t5001\t\t\t63.4305\t10.3951\t4",
        "NO\t9170\tLongyearbyen\tSvalbard\t21\tSvalbard\t2111\t\t\t78.2232\t15.6267\t4",
        "NO\tbad\tNowhere\t\t\t\t\t\t\tnot-a-number\t10\t4",
    ]
)


class Builder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load_builder()


class OrganisationNumber(Builder):
    def test_check_digit(self):
        """A Norwegian organisation number is nine digits with a modulus 11 check digit."""
        self.assertTrue(self.b.org_number_valid("943753709"))
        self.assertFalse(self.b.org_number_valid("943753708"))
        self.assertFalse(self.b.org_number_valid("94375370"))
        self.assertFalse(self.b.org_number_valid("94375370x"))
        self.assertFalse(self.b.org_number_valid(" 943753709"))


class Status(Builder):
    def test_active(self):
        self.assertEqual(self.b.unit_status(unit())["status"], "active")

    def test_deleted_is_closed(self):
        s = self.b.unit_status(unit(slettedato="2026-03-01"))
        self.assertEqual((s["status"], s["date"]), ("deleted", "2026-03-01"))
        self.assertEqual(self.b.STATUS_GROUP[s["status"]], "closed")

    def test_insolvency_and_winding_up_are_flagged(self):
        for field, status in (("konkurs", "bankruptcy"), ("underAvvikling", "winding-up"), ("underTvangsavviklingEllerTvangsopplosning", "compulsory-dissolution")):
            with self.subTest(field):
                s = self.b.unit_status(unit(**{field: True}))
                self.assertEqual(s["status"], status)
                self.assertEqual(self.b.STATUS_GROUP[status], "flagged")

    def test_unknown_number_is_not_found(self):
        self.assertEqual(self.b.unit_status(None)["status"], "not-found")


class LegalPersonsOnly(Builder):
    def test_sole_proprietorships_are_refused(self):
        """A sole proprietorship (ENK) is a person, not a company: never listed."""
        self.assertFalse(self.b.legal_person(unit(organisasjonsform={"kode": "ENK", "beskrivelse": "Enkeltpersonforetak"})))
        for kode in ("AS", "ASA", "SA", "ANS", "DA", "NUF", "STI"):
            with self.subTest(kode):
                self.assertTrue(self.b.legal_person(unit(organisasjonsform={"kode": kode})))

    def test_no_personal_fields_are_kept(self):
        """What Tally keeps of a unit: number, name, status, date, county, postcode, place. Nothing else."""
        kept = self.b.slim_unit(unit())
        self.assertEqual(set(kept), {"brreg", "name", "status", "date", "region", "postcode", "place"})
        self.assertEqual(kept["region"], "Buskerud")
        self.assertEqual((kept["postcode"], kept["place"]), ("3616", "Kongsberg"))
        text = json.dumps(kept, ensure_ascii=False)
        self.assertNotIn("post@example.no", text)
        self.assertNotIn("+47", text)
        self.assertNotIn("Example gate", text)
        self.assertNotIn("Free text", text)


class Counties(Builder):
    def test_county_from_municipality_number(self):
        for number, county in (("0301", "Oslo"), ("3303", "Buskerud"), ("5001", "Trøndelag"), ("4601", "Vestland"), ("5601", "Finnmark")):
            with self.subTest(number):
                self.assertEqual(self.b.county_for(number), county)

    def test_every_county(self):
        for prefix, county in COUNTIES.items():
            self.assertEqual(self.b.county_for(prefix + "01"), county)

    def test_outside_the_counties(self):
        """Svalbard, Jan Mayen, pre-2024 numbers and nonsense have no county."""
        for number in ("2111", "2211", "3005", "1201", "", "abcd", "33"):
            with self.subTest(number):
                self.assertEqual(self.b.county_for(number), "")


class Points(Builder):
    def test_postcode_points_from_geonames(self):
        table = self.b.read_geonames(GEONAMES)
        self.assertEqual(table["3616"], (59.6689, 9.6502, "Kongsberg"))
        self.assertEqual(self.b.point_for("3616", table), (59.6689, 9.6502))
        self.assertNotIn("bad", table)

    def test_no_point_outside_mainland_norway_or_unknown(self):
        table = self.b.read_geonames(GEONAMES)
        self.assertIsNone(self.b.point_for("9170", table))  # Svalbard, outside the map's Norway
        self.assertIsNone(self.b.point_for("0000", table))
        self.assertIsNone(self.b.point_for("", table))


class Guards(Builder):
    def test_failures_within_limit(self):
        self.b.check_guards({"companies": 200, "failed": 2}, closed=[], previous_closed=[])

    def test_too_many_failures_refused(self):
        with self.assertRaises(SystemExit):
            self.b.check_guards({"companies": 200, "failed": 20}, closed=[], previous_closed=[])

    def test_closed_jump_refused(self):
        with self.assertRaises(SystemExit):
            self.b.check_guards({"companies": 200, "failed": 0}, closed=list(range(12)), previous_closed=list(range(5)))

    def test_closed_growth_allowed(self):
        self.b.check_guards({"companies": 200, "failed": 0}, closed=list(range(6)), previous_closed=list(range(5)))


class Contract(unittest.TestCase):
    """norway-register.json, once built, keeps to its contract."""

    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(OUT.read_text(encoding="utf-8"))

    def test_contract(self):
        self.assertEqual(set(self.data), {"generated", "attribution", "source", "checked", "closed", "flagged", "not_found"})
        self.assertEqual(self.data["attribution"], NLOD)
        self.assertRegex(self.data["generated"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(set(self.data["checked"]), {"companies", "found", "not_found", "failed"})

    def test_rows(self):
        for group in ("closed", "flagged"):
            for row in self.data[group]:
                self.assertEqual(set(row), {"name", "brreg", "status", "date"}, row)
                self.assertTrue(load_builder().org_number_valid(row["brreg"]))
        text = json.dumps(self.data, ensure_ascii=False)
        self.assertNotRegex(text, r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}")

    def test_only_tally_companies(self):
        numbers = set()
        for path in (ROOT / "Companies").rglob("*.md"):
            m = re.search(r"^brreg:[ \t]*\"?(\d{9})\"?[ \t]*$", path.read_text(encoding="utf-8"), re.M)
            if m:
                numbers.add(m.group(1))
        for group in ("closed", "flagged", "not_found"):
            for row in self.data[group]:
                self.assertIn(row["brreg"] if isinstance(row, dict) else row, numbers)


class NorwayInCountries(unittest.TestCase):
    def test_norway_has_bounds_and_counties(self):
        """countries.json gives Norway its mainland bounds and its 15 counties (live is turned on in its own change)."""
        countries = {c["code"]: c for c in json.loads((ROOT / "countries.json").read_text(encoding="utf-8"))["countries"]}
        no = countries["NO"]
        self.assertEqual(no["bloc"], "europe")
        self.assertEqual(no["bounds"], NORWAY_BOUNDS)
        self.assertEqual(sorted(no["regions"]), sorted(COUNTIES.values()))
        self.assertEqual(len(no["regions"]), 15)


class NorwegianPages(unittest.TestCase):
    """Every Norwegian company page names its register entry and is placed by the rules."""

    def test_gate_checks_the_register_number(self):
        page = lambda extra: "---\ntype: organisation\nname: Example\ncountry: Norway\ncountry-code: NO\nuk-region: Overseas\n" + extra + "tags:\n  - defence\n---\n# Example\n"
        self.assertEqual(gate.register_problems(page('brreg: "943753709"\n')), [])
        self.assertTrue(gate.register_problems(page("")), "a Norwegian page needs its organisation number")
        self.assertTrue(gate.register_problems(page('brreg: "943753708"\n')), "the check digit must be right")
        uk = "---\ntype: organisation\nname: Example\nuk-region: London\ncountry-code: GB\ntags:\n  - defence\n---\n"
        self.assertEqual(gate.register_problems(uk), [])

    def test_norwegian_pages_follow_the_rules(self):
        """Holds for whatever Norwegian pages exist: a valid number, a point inside Norway or none, a known source."""
        bad = []
        for path in (ROOT / "Companies").rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            if not re.search(r"^country-code:[ \t]*NO[ \t]*$", text, re.M):
                continue
            bad += [(path.name, p) for p in gate.register_problems(text)]
            lat = re.search(r"^lat:[ \t]*(.+)$", text, re.M)
            lon = re.search(r"^lon:[ \t]*(.+)$", text, re.M)
            if lat and lon:
                la, lo = float(lat.group(1)), float(lon.group(1))
                if not (NORWAY_BOUNDS[1] <= la <= NORWAY_BOUNDS[3] and NORWAY_BOUNDS[0] <= lo <= NORWAY_BOUNDS[2]):
                    bad.append((path.name, "point outside Norway"))
                source = re.search(r"^location-source:[ \t]*(.+)$", text, re.M)
                if not source or source.group(1).strip() not in {"register", "website", "town"}:
                    bad.append((path.name, "bad location-source"))
        self.assertEqual(bad, [])


class Sample(Builder):
    def test_accuracy_sample(self):
        """The accuracy sample: 50 distinct companies, the same for the same seed, all of them when fewer."""
        names = [f"Company {i}" for i in range(180)]
        a = self.b.accuracy_sample(names, seed="2026-12-01")
        self.assertEqual(len(a), 50)
        self.assertEqual(len(set(a)), 50)
        self.assertEqual(a, self.b.accuracy_sample(names, seed="2026-12-01"))
        self.assertNotEqual(a, self.b.accuracy_sample(names, seed="2026-12-02"))
        self.assertEqual(sorted(self.b.accuracy_sample(names[:30], seed="x")), sorted(names[:30]))


if __name__ == "__main__":
    unittest.main()
