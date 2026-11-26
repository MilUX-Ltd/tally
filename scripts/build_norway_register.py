#!/usr/bin/env python3
"""Build norway-register.json: Norwegian Tally companies that have closed or are in trouble.

Reads the Brønnøysund Register Centre's Central Coordinating Register for Legal Entities
(Enhetsregisteret) through its open API, which needs no key, under the Norwegian licence for
Open Government data (NLOD 2.0). Standard library only.

    python3 scripts/build_norway_register.py --previous norway-register.json

Every company page with `country-code: NO` and a `brreg` organisation number is looked up. An
entity deleted from the register goes in `closed`; one in bankruptcy, winding up or compulsory
dissolution goes in `flagged`; a number the register does not know goes in `not_found` (the
number may be wrong in Tally, so it is not treated as closed).

The register's answer also carries email addresses, phone numbers, street addresses and free
text. None of it is ever kept: a unit is cut down to its number, name, status, date, county,
postcode and place (`slim_unit`). Sole proprietorships are people, not companies, and are never
listed (`legal_person`).

The same module holds the rules the first load of Norwegian companies uses: the county from the
municipality number, the point from a GeoNames postcode (CC BY 4.0), and the accuracy sample.
Rules and caveats: docs/norway-data.md.
"""

import argparse
import datetime
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "Companies"
OUT = ROOT / "norway-register.json"
API = "https://data.brreg.no/enhetsregisteret/api/enheter/"
ATTRIBUTION = (
    "Contains data under the Norwegian licence for Open Government data (NLOD) "
    "distributed by the Brønnøysund Register Centre."
)
SOURCE = "Brønnøysund Register Centre, Central Coordinating Register for Legal Entities"
USER_AGENT = "tally-register-check"
PAUSE = 0.2
MAX_FAILED_SHARE = 0.02
SAMPLE_SIZE = 50

# Mainland Norway, west, south, east, north: the same bounds as countries.json.
NORWAY_BOUNDS = (4.5, 57.9, 31.2, 71.2)

# Norway's 15 counties from 1 January 2024, by the first two digits of the municipality number.
# Svalbard (21) and Jan Mayen (22) are in no county.
COUNTIES = {
    "03": "Oslo", "11": "Rogaland", "15": "Møre og Romsdal", "18": "Nordland", "31": "Østfold",
    "32": "Akershus", "33": "Buskerud", "34": "Innlandet", "39": "Vestfold", "40": "Telemark",
    "42": "Agder", "46": "Vestland", "50": "Trøndelag", "55": "Troms", "56": "Finnmark",
}

STATUS_GROUP = {
    "active": "active",
    "deleted": "closed",
    "bankruptcy": "flagged",
    "winding-up": "flagged",
    "compulsory-dissolution": "flagged",
    "not-found": "not_found",
}
# A sole proprietorship (enkeltpersonforetak) is a person trading under their own name.
NOT_LEGAL_PERSONS = {"ENK"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEIGHTS = (3, 2, 7, 6, 5, 4, 3, 2)


def org_number_valid(value):
    """A Norwegian organisation number: nine digits, the last a modulus 11 check digit."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{9}", value):
        return False
    remainder = sum(int(d) * w for d, w in zip(value[:8], WEIGHTS)) % 11
    check = 0 if remainder == 0 else 11 - remainder
    return check != 10 and check == int(value[8])


def unit_status(unit):
    """The status Tally records for a register unit: one of STATUS_GROUP's keys, with a date when known."""
    if not unit:
        return {"status": "not-found", "date": None}
    deleted = unit.get("slettedato")
    if deleted:
        return {"status": "deleted", "date": deleted if DATE.match(str(deleted)) else None}
    if unit.get("konkurs"):
        return {"status": "bankruptcy", "date": None}
    if unit.get("underTvangsavviklingEllerTvangsopplosning"):
        return {"status": "compulsory-dissolution", "date": None}
    if unit.get("underAvvikling"):
        return {"status": "winding-up", "date": None}
    return {"status": "active", "date": None}


def legal_person(unit):
    """True unless the unit is a sole proprietorship (a person, never listed in Tally)."""
    form = (unit.get("organisasjonsform") or {}).get("kode", "")
    return form not in NOT_LEGAL_PERSONS


def county_for(municipality):
    """The county for a four-digit municipality number on the 2024 structure, or ''."""
    if not isinstance(municipality, str) or not re.fullmatch(r"\d{4}", municipality):
        return ""
    return COUNTIES.get(municipality[:2], "")


_SMALL = {"i", "på", "og", "ved", "under", "over"}


def place_name(value):
    """A register place name in capitals, written as a name: 'MO I RANA' is 'Mo i Rana'."""
    words = str(value or "").strip().lower().split()
    return " ".join(w if (i and w in _SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def slim_unit(unit):
    """All Tally keeps of a unit. Contacts, street addresses and free text are never read out."""
    address = unit.get("forretningsadresse") or {}
    status = unit_status(unit)
    postcode = str(address.get("postnummer") or "")
    return {
        "brreg": str(unit.get("organisasjonsnummer", "")),
        "name": str(unit.get("navn", "")),
        "status": status["status"],
        "date": status["date"],
        "region": county_for(str(address.get("kommunenummer") or "")),
        "postcode": postcode if re.fullmatch(r"\d{4}", postcode) else "",
        "place": place_name(address.get("poststed")),
    }


def read_geonames(text):
    """GeoNames postal codes (tab separated, CC BY 4.0): postcode to (lat, lon, place). Bad rows are skipped."""
    table = {}
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) < 11 or cols[0] != "NO" or not re.fullmatch(r"\d{4}", cols[1]):
            continue
        try:
            lat, lon = float(cols[9]), float(cols[10])
        except ValueError:
            continue
        table[cols[1]] = (lat, lon, cols[2])
    return table


def point_for(postcode, table):
    """The point for a postcode, or None when unknown or outside mainland Norway."""
    row = table.get(postcode or "")
    if not row:
        return None
    lat, lon = row[0], row[1]
    w, s, e, n = NORWAY_BOUNDS
    return (lat, lon) if w <= lon <= e and s <= lat <= n else None


def check_guards(checked, closed, previous_closed):
    """Stops the run when too many lookups failed or closed companies jumped."""
    total, failed = checked.get("companies", 0), checked.get("failed", 0)
    if total and failed / total > MAX_FAILED_SHARE:
        raise SystemExit(f"{failed} of {total} lookups failed (limit {MAX_FAILED_SHARE:.0%}); not written")
    before, now = len(previous_closed), len(closed)
    if now > max(2 * before, before + 3):
        raise SystemExit(f"closed companies went from {before} to {now}; check before publishing")


def accuracy_sample(names, seed, size=SAMPLE_SIZE):
    """The companies to check by hand: `size` distinct names, the same for the same seed; all when fewer."""
    pool = sorted(set(names))
    return random.Random(str(seed)).sample(pool, min(size, len(pool)))


# =======================================================================================
# The run


def norwegian_pages():
    """(name, organisation number) for every Norwegian page that names its register entry."""
    out = []
    for path in sorted(COMPANIES.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        end = text.find("\n---", 3)
        head = text[:end] if end > 0 else ""
        if not re.search(r"^country-code:[ \t]*NO[ \t]*$", head, re.M):
            continue
        number = re.search(r"^brreg:[ \t]*[\"']?(\d{9})[\"']?[ \t]*$", head, re.M)
        name = re.search(r"^name:[ \t]*(.+)$", head, re.M)
        if number and name:
            out.append((name.group(1).strip().strip("'\""), number.group(1)))
    return out


def fetch_unit(number, attempts=3):
    """The register's answer for a number: the unit, None when unknown, or raises after retries."""
    request = urllib.request.Request(API + number, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                return None
            if attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
        time.sleep(2 * (attempt + 1))
    return None


def check_status(pages, fetch=fetch_unit, log=print):
    checked = {"companies": len(pages), "found": 0, "not_found": 0, "failed": 0}
    closed, flagged, not_found = [], [], []
    for name, number in pages:
        if not org_number_valid(number):
            checked["failed"] += 1
            log(f"  bad number for {name}")
            continue
        try:
            unit = fetch(number)
        except Exception as exc:  # noqa: BLE001 - any failure counts against the guard
            checked["failed"] += 1
            log(f"  lookup failed for {name}: {type(exc).__name__}")
            continue
        status = unit_status(unit)
        group = STATUS_GROUP[status["status"]]
        if group == "not_found":
            checked["not_found"] += 1
            not_found.append(number)
            continue
        checked["found"] += 1
        row = {"name": name, "brreg": number, "status": status["status"], "date": status["date"]}
        if group == "closed":
            closed.append(row)
        elif group == "flagged":
            flagged.append(row)
        time.sleep(PAUSE)
    return checked, closed, flagged, not_found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--previous", type=Path, help="the last published norway-register.json")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--today", type=datetime.date.fromisoformat, default=datetime.date.today())
    args = ap.parse_args(argv)
    pages = norwegian_pages()
    print(f"== Status: {len(pages)} Norwegian organisation numbers")
    checked, closed, flagged, not_found = check_status(pages)
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous and args.previous.exists() else None
    check_guards(checked, closed, previous["closed"] if previous else [])
    doc = {
        "generated": args.today.isoformat(), "attribution": ATTRIBUTION, "source": SOURCE,
        "checked": checked, "closed": closed, "flagged": flagged, "not_found": not_found,
    }
    args.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"closed {len(closed)}, flagged {len(flagged)}, not found {len(not_found)}, failed {checked['failed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
