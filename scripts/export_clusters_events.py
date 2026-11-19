#!/usr/bin/env python3
"""Export the cluster list, upcoming cluster events and open opportunities for the Tally site.

Reads a cluster round-up folder (clusters.json and editions/current.json) and writes
clusters.json, events.json and opportunities.json at the top of this repository. Run by the
weekly refresh:

    python3 scripts/export_clusters_events.py --source <round-up folder> --today YYYY-MM-DD

Standard library only. The export works by allow-list:

- Only items of kind "event", dated on or after --today, for a known cluster.
- Public events keep cluster, date, time, place, title, summary and link. A public event
  without a public http(s) link is left out, because it cannot be shown to be public.
- Members-only events keep cluster and date only, and get a fixed line of text and the
  cluster's own website as their link. Nothing else from a members-only item is read.
  A members-only event for a cluster without a website is left out.
- Items whose text mentions how they were received (email, newsletters, forwarding) are
  left out.
- Nothing else from the round-up is copied: no source, received date, id, other
  clusters, post links or notes.

Funding calls and opportunities (opportunities.json), by allow-list too:

- Only items of kind "funding" or "opportunity", for a known cluster, marked public.
- Only items dated on or after --today, or undated items whose own title or summary says
  they are open-ended (rolling, ongoing, always open, no closing date). If it is unclear,
  the item is left out.
- Only items with a public http(s) link. Each keeps kind, cluster, deadline, time, title,
  summary and link, and nothing else.
- Members-only items are left out entirely, with no signpost: nothing is read from them.
- Items whose text mentions how they were received, or carries an email address or a
  personal LinkedIn profile, are left out.

Region codes are ONS Open Geography codes (December 2025): counties and unitary
authorities, English regions, and countries. They describe each cluster's area from its
region text, and the site draws the cluster boundaries from them.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SIGNPOST = "Members' event: join the cluster for details"
SOURCE_NOTE = (
    "UK regional defence and security clusters and their upcoming events, from the clusters' "
    "public websites and pages. Members-only events appear only as a signpost to join the cluster. "
    "Region codes are ONS Open Geography codes (December 2025)."
)
RECEIVED = re.compile(
    r"e-?mail|newsletter|mailing list|inbox|forward(ed|ing)?\b|\breceived\b|bulletin"
    r"|shared (with|for) (cluster )?members|sent to members",
    re.I,
)
SAFE_LINK = re.compile(r"^https?://[^\s]+$", re.I)

# Each cluster's area, from its region text, as ONS codes and names.
REGIONS = {
    "SWRDSC": [
        ("E06000052", "Cornwall"),
        ("E06000053", "Isles of Scilly"),
        ("E10000008", "Devon"),
        ("E06000026", "Plymouth"),
        ("E06000027", "Torbay"),
        ("E06000059", "Dorset"),
        ("E06000058", "Bournemouth, Christchurch and Poole"),
        ("E06000066", "Somerset"),
    ],
    "GLRDSC": [
        ("E10000019", "Lincolnshire"),
        ("E06000013", "North Lincolnshire"),
        ("E06000012", "North East Lincolnshire"),
        ("E06000017", "Rutland"),
    ],
    "OBCRDSC": [
        ("E10000025", "Oxfordshire"),
        ("E06000060", "Buckinghamshire"),
    ],
    "SCRDSC": [
        ("E10000014", "Hampshire"),
        ("E06000045", "Southampton"),
        ("E06000044", "Portsmouth"),
        ("E06000046", "Isle of Wight"),
        ("E10000030", "Surrey"),
        ("E10000032", "West Sussex"),
    ],
    "NWRDSC": [("E12000002", "North West")],
    "LRDSC": [("E12000007", "London")],
    "NERDSC": [("E12000001", "North East")],
    "ERDSC": [
        ("E10000012", "Essex"),
        ("E06000033", "Southend-on-Sea"),
        ("E06000034", "Thurrock"),
        ("E10000029", "Suffolk"),
        ("E10000020", "Norfolk"),
        ("E10000003", "Cambridgeshire"),
        ("E06000031", "Peterborough"),
        ("E10000015", "Hertfordshire"),
        ("E06000055", "Bedford"),
        ("E06000056", "Central Bedfordshire"),
        ("E06000032", "Luton"),
    ],
    "EMRDSC": [("E12000004", "East Midlands")],
    "WRDSC": [
        ("E06000023", "Bristol, City of"),
        ("E10000013", "Gloucestershire"),
        ("E06000025", "South Gloucestershire"),
        ("E06000022", "Bath and North East Somerset"),
        ("E06000054", "Wiltshire"),
        ("E06000030", "Swindon"),
    ],
    "WalesDSC": [("W92000004", "Wales")],
    "WMRDSC": [("E12000005", "West Midlands")],
    "YRDSC": [("E12000003", "Yorkshire and The Humber")],
    "NIDSC": [("N92000002", "Northern Ireland")],
    "SERDSC": [
        ("E10000016", "Kent"),
        ("E06000035", "Medway"),
        ("E10000011", "East Sussex"),
        ("E06000043", "Brighton and Hove"),
    ],
    "ScotlandDSC": [("S92000003", "Scotland")],
}

# Each cluster's membership tag, where the taxonomy has one.
MEMBERSHIPS = {
    "SCRDSC": "mbr-scrdsc",
    "GLRDSC": "mbr-glrdsc",
    "WalesDSC": "mbr-walesdsc",
}


def text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def https(value):
    value = text(value)
    return value if value and value.startswith("https://") and SAFE_LINK.match(value) else None


def iso_date(value):
    try:
        return date.fromisoformat(value).isoformat() if isinstance(value, str) else None
    except ValueError:
        return None


def build_clusters(raw, today):
    clusters = []
    for c in raw["clusters"]:
        cid = c["id"]
        if cid not in REGIONS:
            raise ValueError(f"cluster {cid} has no region codes; add it to REGIONS")
        clusters.append({
            "id": cid,
            "name": text(c.get("name")),
            "full": text(c.get("full")),
            "region": text(c.get("region")),
            "regions": [{"code": code, "name": name} for code, name in REGIONS[cid]],
            "status": text(c.get("status")),
            "web": https(c.get("web")),
            "linkedin": https(c.get("linkedin")),
            "colour": text(c.get("colour")),
            "membership": MEMBERSHIPS.get(cid),
        })
    return {"as_of": today, "source": SOURCE_NOTE, "clusters": clusters}


def mentions_receipt(item):
    return any(
        isinstance(item.get(k), str) and RECEIVED.search(item[k])
        for k in ("title", "summary", "where", "time")
    )


def build_events(items, clusters, today):
    web = {c["id"]: c["web"] for c in clusters}
    events = []
    for item in items:
        if item.get("kind") != "event":
            continue
        day = iso_date(item.get("date"))
        cluster = item.get("cluster")
        if not day or day < today or cluster not in web:
            continue
        audience = item.get("audience")
        if audience == "members":
            # Allow-list: cluster and date only. Nothing else from the item is read.
            if not web[cluster]:
                continue
            events.append({
                "audience": "members",
                "cluster": cluster,
                "date": day,
                "text": SIGNPOST,
                "link": web[cluster],
            })
        elif audience == "public":
            if mentions_receipt(item) or not text(item.get("title")):
                continue
            link = text(item.get("link"))
            if not (link and SAFE_LINK.match(link)):
                continue
            events.append({
                "audience": "public",
                "cluster": cluster,
                "date": day,
                "time": text(item.get("time")),
                "where": text(item.get("where")),
                "title": text(item.get("title")),
                "summary": text(item.get("summary")),
                "link": link,
            })
    events.sort(key=lambda e: (e["date"], e["cluster"], e.get("title") or ""))
    return {"as_of": today, "events": events}


# Funding calls and opportunities --------------------------------------------------------

OPPORTUNITY_KINDS = ("funding", "opportunity")
OPEN_ENDED = re.compile(
    r"\brolling\b|\bongoing\b|\balways open\b|\bopen all year\b|\bopen year-round\b"
    r"|\bno (closing date|deadline)\b",
    re.I,
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PERSONAL_LINKEDIN = re.compile(r"linkedin\.com/in/", re.I)


def carries_personal_data(item):
    return any(
        isinstance(item.get(k), str) and (EMAIL.search(item[k]) or PERSONAL_LINKEDIN.search(item[k]))
        for k in ("title", "summary", "time", "link")
    )


def build_opportunity_list(items, clusters, today):
    known = {c["id"] for c in clusters}
    out = []
    for item in items:
        if item.get("kind") not in OPPORTUNITY_KINDS or item.get("cluster") not in known:
            continue
        # Members-only (or unlabelled) items are left out; nothing else is read from them.
        if item.get("audience") != "public":
            continue
        title, summary = text(item.get("title")), text(item.get("summary"))
        if not title or mentions_receipt(item) or carries_personal_data(item):
            continue
        link = text(item.get("link"))
        if not (link and SAFE_LINK.match(link)):
            continue
        deadline = iso_date(item.get("date"))
        if deadline:
            if deadline < today:
                continue
        elif item.get("date") is not None or not OPEN_ENDED.search(f"{title} {summary or ''}"):
            continue
        out.append({
            "kind": item["kind"],
            "cluster": item["cluster"],
            "deadline": deadline,
            "time": text(item.get("time")),
            "title": title,
            "summary": summary,
            "link": link,
        })
    out.sort(key=lambda o: (o["deadline"] is None, o["deadline"] or "", o["cluster"], o["title"]))
    return {"as_of": today, "opportunities": out}


def build_opportunities(source, today):
    """Return the opportunities document for a round-up folder and an export date."""
    today = date.fromisoformat(today).isoformat()
    source = Path(source)
    raw_clusters = json.loads((source / "clusters.json").read_text(encoding="utf-8"))
    edition = json.loads((source / "editions" / "current.json").read_text(encoding="utf-8"))
    clusters = build_clusters(raw_clusters, today)["clusters"]
    return build_opportunity_list(edition.get("items", []), clusters, today)


# Clusters and events, and the command line -----------------------------------------------

def build(source, today):
    """Return (clusters, events) documents for a round-up folder and an export date."""
    today = date.fromisoformat(today).isoformat()
    source = Path(source)
    raw_clusters = json.loads((source / "clusters.json").read_text(encoding="utf-8"))
    edition = json.loads((source / "editions" / "current.json").read_text(encoding="utf-8"))
    clusters = build_clusters(raw_clusters, today)
    events = build_events(edition.get("items", []), clusters["clusters"], today)
    return clusters, events


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, help="round-up folder")
    parser.add_argument("--today", default=date.today().isoformat(), help="export date, YYYY-MM-DD")
    args = parser.parse_args(argv)
    clusters, events = build(args.source, args.today)
    opportunities = build_opportunities(args.source, args.today)
    for name, doc in (
        ("clusters.json", clusters), ("events.json", events), ("opportunities.json", opportunities),
    ):
        (ROOT / name).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    members = sum(1 for e in events["events"] if e["audience"] == "members")
    print(
        f"Wrote {len(clusters['clusters'])} clusters and {len(events['events'])} events "
        f"({len(events['events']) - members} public, {members} members-only signposts)."
    )
    print(f"Wrote {len(opportunities['opportunities'])} open funding calls and opportunities.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
