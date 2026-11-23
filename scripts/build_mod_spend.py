#!/usr/bin/env python3
"""Build mod-spend.json: MOD's official direct spend with UK industry, by region and year.

Standard library only. Run monthly in GitHub Actions:

    python3 -I scripts/build_mod_spend.py --previous mod-spend.json

The source is MOD's annual official statistics "MOD regional expenditure with industry"
(Open Government Licence v3.0). The GOV.UK Content API names the newest edition, so no link is
kept by hand; from that edition the "Data tables" ODS is read. Only Table 2 (current prices,
£ million, by region) and Table 4 (the same per person, £) are taken, numbers only. The ODS is
opened as a zip and only content.xml is read, with a size cap; no formula, link or macro is
evaluated. Guards stop the build before anything is written (card 7475, D-tnpb9).
"""

import argparse
import math
import datetime
import json
import re
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "mod-spend.json"
API = "https://www.gov.uk/api/content"
COLLECTION = "/government/collections/mod-regional-expenditure-with-industry-index"
ASSET_HOST = "assets.publishing.service.gov.uk"
USER_AGENT = "TallyModSpend/1.0 (+https://tally.milux.co.uk/about/)"
ATTRIBUTION = ("Contains public sector information licensed under the Open Government Licence v3.0: "
               "Ministry of Defence, MOD regional expenditure with industry.")
TIMEOUT = 60
MAX_DOWNLOAD = 20 * 1024 * 1024
MAX_CONTENT_XML = 50 * 1024 * 1024
MAX_REPEAT = 64

REGIONS = [
    "East of England", "East Midlands", "London", "North East", "North West", "South East",
    "South West", "West Midlands", "Yorkshire and The Humber", "Northern Ireland", "Scotland", "Wales",
]
ENGLISH = REGIONS[:9]
NATIONS = REGIONS[9:]
MILLION = 1_000_000
ENGLAND_TOLERANCE = 10 * MILLION
UK_TOLERANCE = 5 * MILLION
MAX_REVISION = 0.10
YEAR = re.compile(r"^\s*(\d{4}/\d{2})")

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
T = "{%s}" % NS["table"]
X = "{%s}" % NS["text"]
O = "{%s}" % NS["office"]


# =======================================================================================
# Finding the edition (tested in tests/acceptance/test_mod_spend.py)
# =======================================================================================

def latest_edition(collection):
    """The base path of the newest edition in the collection's Content API answer."""
    docs = [d for d in collection.get("links", {}).get("documents", [])
            if d.get("base_path", "").startswith("/government/statistics/") and d.get("public_updated_at")]
    if not docs:
        raise SystemExit("no edition found in the MOD regional expenditure collection; not written")
    return max(docs, key=lambda d: d["public_updated_at"])["base_path"]


def data_tables_url(edition):
    """The URL of the edition's "Data tables" ODS, only from GOV.UK's asset host."""
    for a in edition.get("details", {}).get("attachments", []):
        title = (a.get("title") or "").strip()
        if not title.startswith("Data tables"):
            continue
        if a.get("content_type") != "application/vnd.oasis.opendocument.spreadsheet":
            continue
        url = a.get("url") or ""
        p = urllib.parse.urlsplit(url)
        if p.scheme != "https" or p.hostname != ASSET_HOST:
            raise SystemExit(f"data tables are not on {ASSET_HOST}: {url}; not written")
        return url
    raise SystemExit("the edition has no Data tables ODS; not written")


# =======================================================================================
# Reading the tables
# =======================================================================================

def _cell_text(cell):
    parts = []
    for p in cell.iter(X + "p"):
        parts.append("".join(p.itertext()))
    return " ".join(s for s in parts if s)


def _cell_value(cell):
    """A float cell's number as text when present, otherwise its displayed text."""
    if cell.get(O + "value-type") == "float" and cell.get(O + "value") is not None:
        return cell.get(O + "value")
    return _cell_text(cell)


def read_ods(path):
    """{sheet name: rows of cell strings} from an ODS file. Only content.xml is read."""
    with zipfile.ZipFile(path) as z:
        info = z.getinfo("content.xml")
        if info.file_size > MAX_CONTENT_XML:
            raise SystemExit("content.xml is larger than expected; not written")
        raw = z.read("content.xml")
    if not raw.lstrip().startswith(b"<?xml") or b"utf-8" not in raw[:100].lower():
        raise SystemExit("content.xml is not UTF-8 XML; not written")
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise SystemExit("content.xml carries a document type declaration; not written")
    root = ET.fromstring(raw)
    out = {}
    for tab in root.iter(T + "table"):
        rows = []
        for row in tab.iter(T + "table-row"):
            cells = []
            for cell in row:
                if cell.tag not in (T + "table-cell", T + "covered-table-cell"):
                    continue
                value = _cell_value(cell)
                repeat = int(cell.get(T + "number-columns-repeated", "1"))
                cells.extend([value] * min(repeat, MAX_REPEAT))
            while cells and not cells[-1]:
                cells.pop()
            repeat = int(row.get(T + "number-rows-repeated", "1"))
            if cells:
                rows.extend([cells] * min(repeat, MAX_REPEAT))
        out[tab.get(T + "name")] = rows
    return out


def _number(text):
    """A whole non-negative number from a cell, or None."""
    s = (text or "").replace(",", "").strip()
    try:
        f = float(s)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(f) or f < 0 or f != int(f):
        return None
    return int(f)


def _table(rows):
    """(years, breaks, {row name: [numbers]}) from one table's rows."""
    head = next((i for i, r in enumerate(rows) if r and r[0].strip() == "Region"), None)
    if head is None:
        raise SystemExit("a table has no Region heading row; not written")
    years, breaks, cols = [], [], []
    for j, h in enumerate(rows[head][1:], start=1):
        m = YEAR.match(h or "")
        if m:
            years.append(m.group(1))
            cols.append(j)
            if "[b]" in h:
                breaks.append(m.group(1))
    body = {}
    for r in rows[head + 1:]:
        name = (r[0] if r else "").strip()
        if not name:
            continue
        body[name] = [_number(r[j]) if j < len(r) else None for j in cols]
    return years, breaks, body


def parse(sheets):
    """{years, breaks, uk, england, regions} from Tables 2 and 4; values in pounds."""
    if "Table_2" not in sheets or "Table_4" not in sheets:
        raise SystemExit("Table 2 or Table 4 is missing; not written")
    years, breaks, spend = _table(sheets["Table_2"])
    pyears, _, per = _table(sheets["Table_4"])
    if not years:
        raise SystemExit("Table 2 has no financial years; not written")

    def pounds(name, i):
        v = spend.get(name, [None] * len(years))[i]
        return None if v is None else v * MILLION

    regions, uk, england = {}, {}, {}
    for i, y in enumerate(years):
        uk[y] = pounds("UK Total", i)
        england[y] = pounds("England", i)
        k = pyears.index(y) if y in pyears else None
        regions[y] = {}
        for r in REGIONS:
            if r not in spend:
                continue
            pp = per.get(r)
            regions[y][r] = {"value": pounds(r, i), "per_person": pp[k] if pp and k is not None else None}
    return {"years": years, "breaks": breaks, "uk": uk, "england": england, "regions": regions}


# =======================================================================================
# Guards
# =======================================================================================

def _ok(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def check(doc, previous):
    """Stop the build (SystemExit) when the tables do not hold together."""
    years = doc["years"]
    if not years or years != sorted(years):
        raise SystemExit("financial years missing or out of order; not written")
    for y in years:
        rows = doc["regions"].get(y, {})
        missing = [r for r in REGIONS if r not in rows]
        if missing:
            raise SystemExit(f"{y}: missing {', '.join(missing)}; not written")
        for r in REGIONS:
            if not _ok(rows[r]["value"]) or not _ok(rows[r]["per_person"]):
                raise SystemExit(f"{y} {r}: not a non-negative whole number; not written")
        if not _ok(doc["uk"].get(y)):
            raise SystemExit(f"{y}: UK Total is not a number; not written")
        england = doc.get("england", {}).get(y)
        if not _ok(england):
            raise SystemExit(f"{y}: the England row is missing or not a number; not written")
        if abs(sum(rows[r]["value"] for r in ENGLISH) - england) > ENGLAND_TOLERANCE:
            raise SystemExit(f"{y}: the English regions do not add up to England; not written")
        nations = england + sum(rows[r]["value"] for r in NATIONS)
        if abs(nations - doc["uk"][y]) > UK_TOLERANCE:
            raise SystemExit(f"{y}: England and the nations do not add up to the UK Total; not written")
    if previous:
        if previous.get("years") and years[-1] < previous["years"][-1]:
            raise SystemExit(f"latest year {years[-1]} is earlier than the last file's {previous['years'][-1]}; not written")
        for y, old in (previous.get("uk") or {}).items():
            new = doc["uk"].get(y)
            if new is not None and old and abs(new - old) / old > MAX_REVISION:
                raise SystemExit(f"{y}: UK total moved from {old:,} to {new:,}, more than "
                                 f"{MAX_REVISION:.0%}; a person should check it; not written")


# =======================================================================================
# Fetching and writing
# =======================================================================================

def _get(url, host, limit=MAX_DOWNLOAD):
    """The body at url, refusing an answer that ends anywhere but https on host (redirects included)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        final = urllib.parse.urlsplit(r.geturl())
        if final.scheme != "https" or final.hostname != host:
            raise SystemExit(f"{url} answered from {r.geturl()}, not {host}; not written")
        data = r.read(limit + 1)
    if len(data) > limit:
        raise SystemExit(f"{url} is larger than expected; not written")
    return data


def _api(path):
    return json.loads(_get(API + path, "www.gov.uk"))


def build(ods_path, edition, base_path):
    doc = parse(read_ods(ods_path))
    published = (edition.get("first_published_at") or edition.get("public_updated_at") or "")[:10]
    return doc, {
        "title": edition.get("title", "MOD regional expenditure with industry"),
        "url": "https://www.gov.uk" + base_path,
        "published": published,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--previous", type=Path)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--today", type=datetime.date.fromisoformat, default=datetime.date.today())
    args = ap.parse_args(argv)
    base_path = latest_edition(_api(COLLECTION))
    if not base_path.startswith("/government/statistics/"):
        raise SystemExit(f"unexpected edition path {base_path}; not written")
    edition = _api(base_path)
    url = data_tables_url(edition)
    print(f"== Edition {base_path}")
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "tables.ods"
        path.write_bytes(_get(url, ASSET_HOST))
        doc, source = build(path, edition, base_path)
    previous = None
    if args.previous and args.previous.exists():
        previous = json.loads(args.previous.read_text(encoding="utf-8"))
    check(doc, previous)
    if previous and previous.get("source") == source and previous.get("uk") == doc["uk"] \
            and previous.get("regions") == doc["regions"]:
        print("no change")
        return 0
    out = {
        "generated": args.today.isoformat(),
        "attribution": ATTRIBUTION,
        "source": source,
        "years": doc["years"],
        "breaks": doc["breaks"],
        "uk": doc["uk"],
        "regions": doc["regions"],
    }
    args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    latest = doc["years"][-1]
    print(f"{len(doc['years'])} years, latest {latest}, UK total £{doc['uk'][latest]:,}")
    print(f"wrote {args.out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
