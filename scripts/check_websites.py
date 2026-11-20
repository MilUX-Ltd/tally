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
TIMEOUT = 20
WORKERS = 16
MAX_GONE_SHARE = 0.10
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
    p = urllib.parse.urlsplit(url)
    return f"{p.scheme}://{p.netloc}/"


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


def confirm(previous, current, today):
    """(dead, moved, pending): a dead or moved result is published when the previous run had the
    same result for the same company and URL; otherwise it waits in pending."""
    seen = {}
    for kind in ("dead", "moved"):
        for row in (previous or {}).get(kind, []):
            seen[(row["name"], row["url"], kind)] = row["since"]
    for row in (previous or {}).get("pending", []):
        seen.setdefault((row["name"], row["url"], row["result"]), row["since"])
    dead, moved, pending = [], [], []
    for r in current:
        key = (r["name"], r["url"], r["result"])
        detail = {"reason": r["reason"]} if r["result"] == "dead" else {"home": r["home"]}
        if key in seen:
            row = {"name": r["name"], "url": r["url"], **detail, "since": seen[key]}
            (dead if r["result"] == "dead" else moved).append(row)
        else:
            pending.append({"name": r["name"], "url": r["url"], "result": r["result"], **detail, "since": today})
    order = lambda row: (row["name"].lower(), row["url"])  # noqa: E731
    return sorted(dead, key=order), sorted(moved, key=order), sorted(pending, key=order)


def check_gone_share(gone, total):
    if total and gone / total > MAX_GONE_SHARE:
        raise SystemExit(f"{gone} of {total} websites gone in one run (limit {MAX_GONE_SHARE:.0%}); "
                         "probably a network fault on the runner; not written")


# =======================================================================================
# Fetching
# =======================================================================================

def fetch(url):
    """{"status": code} or {"error": "dns" | "refused" | "tls" | "timeout" | "other"}."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
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


def check_one(item):
    name, url = item
    page = classify(fetch(url))
    home = None
    if page[0] == "gone" and page[1] == "not-found" and not is_home(url):
        home = classify(fetch(home_of(url)))
    result, extra = settle(url, page, home)
    return {"name": name, "url": url, "page": page[0], "result": result,
            **({"reason": extra} if result == "dead" else {"home": extra} if result == "moved" else {})}


def tally_websites():
    companies = json.loads(TALLY.read_text(encoding="utf-8"))["companies"]
    counts = Counter(c["name"] for c in companies)
    out = []
    for c in companies:
        url = (c.get("website") or "").strip()
        if counts[c["name"]] == 1 and url.lower().startswith(("http://", "https://")):
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
    check_gone_share(pages["gone"], len(sites))
    previous = None
    if args.previous and args.previous.exists():
        previous = json.loads(args.previous.read_text(encoding="utf-8"))
    current = [r for r in results if r["result"] in ("dead", "moved")]
    dead, moved, pending = confirm(previous, current, args.today.isoformat())
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
