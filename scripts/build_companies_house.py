#!/usr/bin/env python3
"""Build companies-house.json: closed Tally companies, and defence companies formed and dissolved.

Reads the Companies House Public Data API (Open Government Licence v3.0) with the key in the
environment variable COMPANIES_HOUSE_API_KEY. Standard library only.

    python3 scripts/build_companies_house.py --previous companies-house.json

Two parts, one run:

1. Status. Every Tally company with a Companies House number is looked up. A company that is
   dissolved, converted-closed, removed or closed goes in `closed`; one in an insolvency process,
   or with a proposal to strike off, goes in `flagged`; a number Companies House does not know
   goes in `not_found` (the number may be wrong in Tally, so it is not treated as closed).
2. Trend. For three defence activity codes, the companies formed and dissolved in each calendar
   year from 2010, per code and in total (one search across the codes, so a company with two of
   them counts once).

Officers, addresses and every other field are never read into the output. Rules and caveats:
docs/companies-house-data.md.
"""

import argparse
import base64
import datetime
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TALLY = ROOT / "tally-data.json"
COMPANIES = ROOT / "Companies"
OUT = ROOT / "companies-house.json"
API = "https://api.company-information.service.gov.uk"
ATTRIBUTION = "Contains public sector information licensed under the Open Government Licence v3.0."
SOURCE = "Companies House Public Data API"
# The API allows 600 requests per 5 minutes: one every 0.5 s. Stay a little under.
PAUSE = 0.6

CODES = {
    "25400": "Manufacture of weapons and ammunition",
    "30400": "Manufacture of military fighting vehicles",
    "84220": "Defence activities",
}
FIRST_YEAR = 2010
CLOSED = {"dissolved", "converted-closed", "removed", "closed"}
FLAGGED = {"liquidation", "administration", "receivership", "insolvency-proceedings", "voluntary-arrangement"}
STRIKE_OFF = "active-proposal-to-strike-off"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_FAILED_SHARE = 0.02


# =======================================================================================
# Rules (tested in tests/acceptance/test_companies_house.py)
# =======================================================================================

def sort_profile(profile):
    """("closed" | "flagged" | "active" | "not_found", record) for a company profile or None."""
    if profile is None:
        return "not_found", {}
    status = str(profile.get("company_status") or "").strip().lower()
    detail = str(profile.get("company_status_detail") or "").strip().lower()
    rec = {"status": status}
    if status in CLOSED:
        date = profile.get("date_of_cessation")
        if isinstance(date, str) and DATE.match(date):
            rec["date"] = date
        return "closed", rec
    if status in FLAGGED:
        if detail:
            rec["detail"] = detail
        return "flagged", rec
    if detail == STRIKE_OFF:
        rec["detail"] = detail
        return "flagged", rec
    return "active", rec


def check_total(total, per_code):
    """A total across the codes lies between the largest code and their sum."""
    values = list(per_code.values())
    if not (max(values) <= total <= sum(values)):
        raise SystemExit(f"trend total {total} is outside {max(values)} to {sum(values)} ({per_code}); not written")


def trend_years(today):
    """[(year, partial)] from FIRST_YEAR to this year; this year is partial."""
    return [(y, y == today.year) for y in range(FIRST_YEAR, today.year + 1)]


def year_range(year, today):
    """The search range for a year; this year runs to yesterday, the last complete day."""
    end = datetime.date(year, 12, 31)
    if year == today.year:
        end = today - datetime.timedelta(days=1)
    return f"{year}-01-01", end.isoformat()


def check_failures(failed, total):
    if total and failed / total > MAX_FAILED_SHARE:
        raise SystemExit(f"{failed} of {total} lookups failed (limit {MAX_FAILED_SHARE:.0%}); not written")


def check_closed_jump(previous, now):
    """Closed companies more than doubling since the last file points to a fault, not closures."""
    if previous and now > 2 * previous:
        raise SystemExit(f"closed companies went from {previous} to {now}; check before publishing")


def norm_ch(value):
    """A Companies House number as 8 characters (numbers zero-padded), or None."""
    v = re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()
    if not v:
        return None
    if v.isdigit():
        v = v.zfill(8)
    if not re.fullmatch(r"([0-9]{8}|[A-Z]{2}[0-9]{6})", v):
        return None
    return v


# =======================================================================================
# Reading Tally and the API
# =======================================================================================

def tally_numbers():
    """{number: [Tally names]} for every Tally company page that carries a number."""
    names = {c["name"] for c in json.loads(TALLY.read_text(encoding="utf-8"))["companies"]}
    out = {}
    for p in sorted(COMPANIES.rglob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            continue
        fm = text.split("---", 2)[1]
        m_name = re.search(r'^name:\s*"?(.+?)"?\s*$', fm, re.M)
        m_ch = re.search(r'^companies-house:\s*"?([A-Za-z0-9 ]+?)"?\s*$', fm, re.M)
        if not (m_name and m_ch):
            continue
        name, ch = m_name.group(1).strip(), norm_ch(m_ch.group(1))
        if ch and name in names:
            out.setdefault(ch, [])
            if name not in out[ch]:
                out[ch].append(name)
    return out


class Client:
    def __init__(self, key, log=print):
        self.auth = "Basic " + base64.b64encode((key + ":").encode()).decode()
        self.last = 0.0
        self.requests = 0
        self.log = log

    def get(self, path, tries=6):
        """The JSON document, or None for 404. Raises after repeated failures."""
        for attempt in range(tries):
            wait = PAUSE - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.requests += 1
            req = urllib.request.Request(API + path, headers={
                "Authorization": self.auth, "Accept": "application/json",
                "User-Agent": "tally-data-build"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                    self.log(f"    HTTP {e.code}, waiting")
                    time.sleep(min(300, 10 * 2 ** attempt))
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError,
                    http.client.HTTPException, json.JSONDecodeError):
                if attempt < tries - 1:
                    time.sleep(min(120, 5 * 2 ** attempt))
                    continue
                raise
        raise RuntimeError("no response")


def check_status(client, numbers, log):
    closed, flagged, not_found = [], [], []
    found = failed = 0
    for i, (ch, names) in enumerate(sorted(numbers.items()), 1):
        try:
            profile = client.get(f"/company/{ch}")
        except Exception as e:  # noqa: BLE001 - one failed lookup must not stop the run
            failed += 1
            log(f"  {ch}: lookup failed ({type(e).__name__})")
            continue
        kind, rec = sort_profile(profile)
        if kind != "not_found":
            found += 1
        rows = [{"name": n, "ch": ch, **rec} for n in names]
        {"closed": closed, "flagged": flagged, "not_found": not_found}.get(kind, []).extend(rows)
        if i % 200 == 0:
            log(f"  {i} of {len(numbers)} looked up")
    check_failures(failed, len(numbers))
    key = lambda r: (r["name"].lower(), r["ch"])  # noqa: E731
    checked = {"companies": len(numbers), "found": found, "not_found": len(not_found), "failed": failed}
    return checked, sorted(closed, key=key), sorted(flagged, key=key), sorted(not_found, key=key)


def hits(client, codes, field, start, end):
    q = urllib.parse.urlencode({"sic_codes": ",".join(codes), f"{field}_from": start, f"{field}_to": end, "size": 1})
    doc = client.get(f"/advanced-search/companies?{q}")
    return int(doc.get("hits") or 0) if doc else 0


def build_trend(client, today, log):
    years = []
    for year, partial in trend_years(today):
        start, end = year_range(year, today)
        row = {"year": year, "partial": partial}
        for kind, field in (("formed", "incorporated"), ("dissolved", "dissolved")):
            per = {c: hits(client, [c], field, start, end) for c in CODES}
            total = hits(client, list(CODES), field, start, end)
            check_total(total, per)
            row[kind] = {"total": total, **per}
        log(f"  {year}: formed {row['formed']['total']}, dissolved {row['dissolved']['total']}")
        years.append(row)
    return {"codes": CODES, "years": years}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--previous", type=Path, help="the last published companies-house.json")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--today", type=datetime.date.fromisoformat, default=datetime.date.today())
    args = ap.parse_args(argv)
    key = os.environ.get("COMPANIES_HOUSE_API_KEY", "").strip()
    if not key:
        raise SystemExit("COMPANIES_HOUSE_API_KEY is not set")
    client = Client(key)
    numbers = tally_numbers()
    print(f"== Status: {len(numbers)} Companies House numbers")
    checked, closed, flagged, not_found = check_status(client, numbers, print)
    previous = None
    if args.previous and args.previous.exists():
        previous = len(json.loads(args.previous.read_text(encoding="utf-8")).get("closed", []))
    check_closed_jump(previous, len(closed))
    print(f"== Trend: {', '.join(CODES)}")
    trend = build_trend(client, args.today, print)
    doc = {
        "generated": args.today.isoformat(), "attribution": ATTRIBUTION, "source": SOURCE,
        "checked": checked, "closed": closed, "flagged": flagged, "not_found": not_found, "trend": trend,
    }
    args.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"closed {len(closed)}, flagged {len(flagged)}, not found {len(not_found)}, failed {checked['failed']}")
    print(f"wrote {args.out.name} ({client.requests} requests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
