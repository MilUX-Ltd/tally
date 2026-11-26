"""Acceptance tests: Spearhead membership in Tally (card 7487).

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for marking the members of Spearhead, a UK SME defence
collective, and adding the ones Tally does not yet list. The published member names
(names only) are in tests/fixtures/spearhead_members_2026.json; the outcome for each is in
reports/spearhead-2026.csv (listed, outcome, page, reason). Do not edit these tests to
make a build pass; raise the problem instead.
"""

import csv
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "spearhead_members_2026.json"
REPORT = ROOT / "reports" / "spearhead-2026.csv"
TAG = "mbr-spearhead"
LABEL = "Spearhead"
LISTED = 67
OUTCOMES = {"new", "matched", "skipped"}
TAGS_BLOCK = re.compile(r"^tags:\n((?:[ \t]+- .*\n?)+)", re.M)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE = re.compile(r"(\+44[\s(]*\d|\b0\d{2,4}[\s-]\d{3,4}[\s-]?\d{3,4}\b)")
PROFILE = re.compile(r"linkedin\.com/in/", re.I)


def page_tags(text):
    match = TAGS_BLOCK.search(text)
    if not match:
        return []
    return [t.strip().strip("'\"") for t in re.findall(r"^[ \t]+- (.+)$", match.group(1), re.M)]


def field(text, key):
    match = re.search(rf"^{key}:[ \t]*(.*)$", text, re.M)
    return match.group(1).strip().strip("'\"") if match else ""


def report_rows():
    if not REPORT.exists():
        return []
    return list(csv.DictReader(REPORT.read_text(encoding="utf-8").splitlines()))


class Spearhead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.listed = json.loads(FIXTURE.read_text(encoding="utf-8"))["members"]
        cls.taxonomy = json.loads((ROOT / "taxonomy.json").read_text(encoding="utf-8"))
        cls.rows = report_rows()
        cls.pages = {}
        for path in sorted((ROOT / "Companies").rglob("*.md")):
            cls.pages[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")

    def test_spearhead_is_a_known_membership(self):
        values = self.taxonomy["facets"]["memberships"]["values"]
        labels = {(v.get("slug") or v.get("value")): v.get("label") for v in values}
        self.assertIn(TAG, labels, f"{TAG} is not a known membership")
        self.assertEqual(labels[TAG], LABEL)
        self.assertIn(f"`{TAG}`", (ROOT / "Taxonomy.md").read_text(encoding="utf-8"), f"Taxonomy.md does not list {TAG}")
        self.assertIn(f"`{TAG}`", (ROOT / "Tagging.md").read_text(encoding="utf-8"), f"Tagging.md does not list {TAG}")

    def test_every_listed_member_is_accounted_for(self):
        self.assertEqual(len(self.listed), LISTED)
        self.assertEqual(len(set(self.listed)), LISTED)
        self.assertTrue(REPORT.exists(), "reports/spearhead-2026.csv is missing")
        by_name = {}
        for row in self.rows:
            self.assertNotIn(row["listed"], by_name, f"{row['listed']} is reported twice")
            by_name[row["listed"]] = row
        extra = set(by_name) - set(self.listed)
        self.assertEqual(extra, set(), f"report names organisations not listed: {sorted(extra)[:5]}")
        problems = []
        for name in self.listed:
            row = by_name.get(name)
            if row is None:
                problems.append((name, "not reported"))
            elif row["outcome"] not in OUTCOMES:
                problems.append((name, f"unknown outcome {row['outcome']}"))
            elif row["outcome"] == "skipped":
                if not row.get("reason", "").strip():
                    problems.append((name, "skipped without a reason"))
            else:
                text = self.pages.get(row["page"])
                if text is None:
                    problems.append((name, f"no page {row['page']}"))
                elif TAG not in page_tags(text):
                    problems.append((name, f"{row['page']} lacks {TAG}"))
        self.assertEqual(problems, [], f"{len(problems)} listed members not accounted for, e.g. {problems[:5]}")

    def test_members_already_in_tally_are_matched_not_duplicated(self):
        matched = [row for row in self.rows if row["outcome"] == "matched"]
        new = [row for row in self.rows if row["outcome"] == "new"]
        self.assertGreaterEqual(len(matched), 30, "fewer than 30 members matched to existing pages")
        pages = [row["page"] for row in matched + new]
        self.assertEqual(len(pages), len(set(pages)), "two listed members point at the same page")
        data = json.loads((ROOT / "tally-data.json").read_text(encoding="utf-8"))
        names = [c["name"] for c in data["companies"]]
        self.assertEqual(len(names), len(set(names)), "tally-data.json has duplicate company names")

    def test_new_pages_are_dated_clean_and_located(self):
        new = sorted({row["page"] for row in self.rows if row["outcome"] == "new"})
        self.assertTrue(new, "no new pages reported")
        bad = []
        for page in new:
            text = self.pages.get(page, "")
            if "defence" not in page_tags(text):
                bad.append((page, "no defence tag"))
            if not re.match(r"^2026-1[12]-\d\d$", field(text, "sources-verified")):
                bad.append((page, "sources-verified not dated November or December 2026"))
            if EMAIL.search(text):
                bad.append((page, "email address"))
            if PHONE.search(text):
                bad.append((page, "phone number"))
            if PROFILE.search(text):
                bad.append((page, "personal LinkedIn profile"))
            if field(text, "uk-region") == "Overseas":
                if not field(text, "country"):
                    bad.append((page, "overseas without a country"))
            elif field(text, "location-source") not in {"website", "companies-house", "town", "region"}:
                bad.append((page, "no location source"))
        self.assertEqual(bad, [], f"{len(bad)} new pages fail, e.g. {bad[:5]}")

    def test_every_tagged_page_is_reported(self):
        reported = {row["page"] for row in self.rows if row["outcome"] in {"matched", "new"}}
        stray = [p for p, text in self.pages.items() if TAG in page_tags(text) and p not in reported]
        self.assertEqual(stray, [], f"{len(stray)} pages carry {TAG} without a report row, e.g. {stray[:5]}")

    def test_viewer_records_match_the_pages(self):
        data = json.loads((ROOT / "tally-data.json").read_text(encoding="utf-8"))
        self.assertEqual(data["count"], len(data["companies"]))
        by_name = {c["name"]: c for c in data["companies"]}
        pages = sorted({row["page"] for row in self.rows if row["outcome"] in {"matched", "new"}})
        self.assertTrue(pages, "no pages reported")
        bad = []
        for page in pages:
            text = self.pages.get(page, "")
            name = field(text, "name") or Path(page).stem
            record = by_name.get(name)
            if record is None:
                bad.append((page, "no record"))
            elif record["tags"] != page_tags(text):
                bad.append((page, "record tags differ from page tags"))
        self.assertEqual(bad, [], f"{len(bad)} reported pages without a matching record, e.g. {bad[:5]}")


if __name__ == "__main__":
    unittest.main()
