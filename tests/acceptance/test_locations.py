"""Acceptance tests: a location for every company.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for company locations. Do not edit them to make a
build pass; raise the problem instead.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
POSTCODE = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}$")
UK_LAT, UK_LON = (49.8, 60.95), (-8.7, 1.8)


def frontmatter(text):
    end = text.index("\n---", 3)
    meta = {}
    for key, value in re.findall(r"^([a-z-]+):[ \t]*(.*)$", text[:end], re.M):
        meta[key] = value.strip().strip("'\"")
    return meta


class Locations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {}
        for path in sorted((ROOT / "Companies").rglob("*.md")):
            cls.pages[path] = frontmatter(path.read_text(encoding="utf-8"))

    def test_every_uk_company_has_a_uk_point(self):
        """Every UK company has a UK point, or is marked region-level with a note and no point."""
        bad = []
        for path, meta in self.pages.items():
            if meta.get("uk-region") == "Overseas":
                continue
            if meta.get("location-source") == "region":
                # Approved amendment: a UK company whose town is not published is listed without a map point.
                if meta.get("lat") or meta.get("lon") or not meta.get("location-note"):
                    bad.append((path.name, "region source must have a note and no point"))
                continue
            try:
                lat, lon = float(meta.get("lat", "")), float(meta.get("lon", ""))
            except ValueError:
                bad.append((path.name, "no point"))
                continue
            if not (UK_LAT[0] <= lat <= UK_LAT[1] and UK_LON[0] <= lon <= UK_LON[1]):
                bad.append((path.name, "outside UK"))
            if meta.get("location-source") not in {"website", "companies-house", "town"}:
                bad.append((path.name, "bad source"))
        self.assertEqual(bad, [], f"{len(bad)} UK companies without a good point, e.g. {bad[:5]}")

    def test_postcodes_are_well_formed(self):
        bad = []
        for path, meta in self.pages.items():
            postcode, source = meta.get("postcode", ""), meta.get("location-source", "")
            if postcode:
                if not POSTCODE.match(postcode) or source not in {"website", "companies-house"}:
                    bad.append((path.name, postcode, source))
            elif source in {"website", "companies-house"}:
                bad.append((path.name, "source without postcode", source))
        self.assertTrue(any(m.get("postcode") for m in self.pages.values()), "no postcodes at all")
        self.assertEqual(bad, [], f"{len(bad)} bad postcodes, e.g. {bad[:5]}")

    def test_overseas_companies_have_a_country(self):
        overseas = [(p, m) for p, m in self.pages.items() if m.get("uk-region") == "Overseas"]
        self.assertTrue(overseas, "no overseas companies found")
        bad = [p.name for p, m in overseas if not m.get("country")]
        self.assertEqual(bad, [], f"{len(bad)} overseas companies without a country, e.g. {bad[:5]}")

    def test_viewer_data_carries_location(self):
        data = json.loads((ROOT / "tally-data.json").read_text(encoding="utf-8"))
        by_name = {c["name"]: c for c in data["companies"]}
        bad = []
        for path, meta in self.pages.items():
            record = by_name.get(meta.get("name", path.stem))
            if record is None:
                bad.append((path.name, "no record"))
                continue
            for key, field in (("postcode", "postcode"), ("location-source", "location_source"), ("country", "country")):
                if str(record.get(field, "") or "") != meta.get(key, ""):
                    bad.append((path.name, field))
            for key in ("lat", "lon"):
                want = meta.get(key, "")
                got = record.get(key)
                if (want == "") != (got in (None, "")) or (want and abs(float(want) - float(got)) > 1e-6):
                    bad.append((path.name, key))
        self.assertEqual(bad, [], f"{len(bad)} records differ, e.g. {bad[:5]}")


if __name__ == "__main__":
    unittest.main()
