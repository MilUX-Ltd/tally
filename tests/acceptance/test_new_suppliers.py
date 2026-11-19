"""Acceptance tests: new UK defence suppliers, and the gate's blocked-terms guard.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for adding UK defence suppliers researched from
public sources, and for the blocked-terms guard in .github/scripts/check.py. Do not
edit them to make a build pass; raise the problem instead.

Approved amendment: the list of names these pages were researched from is not
kept in this public repository, so the report lists only the published pages and
the full accounting is held privately.
"""

import csv
import hashlib
import importlib.util
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REPORT = ROOT / "reports" / "new-suppliers-2026-11.csv"
CHECK = ROOT / ".github" / "scripts" / "check.py"
OUTCOMES = {"new", "matched", "skipped"}
TAGS_BLOCK = re.compile(r"^tags:\n((?:[ \t]+- .*\n?)+)", re.M)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE = re.compile(r"(\+44[\s(]*\d|\b0\d{2,4}[\s-]\d{3,4}[\s-]?\d{3,4}\b)")
POSTCODE = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}$")
UK_LAT, UK_LON = (49.8, 60.95), (-8.7, 1.8)

# The hash set tally-site holds in scripts/check-public-terms.mjs. Hashes only.
TALLY_SITE_HASHES = {
    "9b89025ce7a6d932b28f6e15132a70d402f723874a425e9b4c7cc3b179fa66ce",
    "10efe505d4967f4a018c4205e15019cc8f7b08c48fb1b47a40541b296767bd55",
    "a48f08493be0a6bf482d176056bd5212a3ca543c605553c8a596aa69a19ef214",
    "01aff0b9db366eb032b5376df6561e64abb8ad4dd628c1e01c0ffa0407c8088d",
    "c0335b42a668bc5714f44f1bfc840acdbab2d4c62bae222d0bf39fef7f54ece8",
    "04b88ecb5f1ff67f0a0ff8135b2373243c31f9c1531c967e80b54a98b43d2e87",
    "74fa0196e5bd7a0a37435ded20ef1ad285c10a2c09070d619edc3408eb97d7f9",
    "c2f6badfda77cf1abeb02781d906a50668a17a0b79d435b05f8dcb2444852ac9",
    "153032bfae92f71e480edd7d358727a700fadf630dc899fb84bfa9b085781443",
    "afe0bafbe651ddcffef38adbc7958609fd798ea179b6c9b242fa8ad4fc6027fa",
    "80d4b7e298b50e1ca8ef8ea89f7d730acbc82fc18769413f5988523850fd3b67",
    "42b61e0b723ffbc9474c00d2e01d34ad0a2d7b8ca6204df0957c674ccb172996",
}

# Source-revealing phrases that must not appear on a new page or in the report.
# Hashes of the lower-case phrase, matched over one- to three-word runs.
SOURCE_PHRASE_HASHES = {
    "d37ff0b37ab9bfc329cda0d98c3e23baa4ffa45c799f3832cb1c142697155a94",
    "33e371b2736f94f2819637ed12398544e4018b37981b8d9812cdd81faf32f5c6",
    "cf5947d6d04692400f64c0830de320e3a1bf6ee35f77f6fa2dcccb61b4ec13f5",
}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_check():
    spec = importlib.util.spec_from_file_location("tally_check", CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def page_tags(text):
    match = TAGS_BLOCK.search(text)
    if not match:
        return []
    return [t.strip().strip("'\"") for t in re.findall(r"^[ \t]+- (.+)$", match.group(1), re.M)]


def field(text, key):
    end = text.find("\n---", 3)
    head = text[:end] if end > 0 else text
    match = re.search(rf"^{key}:[ \t]*(.*)$", head, re.M)
    return match.group(1).strip().strip("'\"") if match else ""


def report_rows():
    if not REPORT.exists():
        return []
    return list(csv.DictReader(REPORT.read_text(encoding="utf-8").splitlines()))


def known_tags(taxonomy):
    known = set()
    for facet in taxonomy["facets"].values():
        for value in facet["values"]:
            known.add(value.get("slug") or value.get("value"))
    retained = taxonomy.get("retained_unfaceted", {})
    known.update(retained.get("type", []))
    known.update(retained.get("ownership", []))
    known.update({"defence", "listed"})
    return known


def runs(text):
    words = re.findall(r"[a-z0-9-]+", text.lower())
    for i in range(len(words)):
        for n in (1, 2, 3):
            if i + n <= len(words):
                yield " ".join(words[i : i + n])


class NewSuppliers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.taxonomy = json.loads((ROOT / "taxonomy.json").read_text(encoding="utf-8"))
        cls.rows = report_rows()
        cls.pages = {}
        for path in sorted((ROOT / "Companies").rglob("*.md")):
            cls.pages[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")

    def test_every_reported_page_is_published(self):
        self.assertTrue(REPORT.exists(), "reports/new-suppliers-2026-11.csv is missing")
        self.assertTrue(self.rows, "the report is empty")
        problems = []
        for row in self.rows:
            if set(row) != {"outcome", "page"}:
                problems.append((row.get("page"), "report must hold only outcome and page"))
            if row["outcome"] not in {"new", "matched"}:
                problems.append((row["page"], f"unexpected outcome {row['outcome']}"))
            if row["page"] not in self.pages:
                problems.append((row["page"], "no such page"))
        self.assertEqual(problems, [], f"{len(problems)} report problems, e.g. {problems[:5]}")
        new_pages = [row["page"] for row in self.rows if row["outcome"] == "new"]
        self.assertEqual(len(new_pages), len(set(new_pages)), "a new page is reported twice")

    def test_new_pages_follow_the_page_rules(self):
        new = sorted({row["page"] for row in self.rows if row["outcome"] == "new"})
        self.assertTrue(new, "no new pages reported")
        known = known_tags(self.taxonomy)
        bad = []
        for page in new:
            text = self.pages.get(page, "")
            tags = page_tags(text)
            if "defence" not in tags:
                bad.append((page, "no defence tag"))
            for tag in tags:
                if tag not in known:
                    bad.append((page, f"unknown tag {tag}"))
                if "/" in tag and tag.split("/")[0] not in tags:
                    bad.append((page, f"{tag} without its parent"))
            if not field(text, "sources-verified").startswith("2026-11"):
                bad.append((page, "sources-verified not 2026-11"))
            if EMAIL.search(text):
                bad.append((page, "email address"))
            if PHONE.search(text):
                bad.append((page, "phone number"))
            source = field(text, "location-source")
            postcode, lat, lon = field(text, "postcode"), field(text, "lat"), field(text, "lon")
            if field(text, "uk-region") == "Overseas":
                if not field(text, "country"):
                    bad.append((page, "overseas without a country"))
            elif source == "region":
                if lat or lon or not field(text, "location-note"):
                    bad.append((page, "region source needs a note and no point"))
            elif source in {"website", "companies-house", "town"}:
                if source in {"website", "companies-house"} and not POSTCODE.match(postcode):
                    bad.append((page, "postcode missing or malformed"))
                try:
                    la, lo = float(lat), float(lon)
                    if not (UK_LAT[0] <= la <= UK_LAT[1] and UK_LON[0] <= lo <= UK_LON[1]):
                        bad.append((page, "point outside the UK"))
                except ValueError:
                    bad.append((page, "no point"))
            else:
                bad.append((page, "no location source"))
        self.assertEqual(bad, [], f"{len(bad)} new-page problems, e.g. {bad[:5]}")

    def test_viewer_records_match_the_pages(self):
        data = json.loads((ROOT / "tally-data.json").read_text(encoding="utf-8"))
        self.assertEqual(data["count"], len(data["companies"]))
        self.assertEqual(data["count"], len(self.pages))
        by_name = {c["name"]: c for c in data["companies"]}
        pages = sorted({row["page"] for row in self.rows if row["outcome"] in {"new", "matched"}})
        self.assertTrue(pages, "no pages reported")
        bad = []
        for page in pages:
            text = self.pages.get(page, "")
            record = by_name.get(field(text, "name") or Path(page).stem)
            if record is None:
                bad.append((page, "no record"))
            elif record["tags"] != page_tags(text):
                bad.append((page, "record tags differ from page tags"))
        self.assertEqual(bad, [], f"{len(bad)} reported pages without a matching record, e.g. {bad[:5]}")

    def test_guard_catches_a_planted_term_and_passes_ordinary_text(self):
        check = load_check()
        self.assertEqual(set(check.BLOCKED_HASHES), TALLY_SITE_HASHES)
        planted = {sha("quokkafern"), sha("amber quokka fern"), sha("wombat lantern")}
        self.assertTrue(check.find_blocked("A page about the Quokkafern radar.", planted))
        self.assertTrue(check.find_blocked("A Wombat Lantern sensor.", planted))
        self.assertTrue(check.find_blocked("They sell Amber\nQuokka Fern sensors.", planted))
        self.assertEqual(check.find_blocked("They sell amber sensors and fern pots.", planted), [])
        ordinary = "Made in Wales: precision engineering, radar and secure communications for defence."
        self.assertEqual(check.find_blocked(ordinary), [])

    def test_no_page_or_report_names_a_source(self):
        check = load_check()
        files = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        ).stdout.decode().split("\0")
        problems = check.blocked_problems([f for f in files if f])
        self.assertEqual(problems, [], f"blocked terms found: {problems[:5]}")
        targets = [REPORT.read_text(encoding="utf-8")] if REPORT.exists() else []
        targets += [self.pages.get(row["page"], "") for row in self.rows if row["outcome"] == "new"]
        self.assertTrue(targets, "nothing to check")
        hits = [run for text in targets for run in runs(text) if sha(run) in SOURCE_PHRASE_HASHES]
        self.assertEqual(len(hits), 0, f"{len(hits)} source-revealing phrases on new pages or in the report")


if __name__ == "__main__":
    unittest.main()
