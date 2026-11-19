"""Acceptance tests: the Defence Wales companies in Tally.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for adding the Defence Wales companies. Do not edit
them to make a build pass; raise the problem instead.
"""

import csv
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "defence_wales_companies_2026.json"
REPORT = ROOT / "reports" / "defence-wales-2026.csv"
TAG = "mbr-walesdsc"
TAGS_BLOCK = re.compile(r"^tags:\n((?:[ \t]+- .*\n?)+)", re.M)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE = re.compile(r"(\+44[\s(]*\d|\b0\d{2,4}[\s-]\d{3,4}[\s-]?\d{3,4}\b)")


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


class DefenceWales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.listed = json.loads(FIXTURE.read_text(encoding="utf-8"))["companies"]
        cls.taxonomy = json.loads((ROOT / "taxonomy.json").read_text(encoding="utf-8"))
        cls.rows = report_rows()
        cls.pages = {}
        for path in sorted((ROOT / "Companies").rglob("*.md")):
            cls.pages[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")

    def test_membership_is_known(self):
        values = self.taxonomy["facets"]["memberships"]["values"]
        labels = {(v.get("slug") or v.get("value")): v.get("label") for v in values}
        self.assertIn(TAG, labels, f"{TAG} is not a known membership")
        self.assertEqual(labels[TAG], "Defence Wales")
        text = (ROOT / "Taxonomy.md").read_text(encoding="utf-8")
        self.assertIn(f"`{TAG}`", text, f"Taxonomy.md does not list {TAG}")

    def test_every_listed_company_is_accounted_for(self):
        self.assertEqual(len(self.listed), 78)
        self.assertTrue(REPORT.exists(), "reports/defence-wales-2026.csv is missing")
        by_listed = {}
        for row in self.rows:
            self.assertNotIn(row["listed"], by_listed, f"{row['listed']} is reported twice")
            by_listed[row["listed"]] = row
        problems = []
        for name in self.listed:
            row = by_listed.get(name)
            if row is None:
                problems.append((name, "not reported"))
            elif row["status"] in {"existing", "new"}:
                text = self.pages.get(row["page"])
                if text is None:
                    problems.append((name, f"no page {row['page']}"))
                elif TAG not in page_tags(text):
                    problems.append((name, f"{row['page']} lacks {TAG}"))
            elif row["status"] == "skipped":
                if not row.get("reason", "").strip():
                    problems.append((name, "skipped without a reason"))
            else:
                problems.append((name, f"unknown status {row['status']}"))
        extra = set(by_listed) - set(self.listed)
        self.assertEqual(extra, set(), f"report names companies not on the list: {sorted(extra)[:5]}")
        self.assertEqual(problems, [], f"{len(problems)} listed companies not accounted for, e.g. {problems[:5]}")

    def test_new_pages_are_dated_and_clean(self):
        new = [row for row in self.rows if row["status"] == "new"]
        self.assertTrue(new, "no new pages reported")
        bad = []
        for row in new:
            text = self.pages.get(row["page"], "")
            if "defence" not in page_tags(text):
                bad.append((row["page"], "no defence tag"))
            if not field(text, "sources-verified").startswith("2026-11"):
                bad.append((row["page"], "sources-verified not 2026-11"))
            if EMAIL.search(text):
                bad.append((row["page"], "email address"))
            if PHONE.search(text):
                bad.append((row["page"], "phone number"))
        self.assertEqual(bad, [], f"{len(bad)} new pages fail, e.g. {bad[:5]}")

    def test_every_tagged_page_is_listed(self):
        reported = {row["page"] for row in self.rows if row["status"] in {"existing", "new"}}
        stray = [p for p, text in self.pages.items() if TAG in page_tags(text) and p not in reported]
        self.assertEqual(stray, [], f"{len(stray)} pages carry {TAG} without a report row, e.g. {stray[:5]}")

    def test_viewer_records_carry_the_membership(self):
        data = json.loads((ROOT / "tally-data.json").read_text(encoding="utf-8"))
        self.assertEqual(data["count"], len(data["companies"]))
        by_name = {c["name"]: c for c in data["companies"]}
        rows = [row for row in self.rows if row["status"] in {"existing", "new"}]
        self.assertTrue(rows, "no pages reported")
        bad = []
        for row in rows:
            text = self.pages.get(row["page"], "")
            name = field(text, "name") or Path(row["page"]).stem
            record = by_name.get(name)
            if record is None or TAG not in record["tags"]:
                bad.append(row["page"])
        self.assertEqual(bad, [], f"{len(bad)} reported pages without a record carrying {TAG}, e.g. {bad[:5]}")


if __name__ == "__main__":
    unittest.main()
