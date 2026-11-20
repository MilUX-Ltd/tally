#!/usr/bin/env python3
"""Build money.json: where UK defence contract money goes, from public award notices.

Two stages, standard library only (Python 3.9 or later):

    python3 scripts/build_money.py fetch --cache <folder>   # download award notices
    python3 scripts/build_money.py build --cache <folder>   # write money.json
    python3 scripts/build_money.py all   --cache <folder>   # both

The cache folder holds the raw downloads. Keep it outside the repository: raw downloads are
never committed. A rerun reads pages already in the cache and does not fetch them again.

Sources (both free, no key, Open Government Licence v3.0):
  Contracts Finder OCDS search  https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search
  Find a Tender OCDS releases   https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages
  postcodes.io                  https://api.postcodes.io (postcode to region)

Rules (see docs/money-data.md):

1. Defence buyers only. A notice counts when its buyer name matches the allowlist below
   (case-insensitive). Everything else is left out. The build prints the distinct buyer names
   it included and the near misses it excluded, so the list can be checked.
2. Period: awards dated 1 January 2023 to the build date, by award date. Years are calendar
   years.
3. Value: GBP award values only, in whole pounds. Non-GBP awards are counted separately and
   left out of totals. Framework agreements and dynamic purchasing systems carry ceilings,
   not spend: their award notices are left out of totals and counted separately. Call-offs
   from a framework or DPS are real spend and are counted. An award shared by several
   suppliers is split equally between them.
4. Place: a UK supplier is placed in one of the 12 Tally regions by its postcode
   (postcodes.io: `region` in England, `country` elsewhere; outcode lookup as a fallback).
   A supplier whose address gives a country other than the UK is overseas, by country.
   Anything else is unplaced.
5. Tally match: by Companies House number where the notice gives one (scheme GB-COH),
   else by normalised name (lower case, punctuation stripped, legal and group suffixes
   stripped). Missing a match is preferred to a wrong one: a normalised name that maps to
   more than one Tally company is not used.
6. No personal data. A supplier is named only when it is clearly a registered organisation
   (a Companies House number, a legal-form suffix, or a university or public body).
   Otherwise it counts in totals and is never named.
"""

import argparse
import datetime
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "money.json"
TALLY = ROOT / "tally-data.json"
COMPANIES = ROOT / "Companies"

START = datetime.date(2023, 1, 1)
ATTRIBUTION = "Contains public sector information licensed under the Open Government Licence v3.0."
USER_AGENT = "tally-money-build/1.0 (+https://tally.milux.co.uk)"
PAUSE = 2.2  # seconds between requests: Contracts Finder allows about 30 a minute

CF_SEARCH = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"
FTS_SEARCH = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
POSTCODES = "https://api.postcodes.io"

# ---------------------------------------------------------------------------------------
# Rule 1: the defence buyer allowlist, matched on buyer name, case-insensitive.
# Each entry is a regular expression searched for in the buyer name.
#   Ministry of Defence / MOD          Defence Equipment and Support (DE&S)
#   Defence Infrastructure Organisation Submarine Delivery Agency
#   Defence Science and Technology Laboratory (Dstl)   Defence Digital
#   Defence and Security Accelerator (DASA) / UK Defence Innovation
#   UK Hydrographic Office             Royal Navy, British Army, Royal Air Force
#   Atomic Weapons Establishment (AWE) Defence Nuclear Organisation
#   Defence Electronics and Components Agency (DECA)   Single Source Regulations Office
# ---------------------------------------------------------------------------------------
ALLOWLIST = [
    r"\bministry of defen[cs]e\b",
    r"^\s*mod\b",
    r"\bmod\s*(uk|-|–|:|\()",
    r"\(mod\)",
    r"\bdefen[cs]e equipment (and|&) support\b",
    r"\bde\s*&\s*s\b",
    r"\bdefen[cs]e infrastructure organi[sz]ation\b",
    r"\bsubmarine delivery agency\b",
    r"\bdefen[cs]e science (and|&) technology lab",
    r"\bdstl\b",
    r"\bdefen[cs]e digital\b",
    r"\bdefen[cs]e (and|&) security accelerator\b",
    r"\buk defen[cs]e innovation\b",
    r"\bhydrographic office\b",
    r"\bukho\b",
    r"\broyal navy\b",
    r"\bbritish army\b",
    r"\broyal air force\b",
    r"\batomic weapons establishment\b",
    r"\bawe\b",
    r"\bdefen[cs]e nuclear organi[sz]ation\b",
    r"\bdefen[cs]e electronics (and|&) components agency\b",
    r"\bsingle source regulations office\b",
]
ALLOW_RE = re.compile("|".join(ALLOWLIST), re.I)

# Buyer names that look military but are not in the allowlist are kept in the cache and
# reported as near misses, so the allowlist can be judged. This wider net decides only what
# is cached, never what is counted.
NEAR_RE = re.compile(
    r"defen[cs]e|\bmod\b|navy|naval|army|air force|\braf\b|military|hydrographic|dstl|"
    r"weapons|nuclear|submarine|armed forces|\bdasa\b|single source|royal marines|veteran|"
    r"\bawe\b|cadet",
    re.I,
)

# ---------------------------------------------------------------------------------------
# Rule 3: framework agreements and dynamic purchasing systems (ceilings, not spend).
# A notice is a framework or DPS award when the OCDS techniques flags say so, or when its
# procurement method text names a framework or DPS and is not a call-off from one.
# ---------------------------------------------------------------------------------------
FRAMEWORK_TEXT = re.compile(r"framework|dynamic purchasing|\bdps\b", re.I)
CALL_OFF_TEXT = re.compile(
    r"call[- ]?off|mini[- ]?competition|further competition|direct award|"
    r"(under|from|based on|through|via) (a |an |the )?(existing )?(framework|dynamic purchasing|dps)",
    re.I,
)

# ---------------------------------------------------------------------------------------
# Rule 4: the 12 Tally regions. postcodes.io gives `region` for England and `country`
# for Scotland, Wales and Northern Ireland.
# ---------------------------------------------------------------------------------------
REGIONS = [
    "North East", "North West", "Yorkshire and The Humber", "East Midlands", "West Midlands",
    "East of England", "London", "South East", "South West", "Scotland", "Wales",
    "Northern Ireland",
]
UK_NAMES = {
    "uk", "united kingdom", "great britain", "gb", "england", "scotland", "wales",
    "northern ireland", "united kingdom of great britain and northern ireland", "britain",
}
# NUTS 1 and ITL 1 codes that Find a Tender gives in an address `region`, as a fallback when
# there is no usable postcode.
NUTS = {
    "UKC": "North East", "UKD": "North West", "UKE": "Yorkshire and The Humber",
    "UKF": "East Midlands", "UKG": "West Midlands", "UKH": "East of England", "UKI": "London",
    "UKJ": "South East", "UKK": "South West", "UKL": "Wales", "UKM": "Scotland",
    "UKN": "Northern Ireland",
}
NUTS.update({"TL" + k[2]: v for k, v in list(NUTS.items())})
PLACE_REGION = {r.lower(): r for r in REGIONS}
PLACE_REGION["eastern"] = "East of England"
# Countries recognised at the end of a free-text address that gives no country field.
COUNTRIES = [
    "United States", "United States of America", "USA", "Canada", "Mexico", "Brazil",
    "Australia", "New Zealand", "Japan", "South Korea", "Republic of Korea", "Korea",
    "Singapore", "India", "Israel", "United Arab Emirates", "UAE", "Saudi Arabia", "Qatar",
    "Turkey", "Türkiye", "Ireland", "Republic of Ireland", "France", "Germany", "Deutschland",
    "Netherlands", "The Netherlands", "Belgium", "Luxembourg", "Switzerland", "Austria",
    "Italy", "Spain", "Portugal", "Greece", "Cyprus", "Malta", "Denmark", "Norway", "Sweden",
    "Finland", "Iceland", "Estonia", "Latvia", "Lithuania", "Poland", "Czech Republic",
    "Czechia", "Slovakia", "Hungary", "Romania", "Bulgaria", "Croatia", "Slovenia", "Serbia",
    "Ukraine", "South Africa", "Kenya", "Nigeria", "Egypt", "Oman", "Bahrain", "Kuwait",
    "Jordan", "Malaysia", "Thailand", "Indonesia", "Philippines", "Vietnam", "China",
    "Hong Kong", "Taiwan", "Chile", "Argentina", "Colombia", "Falkland Islands", "Gibraltar",
    "Jersey", "Guernsey", "Isle of Man",
]
COUNTRY_TAIL = re.compile(r"(?:^|[\s,])(" + "|".join(re.escape(c) for c in
                          sorted(COUNTRIES, key=len, reverse=True)) + r")[\s.,]*$", re.I)
POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}[0-9][A-Z0-9]?)\s*([0-9][A-Z]{2})\b")
OUTCODE_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]?$")

# ---------------------------------------------------------------------------------------
# Rule 5: name normalisation for matching to Tally.
# ---------------------------------------------------------------------------------------
NAME_SUFFIXES = {
    "ltd", "limited", "plc", "llp", "uk", "group", "holdings", "holding", "the",
    "co", "company", "inc", "llc",
}

# ---------------------------------------------------------------------------------------
# Rule 6: a supplier is named only when clearly a registered organisation.
# ---------------------------------------------------------------------------------------
LEGAL_FORM = re.compile(
    r"\b(ltd|limited|plc|p\.l\.c|llp|llc|l\.l\.c|inc|incorporated|corp|corporation|gmbh|"
    r"s\.?a|b\.?v|n\.?v|a\.?g|ab|a/?s|asa|oy|oyj|s\.?p\.?a|s\.?r\.?l|s\.?a\.?s|s\.?l|"
    r"pty|pte|kg|se|cic|lp|ulc|sarl|aps|bvba|kft|sp\.? z o\.?o|co\.?,? ltd)\.?\s*\)?$",
    re.I,
)
PUBLIC_BODY = re.compile(
    r"\b(university|college|council|nhs|trust|agency|authority|ministry|department|"
    r"office|institute|police|fire and rescue|government|commission|laboratory|"
    r"school|academy|research council|uk research)\b",
    re.I,
)


# =======================================================================================
# Fetching
# =======================================================================================

class Fetcher:
    """Polite, cached GET and POST. Sequential, paced, backs off on 429 and 5xx."""

    def __init__(self, cache, max_requests, log=print):
        self.log = log
        self.throttled = 0
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.requests = 0
        self.max_requests = max_requests
        self.last = {}
        self.pause = {}

    def _path(self, kind, key):
        return self.cache / kind / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")

    def cached(self, kind, key):
        p = self._path(kind, key)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def store(self, kind, key, doc):
        p = self._path(kind, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        tmp.replace(p)

    def request(self, url, body=None, timeout=120, tries=8):
        for attempt in range(tries):
            if self.requests >= self.max_requests:
                raise RuntimeError("request budget reached")
            host = urllib.parse.urlsplit(url).netloc
            pause = 0.3 if host == "api.postcodes.io" else self.pause.get(host, PAUSE)
            wait = pause - (time.time() - self.last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            self.last[host] = time.time()
            self.requests += 1
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(url, data=data, headers={
                "User-Agent": USER_AGENT, "Accept": "application/json",
                **({"Content-Type": "application/json"} if data else {}),
            })
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                    retry = e.headers.get("Retry-After") if e.headers else None
                    wait = int(retry) if retry and retry.isdigit() else 5 * 2 ** attempt
                    if e.code == 429:
                        # Slow down for the rest of the run: the services rate-limit by IP.
                        self.throttled += 1
                        self.pause[host] = min(30.0, self.pause.get(host, PAUSE) * 1.25)
                        self.log(f"    rate limited; pause now {self.pause[host]:.1f} s")
                    self.log(f"    HTTP {e.code}, waiting {min(300, wait)} s")
                    time.sleep(min(300, wait) + 1)
                    continue
                if e.code == 404:
                    return None
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt < tries - 1:
                    time.sleep(min(120, 5 * 2 ** attempt))
                    continue
                raise
        return None


def slim_page(doc):
    """Keep what the build needs from one page: the next link, the count, the buyer-name
    tally, and the releases whose buyer passes the wider near-miss net."""
    releases = doc.get("releases") or []
    buyers = Counter()
    kept = []
    for r in releases:
        name = buyer_name(r)
        buyers[name] += 1
        if NEAR_RE.search(name or ""):
            kept.append(r)
    return {
        "next": (doc.get("links") or {}).get("next"),
        "n": len(releases),
        "buyers": {k: v for k, v in buyers.items() if NEAR_RE.search(k or "")},
        "releases": kept,
    }


CF_PAGE_CAP = 5  # Contracts Finder stops a cursor chain after 5 pages (500 notices)


def day_windows(start, end):
    """One window per weekday, one per weekend, most recent first."""
    out = []
    d = start
    while d <= end:
        if d.weekday() == 5:  # Saturday: take Saturday and Sunday together
            nxt = min(d + datetime.timedelta(days=2), end + datetime.timedelta(days=1))
        else:
            nxt = d + datetime.timedelta(days=1)
        out.append((datetime.datetime.combine(d, datetime.time()),
                    datetime.datetime.combine(nxt, datetime.time())))
        d = nxt
    return out[::-1]


def week_windows(start, end):
    """Seven-day windows, most recent first (Find a Tender has no page cap)."""
    out = []
    d = start
    while d <= end:
        nxt = min(d + datetime.timedelta(days=7), end + datetime.timedelta(days=1))
        out.append((datetime.datetime.combine(d, datetime.time()),
                    datetime.datetime.combine(nxt, datetime.time())))
        d = nxt
    return out[::-1]


def walk(f, kind, url, timeout):
    """Follow one cursor chain. Returns (pages, notices, capped) or None on no response."""
    pages = notices = 0
    last = None
    seen = set()
    while url and url not in seen:
        seen.add(url)
        page = f.cached(kind, url)
        if page is None:
            raw = f.request(url, timeout=timeout)
            if raw is None:
                return None
            page = slim_page(raw)
            f.store(kind, url, page)
        pages += 1
        notices += page["n"]
        last = page
        url = page["next"]
    capped = pages >= CF_PAGE_CAP and last is not None and last["n"] >= 100 and not last["next"]
    return pages, notices, capped


def fetch_windows(f, kind, url_for, windows, log, timeout=120):
    """Fetch every window, halving any window whose cursor chain hits the page cap.
    Pages from a capped window stay in the cache; the build removes duplicates by
    release id, so they do no harm."""
    totals = {"windows": 0, "pages": 0, "notices": 0, "split": 0, "failed": []}
    stack = list(windows)[::-1]
    done = 0
    while stack:
        a, b = stack.pop()
        res = walk(f, kind, url_for(a, b), timeout)
        if res is None:
            totals["failed"].append([a.isoformat(), b.isoformat()])
            continue
        pages, notices, capped = res
        if capped and (b - a) > datetime.timedelta(minutes=30):
            mid = a + (b - a) / 2
            mid = mid.replace(second=0, microsecond=0)
            stack.extend([(mid, b), (a, mid)][::-1])
            totals["split"] += 1
            continue
        totals["windows"] += 1
        totals["pages"] += pages
        totals["notices"] += notices
        done += 1
        if done % 50 == 0:
            log(f"  {kind} reached {a.date()}: {totals['notices']} notices, requests {f.requests}")
    return totals


def cf_url(a, b):
    q = {"publishedFrom": a.strftime("%Y-%m-%dT%H:%M:%S"),
         "publishedTo": b.strftime("%Y-%m-%dT%H:%M:%S"), "stages": "award", "limit": "100"}
    return CF_SEARCH + "?" + urllib.parse.urlencode(q)


def fts_url(a, b):
    q = {"stages": "award", "updatedFrom": a.strftime("%Y-%m-%dT%H:%M:%S"),
         "updatedTo": b.strftime("%Y-%m-%dT%H:%M:%S"), "limit": "100"}
    return FTS_SEARCH + "?" + urllib.parse.urlencode(q)


def cached_complete(f, kind, a, b):
    """True when the window's cursor chain is complete in the cache, splitting capped
    windows the same way the fetch does. No network."""
    url = url_for_kind(kind)(a, b)
    pages, last, seen = 0, None, set()
    while url and url not in seen:
        seen.add(url)
        page = f.cached(kind, url)
        if page is None:
            return False
        pages += 1
        last = page
        url = page["next"]
    capped = pages >= CF_PAGE_CAP and last["n"] >= 100 and not last["next"]
    if capped and (b - a) > datetime.timedelta(minutes=30):
        mid = (a + (b - a) / 2).replace(second=0, microsecond=0)
        return cached_complete(f, kind, a, mid) and cached_complete(f, kind, mid, b)
    return True


def url_for_kind(kind):
    return cf_url if kind == "cf" else fts_url


def coverage(f, kind, windows):
    """The earliest date from which every window up to today is complete in the cache,
    or None when even the latest window is missing. Windows are most recent first."""
    start = None
    for a, b in windows:
        if not cached_complete(f, kind, a, b):
            break
        start = a.date()
    return start


def fetch(args, log):
    f = Fetcher(args.cache, args.max_requests, log)
    status = {}

    windows = day_windows(args.since, args.today)
    try:
        if not args.skip_cf:
            log("Contracts Finder")
            status["cf"] = fetch_windows(f, "cf", cf_url, windows, log)
        if not args.skip_fts:
            log("Find a Tender")
            fts_windows = week_windows(max(args.since, args.fts_since), args.today)
            status["fts"] = fetch_windows(f, "fts", fts_url, fts_windows, log, timeout=300)
    except RuntimeError as e:  # request budget reached: keep what was fetched
        log(f"stopped: {e}")
        status["stopped"] = str(e)
    status.update({"since": args.since.isoformat(), "today": args.today.isoformat(),
                   "requests": f.requests, "throttled": f.throttled})
    (Path(args.cache) / f"fetch-status-{int(time.time())}.json").write_text(
        json.dumps(status, indent=1), encoding="utf-8")
    log(json.dumps(status))


# =======================================================================================
# Reading releases
# =======================================================================================

def buyer_name(r):
    b = (r.get("buyer") or {}).get("name")
    if b:
        return b.strip()
    for p in r.get("parties") or []:
        if "buyer" in (p.get("roles") or []):
            return (p.get("name") or "").strip()
    return ""


def norm_space(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def norm_name(name):
    """Rule 5: lower case, '&' to 'and', punctuation stripped, legal and group suffixes
    stripped from the end (repeatedly), and a leading 'the' dropped."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ")
    s = re.sub(r"\(uk\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = s.split()
    while words and words[-1] in NAME_SUFFIXES:
        words.pop()
    while words and words[0] == "the":
        words.pop(0)
    return " ".join(words)


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


def find_postcode(*texts):
    for t in texts:
        m = POSTCODE_RE.search((t or "").upper())
        if m:
            return f"{m.group(1)} {m.group(2)}"
    return None


def is_uk(country):
    return norm_space(country).lower().strip(". ") in UK_NAMES


def country_label(country):
    c = norm_space(country).strip(". ")
    fixes = {"usa": "United States", "us": "United States", "united states of america":
             "United States", "the netherlands": "Netherlands", "holland": "Netherlands",
             "republic of korea": "South Korea", "korea, republic of": "South Korea",
             "deutschland": "Germany", "uae": "United Arab Emirates",
             "the netherlands": "Netherlands", "republic of ireland": "Ireland",
             "korea": "South Korea", "czechia": "Czech Republic", "türkiye": "Turkey"}
    low = c.lower()
    if low in fixes:
        return fixes[low]
    return c.title() if c.isupper() or c.islower() else c


def nameable(name, ch):
    """Rule 6."""
    if ch:
        return True
    n = norm_space(name)
    return bool(LEGAL_FORM.search(n) or PUBLIC_BODY.search(n))


def is_framework(release, award=None):
    """Rule 3. A framework agreement or DPS award notice. A notice that says it is a call-off
    or an award made under a framework or DPS is real spend and is never one. Otherwise it
    is one when the OCDS techniques flags say so (on the tender or a lot), when the
    procurement method or the tender title names a framework or DPS, or when a single award
    names three or more suppliers (a shared ceiling, not an order)."""
    t = release.get("tender") or {}
    details = " ".join(str(x or "") for x in (
        t.get("procurementMethodDetails"), t.get("procurementMethodRationale")))
    if CALL_OFF_TEXT.search(details):
        return False
    for tech in [t.get("techniques") or {}] + [(l.get("techniques") or {}) for l in t.get("lots") or []]:
        if tech.get("hasFrameworkAgreement") or tech.get("hasDynamicPurchasingSystem"):
            return True
    if FRAMEWORK_TEXT.search(str(t.get("procurementMethodDetails") or "")) or \
            FRAMEWORK_TEXT.search(t.get("title") or ""):
        return True
    if award is not None and len(award.get("suppliers") or []) >= 3:
        return True
    return False


def notice_url(release, award, source):
    for d in (award.get("documents") or []) + ((release.get("tender") or {}).get("documents") or []):
        u = d.get("url") or ""
        if d.get("documentType") in ("awardNotice", "contractNotice") and u.startswith("https://"):
            return u
    if source == "cf":
        m = re.match(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", release.get("id", ""))
        if m:
            return f"https://www.contractsfinder.service.gov.uk/Notice/{m.group(1)}"
    else:
        rid = release.get("id", "")
        m = re.match(r"([0-9]{6}-[0-9]{4})", rid)
        if m:
            return f"https://www.find-tender.service.gov.uk/Notice/{m.group(1)}"
    return None


def supplier_record(party):
    ident = party.get("identifier") or {}
    ch = None
    for i in [ident] + list(party.get("additionalIdentifiers") or []):
        if (i.get("scheme") or "").upper() == "GB-COH":
            ch = norm_ch(i.get("id"))
            if ch:
                break
    pid = party.get("id") or ""
    if not ch and pid.upper().startswith("GB-COH-"):
        ch = norm_ch(pid[7:])
    addr = party.get("address") or {}
    name = norm_space(party.get("name") or ident.get("legalName"))
    street = (addr.get("streetAddress") or "").replace("\u202f", " ").strip()
    country = norm_space(addr.get("countryName"))
    pc = find_postcode(addr.get("postalCode"), street, addr.get("locality"), addr.get("region"))
    if not country and not pc:
        m = COUNTRY_TAIL.search(street)
        if m:
            country = m.group(1)
    locality = norm_space(addr.get("locality"))
    if not locality and street:
        # Contracts Finder gives one free-text line; its last part is usually the town.
        locality = norm_space(re.split(r"[,\n\r]+", street.strip(" ,"))[-1])
    return {
        "name": name,
        "ch": ch,
        "postcode": pc,
        "country": country,
        "nuts": NUTS.get(norm_space(addr.get("region")).upper()[:3]),
        "locality": locality,
        "scale": supplier_scale(party),
    }


def supplier_scale(party):
    """The size the supplier declared on the notice: "sme", "large", or None."""
    scale = norm_space(str((party.get("details") or {}).get("scale") or "")).lower()
    return scale if scale in ("sme", "large") else None


def fill_scale(rows):
    """Fill a missing size from the same supplier's other notices, matched by Companies
    House number or normalised name. A supplier that declared both sizes fills nothing."""
    seen = defaultdict(set)
    keys = lambda r: [k for k in (("ch", r.get("ch")), ("name", norm_name(r.get("name") or ""))) if k[1]]
    for r in rows:
        if r.get("scale"):
            for k in keys(r):
                seen[k].add(r["scale"])
    for r in rows:
        if r.get("scale"):
            continue
        found = set().union(*[seen[k] for k in keys(r)]) if keys(r) else set()
        if len(found) == 1:
            r["scale"] = next(iter(found))
            r["scale_filled"] = True


def load_releases(cache):
    """Every cached release, newest version per (source, ocid)."""
    best = {}
    for source in ("cf", "fts"):
        folder = Path(cache) / source
        if not folder.exists():
            continue
        for p in sorted(folder.glob("*.json")):
            for r in json.loads(p.read_text(encoding="utf-8")).get("releases") or []:
                key = (source, r.get("ocid") or r.get("id"))
                if key not in best or (r.get("date") or "") > (best[key][1].get("date") or ""):
                    best[key] = (source, r)
    return list(best.values())


def award_date(award, release):
    for v in (award.get("date"), (award.get("contractPeriod") or {}).get("startDate"),
              award.get("datePublished"), release.get("date")):
        if v:
            try:
                return datetime.date.fromisoformat(str(v)[:10])
            except ValueError:
                continue
    return None


def extract(cache, today, log, period_from=START):
    """Return (rows, report). One row per supplier share of a counted award."""
    rows = []
    rep = {
        "buyers_in": Counter(), "buyers_near": Counter(), "frameworks": 0, "non_gbp": 0,
        "non_gbp_currencies": Counter(), "no_value": 0, "out_of_period": 0, "dup_cross": 0,
        "inactive": 0, "no_supplier": 0, "shared": 0, "releases": Counter(), "before_period": 0,
        "dup_pairs": [],
        "framework_titles": [],
    }
    releases = load_releases(cache)
    seen_ocids = {}
    for source, r in releases:
        rep["releases"][source] += 1
        b = buyer_name(r)
        if not ALLOW_RE.search(b):
            if NEAR_RE.search(b):
                rep["buyers_near"][b] += 1
            continue
        rep["buyers_in"][b] += 1
        parties = {p.get("id"): p for p in r.get("parties") or []}
        contracts = defaultdict(list)
        for c in r.get("contracts") or []:
            contracts[c.get("awardID")].append(c)
        title = norm_space((r.get("tender") or {}).get("title"))
        for a in r.get("awards") or []:
            if (a.get("status") or "active") in ("cancelled", "unsuccessful"):
                rep["inactive"] += 1
                continue
            framework = is_framework(r, a)
            cs = contracts.get(a.get("id")) or []
            if not (a.get("value") or {}).get("amount") and cs:
                # Find a Tender gives the value and signature date on the contract.
                amounts = [c.get("value") or {} for c in cs if (c.get("value") or {}).get("amount") is not None]
                if amounts:
                    a = dict(a, value={"amount": sum(float(v["amount"]) for v in amounts),
                                       "currency": amounts[0].get("currency") or "GBP"})
                if not a.get("date"):
                    signed = sorted(c.get("dateSigned") for c in cs if c.get("dateSigned"))
                    if signed:
                        a = dict(a, date=signed[0])
            d = award_date(a, r)
            if d is None or d < START or d > today:
                rep["out_of_period"] += 1
                continue
            if d < period_from:
                rep["before_period"] += 1
                continue
            if framework:
                rep["frameworks"] += 1
                rep["framework_titles"].append(f"{d} {b[:30]} | {title[:90]}")
                continue
            val = a.get("value") or {}
            cur = (val.get("currency") or "GBP").upper()
            amount = val.get("amount")
            if cur != "GBP":
                rep["non_gbp"] += 1
                rep["non_gbp_currencies"][cur] += 1
                continue
            if amount is None:
                rep["no_value"] += 1
                amount = 0
            sups = []
            for s in a.get("suppliers") or []:
                p = parties.get(s.get("id")) or {"name": s.get("name"), "id": s.get("id")}
                sups.append(supplier_record(p))
            if not sups:
                rep["no_supplier"] += 1
                continue
            if len(sups) > 1:
                rep["shared"] += 1
            share = float(amount) / len(sups)
            for sup in sups:
                rows.append({
                    "source": source, "ocid": r.get("ocid"), "award": a.get("id"),
                    "date": d.isoformat(), "value": share, "buyer": b,
                    "title": norm_space(a.get("title")) or title,
                    "url": notice_url(r, a, source), **sup,
                })
    # Cross-source duplicates: same ocid, or same supplier, value and award date.
    keyed = {}
    out = []
    # Find a Tender first: for an above-threshold award it is the notice of record. The same
    # supplier within three days of the same award date in both services is one award, even when the two
    # notices give different values; the Find a Tender value is kept.
    for row in sorted(rows, key=lambda x: x["source"] != "fts"):
        k1 = ("ocid", row["ocid"], norm_name(row["name"]))
        day = datetime.date.fromisoformat(row["date"])
        near = [("sd", norm_name(row["name"]), (day + datetime.timedelta(days=o)).isoformat())
                for o in (0, -1, 1, -2, 2, -3, 3)]
        k2 = near[0]
        hit = keyed.get(k1) or next((keyed[k] for k in near if k in keyed), None)
        if hit and hit[0] != row["source"]:
            rep["dup_cross"] += 1
            rep["dup_pairs"].append(f"{row['date']} {row['name'][:40]}: kept {hit[0]} "
                                    f"{gbp(hit[1])}, dropped {row['source']} {gbp(row['value'])}")
            continue
        keyed.setdefault(k1, (row["source"], row["value"]))
        keyed.setdefault(k2, (row["source"], row["value"]))
        out.append(row)
    return out, rep


# =======================================================================================
# Places
# =======================================================================================

def lookup_postcodes(f, postcodes, log):
    """postcode -> region (one of REGIONS) or None. Cached in the fetch cache."""
    result = {}
    todo = []
    for pc in sorted(set(postcodes)):
        c = f.cached("postcodes", pc)
        if c is not None:
            result[pc] = c.get("region")
        else:
            todo.append(pc)

    def region_of(res):
        if not res:
            return None
        if res.get("country") == "England":
            return res.get("region")
        return res.get("country") if res.get("country") in REGIONS else None

    def reverse(lat, lon):
        q = urllib.parse.urlencode({"lon": lon, "lat": lat, "limit": 1, "radius": 2000})
        doc = f.request(f"{POSTCODES}/postcodes?{q}", timeout=60)
        res = (doc or {}).get("result") or []
        return region_of(res[0]) if res else None

    for i in range(0, len(todo), 100):
        batch = todo[i:i + 100]
        doc = f.request(f"{POSTCODES}/postcodes", body={"postcodes": batch}, timeout=60) or {}
        for item in doc.get("result") or []:
            pc = item.get("query")
            reg = region_of(item.get("result"))
            how = "postcode"
            if reg is None:
                # Fallbacks: a terminated postcode's position, then the outcode.
                t = f.request(f"{POSTCODES}/terminated_postcodes/{urllib.parse.quote(pc)}", timeout=60)
                tr = (t or {}).get("result")
                if tr and tr.get("latitude"):
                    reg = reverse(tr["latitude"], tr["longitude"])
                    how = "terminated"
            if reg is None:
                oc = pc.split()[0]
                o = f.request(f"{POSTCODES}/outcodes/{urllib.parse.quote(oc)}", timeout=60)
                orr = (o or {}).get("result")
                if orr:
                    countries = set(orr.get("country") or [])
                    if len(countries) == 1 and next(iter(countries)) in REGIONS:
                        reg = next(iter(countries))
                    elif orr.get("latitude"):
                        reg = reverse(orr["latitude"], orr["longitude"])
                    how = "outcode"
            f.store("postcodes", pc, {"region": reg, "how": how})
            result[pc] = reg
    return result


def lookup_places(f, localities):
    """Town name -> region, only when every town or city of that name agrees on one region."""
    out = {}
    for loc in sorted(set(l for l in localities if l)):
        c = f.cached("places", loc.lower())
        if c is None:
            q = urllib.parse.urlencode({"q": loc, "limit": 20})
            doc = f.request(f"{POSTCODES}/places?{q}", timeout=60) or {}
            # Cities first, then towns: a city of that name wins over suburbs elsewhere,
            # but two cities or two towns of the same name in different regions place nothing.
            c = {"region": None}
            for tier in (("City",), ("Town",)):
                regs = set()
                for r in doc.get("result") or []:
                    names = {(r.get("name_1") or "").lower(), (r.get("name_2") or "").lower()}
                    if loc.lower() in names and r.get("local_type") in tier:
                        regs.add(PLACE_REGION.get((r.get("region") or "").lower()))
                if regs:
                    if len(regs) == 1 and None not in regs:
                        c = {"region": next(iter(regs))}
                    break
            f.store("places", loc.lower(), c)
        out[loc] = c["region"]
    return out


# =======================================================================================
# Tally companies
# =======================================================================================

def load_tally():
    """(names, by_ch, by_norm). by_norm leaves out names shared by more than one company."""
    data = json.loads(TALLY.read_text(encoding="utf-8"))
    names = {c["name"] for c in data["companies"]}
    by_ch = {}
    for p in COMPANIES.rglob("*.md"):
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
            by_ch.setdefault(ch, set()).add(name)
    by_ch = {k: next(iter(v)) for k, v in by_ch.items() if len(v) == 1}
    counts = Counter(norm_name(n) for n in names)
    by_norm = {norm_name(n): n for n in names if norm_name(n) and counts[norm_name(n)] == 1}
    return names, by_ch, by_norm


def match_tally(row, by_ch, by_norm):
    if row["ch"] and row["ch"] in by_ch:
        return by_ch[row["ch"]], "ch"
    n = norm_name(row["name"])
    if len(n) >= 3 and n in by_norm:
        return by_norm[n], "name"
    return None, None


# =======================================================================================
# Building money.json
# =======================================================================================

def build(args, log):
    f = Fetcher(args.cache, args.max_requests, log)
    today = args.today
    # Coverage: the period both sources are complete for, read from the cache alone.
    cf_from = coverage(f, "cf", day_windows(START, today))
    fts_since = max(START, args.fts_since)
    fts_from = coverage(f, "fts", week_windows(fts_since, today))
    if cf_from is None:
        raise SystemExit("no complete Contracts Finder coverage in the cache")
    period_from = cf_from
    if fts_from is not None and fts_from > max(cf_from, fts_since):
        period_from = fts_from
    if args.period_from:
        period_from = max(period_from, args.period_from)
    log(f"coverage: Contracts Finder from {cf_from}, Find a Tender from {fts_from} "
        f"(needed from {fts_since}); period from {period_from}")
    rows, rep = extract(args.cache, today, log, period_from)
    rep["coverage"] = {"cf": str(cf_from), "fts": str(fts_from), "from": str(period_from)}
    fill_scale(rows)
    names, by_ch, by_norm = load_tally()

    # Place every supplier share.
    pcs = lookup_postcodes(f, [r["postcode"] for r in rows if r["postcode"]
                               and not (r["country"] and not is_uk(r["country"]))], log)
    need_place = [r["locality"] for r in rows
                  if not (r["country"] and not is_uk(r["country"]))
                  and not (r["postcode"] and pcs.get(r["postcode"]) in REGIONS) and not r["nuts"]]
    places = lookup_places(f, need_place)
    rep["placed_by"] = Counter()
    for r in rows:
        if r["country"] and not is_uk(r["country"]):
            r["place"], r["where"], how = "overseas", country_label(r["country"]), "country"
        elif r["postcode"] and pcs.get(r["postcode"]) in REGIONS:
            r["place"], r["where"], how = "region", pcs[r["postcode"]], "postcode"
        elif r["nuts"]:
            r["place"], r["where"], how = "region", r["nuts"], "nuts"
        elif places.get(r["locality"]):
            r["place"], r["where"], how = "region", places[r["locality"]], "town"
        else:
            r["place"], r["where"], how = "unplaced", None, "none"
        rep["placed_by"][how] += 1
        r["tally"], r["how"] = match_tally(r, by_ch, by_norm)
        r["named"] = nameable(r["name"], r["ch"]) or bool(r["tally"])
        r["year"] = int(r["date"][:4])

    years = list(range(period_from.year, today.year + 1))
    regions = {str(y): {} for y in years}
    overseas = {str(y): {} for y in years}
    unplaced = {str(y): {"value": 0, "count": 0} for y in years}
    groups = defaultdict(lambda: {"value": 0.0, "count": 0, "tally_value": 0.0,
                                  "tally_count": 0, "sme": [0.0, 0], "large": [0.0, 0],
                                  "sup": defaultdict(lambda: [0.0, 0, None])})
    for r in rows:
        y = str(r["year"])
        if r["place"] == "unplaced":
            unplaced[y]["value"] += r["value"]
            unplaced[y]["count"] += 1
            continue
        g = groups[(r["place"], y, r["where"])]
        g["value"] += r["value"]
        g["count"] += 1
        if r["tally"]:
            g["tally_value"] += r["value"]
            g["tally_count"] += 1
        if r.get("scale") in ("sme", "large"):
            g[r["scale"]][0] += r["value"]
            g[r["scale"]][1] += 1
        if r["named"]:
            key = r["tally"] or norm_name(r["name"]) or r["name"]
            s = g["sup"][key]
            s[0] += r["value"]
            s[1] += 1
            if s[2] is None:
                s[2] = r["tally"] or r["name"]
    for (place, y, where), g in groups.items():
        top = sorted(g["sup"].items(), key=lambda kv: (-kv[1][0], kv[1][2]))[:5]
        entry = {
            "value": round(g["value"]), "count": g["count"],
            "top": [{"name": s[2], "value": round(s[0]), "count": s[1],
                     "tally": s[2] if s[2] in names and k == s[2] else None} for k, s in top],
        }
        if place == "region":
            entry["tally_value"] = round(g["tally_value"])
            entry["tally_count"] = g["tally_count"]
            for size in ("sme", "large"):
                entry[f"{size}_value"] = round(g[size][0])
                entry[f"{size}_count"] = g[size][1]
            regions[y][where] = entry
        else:
            overseas[y][where] = entry
    for y in unplaced:
        unplaced[y]["value"] = round(unplaced[y]["value"])

    companies = defaultdict(list)
    for r in rows:
        if r["tally"]:
            companies[r["tally"]].append({
                "date": r["date"], "value": round(r["value"]), "buyer": r["buyer"],
                "title": r["title"][:200], "url": r["url"],
            })
    for k in companies:
        companies[k].sort(key=lambda x: (x["date"], x["value"]), reverse=True)

    sources = ["Contracts Finder"]
    if fts_from is not None:
        sources.append("Find a Tender")
    doc = {
        "generated": today.isoformat(),
        "attribution": ATTRIBUTION,
        "sources": sources,
        "period": {"from": period_from.isoformat(), "to": today.isoformat()},
        "years": years,
        "regions": regions,
        "overseas": overseas,
        "unplaced": unplaced,
        "companies": dict(companies),
        "excluded": {"frameworks": rep["frameworks"], "non_gbp": rep["non_gbp"]},
    }
    text = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    OUT.write_text(text + "\n", encoding="utf-8")
    log(f"wrote {OUT.name}: {len(text.encode()) / 1e6:.2f} MB")
    report(rows, rep, doc, log, args)


def gbp(v):
    return f"£{v:,.0f}"


def report(rows, rep, doc, log, args):
    log("\n== Coverage: " + json.dumps(rep["coverage"]))
    log("== Releases read: " + json.dumps(dict(rep["releases"])))
    log(f"postcode lookups etc. not counted here; rows (supplier shares): {len(rows)}")
    log("\n== Buyers included (notices):")
    for b, n in sorted(rep["buyers_in"].items(), key=lambda x: -x[1]):
        log(f"  {n:6d}  {b}")
    log("\n== Near misses excluded (notices):")
    for b, n in sorted(rep["buyers_near"].items(), key=lambda x: -x[1])[:80]:
        log(f"  {n:6d}  {b}")
    log("\n== Exclusions: " + json.dumps({k: rep[k] for k in (
        "frameworks", "non_gbp", "no_value", "out_of_period", "dup_cross", "inactive",
        "no_supplier", "shared", "before_period")}) + " currencies " + json.dumps(dict(rep["non_gbp_currencies"])))
    log(f"\n== Cross-source duplicates removed: {len(rep['dup_pairs'])}")
    for d in rep["dup_pairs"]:
        log("  " + d)
    ft = rep["framework_titles"]
    log(f"\n== Framework or DPS awards excluded: {len(ft)}; a sample:")
    for t in sorted(ft, key=lambda x: hashlib.sha256(x.encode()).hexdigest())[:15]:
        log("  " + t)
    log("\n== Totals per year (counted value, awards-shares, unplaced share of value):")
    for y in doc["years"]:
        ys = [r for r in rows if r["year"] == y]
        tot = sum(r["value"] for r in ys)
        un = sum(r["value"] for r in ys if r["place"] == "unplaced")
        ov = sum(r["value"] for r in ys if r["place"] == "overseas")
        unc = sum(1 for r in ys if r["place"] == "unplaced")
        log(f"  {y}: {gbp(tot)} over {len(ys)}; overseas {gbp(ov)}; unplaced {gbp(un)} "
            f"({(un / tot * 100) if tot else 0:.1f}% of value, {unc} shares)")
    log("\n== Regions, all years:")
    agg = defaultdict(float)
    for r in rows:
        agg[r["where"] or "(unplaced)"] += r["value"]
    for k, v in sorted(agg.items(), key=lambda x: -x[1]):
        log(f"  {gbp(v):>20}  {k}")
    log("\n== Placed by: " + json.dumps(dict(rep["placed_by"])))
    log("\n== Overseas countries: " + ", ".join(sorted({r["where"] for r in rows if r["place"] == "overseas"})))
    log("\n== 15 largest awards:")
    for r in sorted(rows, key=lambda x: -x["value"])[:15]:
        nm = r["name"] if r["named"] else "(unnamed)"
        log(f"  {gbp(r['value']):>18}  {r['date']}  {nm[:45]:45}  {r['buyer'][:30]:30}  {r['title'][:60]}  {r['url']}")
    vals = sorted(r["value"] for r in rows)
    if vals:
        q = lambda p: vals[min(len(vals) - 1, int(p * len(vals)))]
        log(f"\n== Value distribution: median {gbp(q(0.5))}, p90 {gbp(q(0.9))}, p99 {gbp(q(0.99))}, max {gbp(vals[-1])}; zero-value {sum(1 for v in vals if v == 0)}")
    m = [r for r in rows if r["tally"]]
    log(f"\n== Tally matches: {len(m)} award shares, {len({r['tally'] for r in m})} companies "
        f"(by CH {sum(1 for r in m if r['how'] == 'ch')}, by name {sum(1 for r in m if r['how'] == 'name')})")
    seen = set()
    samples = []
    for r in sorted(m, key=lambda x: hashlib.sha256(x["name"].encode()).hexdigest()):
        if r["name"] in seen:
            continue
        seen.add(r["name"])
        samples.append(r)
    for r in samples[:20]:
        log(f"  [{r['how']}] {r['name']}  ->  {r['tally']}")
    sc = [r for r in rows if re.search(r"supply chain notice|subcontract", r["title"], re.I)]
    log(f"\n== Subcontract notices published under a defence buyer (counted): {len(sc)}, "
        f"{gbp(sum(r['value'] for r in sc))}")
    log(f"\n== Unnamed supplier shares (rule 6): {sum(1 for r in rows if not r['named'])}")
    uk = [r for r in rows if r["place"] == "region"]
    by = Counter(r.get("scale") or "not known" for r in uk)
    val = defaultdict(float)
    for r in uk:
        val[r.get("scale") or "not known"] += r["value"]
    log(f"\n== Supplier size, UK regions: " + ", ".join(f"{k} {by[k]} shares {gbp(val[k])}" for k in ("sme", "large", "not known"))
        + f"; filled from the same supplier {sum(1 for r in uk if r.get('scale_filled'))}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stage", choices=["fetch", "build", "all"])
    ap.add_argument("--cache", required=True, help="folder for raw downloads (outside the repo)")
    ap.add_argument("--today", type=datetime.date.fromisoformat, default=datetime.date.today())
    ap.add_argument("--since", type=datetime.date.fromisoformat, default=START,
                    help="fetch from this date (default 2023-01-01)")
    ap.add_argument("--fts-since", type=datetime.date.fromisoformat,
                    default=datetime.date(2025, 2, 24),
                    help="fetch Find a Tender from this date (Procurement Act notices)")
    ap.add_argument("--period-from", type=datetime.date.fromisoformat, default=None,
                    help="build: start the period no earlier than this date")
    ap.add_argument("--skip-cf", action="store_true")
    ap.add_argument("--skip-fts", action="store_true")
    ap.add_argument("--max-requests", type=int, default=4000)
    ap.add_argument("--pause", type=float, default=PAUSE, help="seconds between requests")
    args = ap.parse_args(argv)
    globals()["PAUSE"] = args.pause
    log = lambda m: print(m, flush=True)
    if args.stage in ("fetch", "all"):
        fetch(args, log)
    if args.stage in ("build", "all"):
        build(args, log)


if __name__ == "__main__":
    main()
