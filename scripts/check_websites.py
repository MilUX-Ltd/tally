#!/usr/bin/env python3
"""Check every Tally company website and write websites.json: dead websites and moved pages.

Standard library only. Run weekly in GitHub Actions:

    python3 scripts/check_websites.py --previous websites.json

Each website is fetched once, redirects followed. A host that does not exist, a refused
connection, or a 404 or 410 is "gone"; any answer below 400 is "ok"; everything else (403, 429,
5xx, timeouts, dropped connections, certificate errors) is "uncertain" and never acted on. A gone
page that is not the home page has its home page checked: if that works, the page has "moved"
and the site links to the home page. A result is published only when the same URL had the same
result in the previous run; a first failure waits in `pending`. Rules: docs/websites-data.md.
"""

import argparse
import datetime
import errno
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TALLY = ROOT / "tally-data.json"
OUT = ROOT / "websites.json"
USER_AGENT = "Mozilla/5.0 (compatible; TallyLinkCheck/1.0; +https://tally.milux.co.uk/about/)"
# Some sites answer 404 to anything that is not a browser: a 404 is checked again as one.
BROWSER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
TIMEOUT = 20
WORKERS = 16
MAX_GONE_SHARE = 0.10
MAX_UNCERTAIN_SHARE = 0.30
URL_OK = re.compile(r"^https?://\S+$", re.I)
NO_SUCH_HOST = {getattr(socket, n) for n in ("EAI_NONAME", "EAI_NODATA") if hasattr(socket, n)}


# =======================================================================================
# Rules (tested in tests/acceptance/test_websites.py)
# =======================================================================================

def classify(outcome):
    """("ok" | "gone" | "uncertain", reason) for {"status": int} or {"error": kind}."""
    status = outcome.get("status")
    if status is not None:
        if status < 400:
            return "ok", None
        if status in (404, 410):
            return "gone", "not-found"
        return "uncertain", None
    error = outcome.get("error")
    if error == "dns":
        return "gone", "no-such-host"
    if error == "refused":
        return "gone", "refused"
    return "uncertain", None


def home_of(url):
    """The site's root as a browser writes its origin: host in lower case, no default port or user."""
    p = urllib.parse.urlsplit(url)
    scheme = p.scheme.lower()
    host = (p.hostname or "").lower()
    port = p.port
    keep_port = port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443))
    return f"{scheme}://{host}{f':{port}' if keep_port else ''}/"


def is_home(url):
    path = urllib.parse.urlsplit(url).path
    return path in ("", "/") or path.lower() in ("/index.html", "/index.htm", "/index.php", "/home")


def settle(url, page, home):
    """The result for a website from its page's class and, for a gone deep link, its home page's."""
    kind, reason = page
    if kind != "gone":
        return kind, None
    if is_home(url) or home is None:
        return "dead", reason
    if home[0] == "ok":
        return "moved", home_of(url)
    if home[0] == "gone":
        return "dead", reason
    return "uncertain", None


def confirm(previous, current, today, uncertain=()):
    """(dead, moved, pending): a dead or moved result is published when the previous run had the
    same result for the same company and URL; otherwise it waits in pending. A published row
    whose URL is uncertain in this run is kept as it was: only a working answer clears it. A
    published moved link that is now dead is published as dead at once."""
    seen = {}
    published_moved = set()
    keep = []
    uncertain = set(uncertain)
    for kind in ("dead", "moved"):
        for row in (previous or {}).get(kind, []):
            seen[(row["name"], row["url"], kind)] = row["since"]
            if kind == "moved":
                published_moved.add((row["name"], row["url"]))
            if (row["name"], row["url"]) in uncertain:
                keep.append((kind, row))
    for row in (previous or {}).get("pending", []):
        seen.setdefault((row["name"], row["url"], row["result"]), row["since"])
    dead, moved, pending = [], [], []
    for r in current:
        key = (r["name"], r["url"], r["result"])
        detail = {"reason": r["reason"]} if r["result"] == "dead" else {"home": r["home"]}
        if key in seen or (r["result"] == "dead" and (r["name"], r["url"]) in published_moved):
            row = {"name": r["name"], "url": r["url"], **detail, "since": seen.get(key, today)}
            (dead if r["result"] == "dead" else moved).append(row)
        else:
            pending.append({"name": r["name"], "url": r["url"], "result": r["result"], **detail, "since": today})
    for kind, row in keep:
        (dead if kind == "dead" else moved).append(row)
    order = lambda row: (row["name"].lower(), row["url"])  # noqa: E731
    return sorted(dead, key=order), sorted(moved, key=order), sorted(pending, key=order)


def check_gone_share(gone, total, uncertain=0):
    if total and gone / total > MAX_GONE_SHARE:
        raise SystemExit(f"{gone} of {total} websites gone in one run (limit {MAX_GONE_SHARE:.0%}); "
                         "probably a network fault on the runner; not written")
    if total and uncertain / total > MAX_UNCERTAIN_SHARE:
        raise SystemExit(f"{uncertain} of {total} websites uncertain in one run (limit {MAX_UNCERTAIN_SHARE:.0%}); "
                         "probably a network fault on the runner; not written")


# =======================================================================================
# Fetching
# =======================================================================================

def fetch(url, agent=USER_AGENT):
    """{"status": code} or {"error": "dns" | "refused" | "tls" | "timeout" | "other"}."""
    req = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": "text/html,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            r.read(1024)
            return {"status": r.status}
    except urllib.error.HTTPError as e:
        return {"status": e.code}
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, socket.gaierror):
            return {"error": "dns" if reason.errno in NO_SUCH_HOST else "other"}
        if isinstance(reason, ConnectionRefusedError) or getattr(reason, "errno", None) == errno.ECONNREFUSED:
            return {"error": "refused"}
        if isinstance(reason, ssl.SSLError):
            return {"error": "tls"}
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return {"error": "timeout"}
        return {"error": "other"}
    except (TimeoutError, socket.timeout):
        return {"error": "timeout"}
    except Exception:  # noqa: BLE001 - dropped connections and malformed responses
        return {"error": "other"}


def fetch_page(url):
    """A page's class; a 404 or 410 is checked again as a browser before it counts as gone."""
    page = classify(fetch(url))
    if page == ("gone", "not-found"):
        page = classify(fetch(url, BROWSER_AGENT))
    return page


def check_one(item):
    name, url = item
    page = fetch_page(url)
    home = None
    if page[0] == "gone" and page[1] == "not-found" and not is_home(url):
        home = fetch_page(home_of(url))
    result, extra = settle(url, page, home)
    return {"name": name, "url": url, "page": page[0], "result": result,
            **({"reason": extra} if result == "dead" else {"home": extra} if result == "moved" else {})}


def tally_websites():
    companies = json.loads(TALLY.read_text(encoding="utf-8"))["companies"]
    counts = Counter(c["name"] for c in companies)
    out = []
    for c in companies:
        url = (c.get("website") or "").strip()
        if counts[c["name"]] == 1 and URL_OK.match(url):
            out.append((c["name"], url))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--previous", type=Path)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--today", type=datetime.date.fromisoformat, default=datetime.date.today())
    args = ap.parse_args(argv)
    sites = tally_websites()
    print(f"== Checking {len(sites)} websites")
    with ThreadPoolExecutor(WORKERS) as ex:
        results = list(ex.map(check_one, sites))
    pages = Counter(r["page"] for r in results)
    check_gone_share(pages["gone"], len(sites), pages["uncertain"])
    previous = None
    if args.previous and args.previous.exists():
        previous = json.loads(args.previous.read_text(encoding="utf-8"))
    current = [r for r in results if r["result"] in ("dead", "moved")]
    uncertain = [(r["name"], r["url"]) for r in results if r["result"] == "uncertain"]
    dead, moved, pending = confirm(previous, current, args.today.isoformat(), uncertain)
    doc = {
        "generated": args.today.isoformat(),
        "checked": {"websites": len(sites), "ok": pages["ok"], "gone": pages["gone"], "uncertain": pages["uncertain"]},
        "dead": dead, "moved": moved, "pending": pending,
    }
    args.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ok {pages['ok']}, gone {pages['gone']}, uncertain {pages['uncertain']}")
    print(f"dead {len(dead)}, moved {len(moved)}, pending {len(pending)}")
    print(f"wrote {args.out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
