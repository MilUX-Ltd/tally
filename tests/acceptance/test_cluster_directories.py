"""Acceptance tests: the companies in two regional defence cluster directories.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for adding the companies listed by the South Central
and Greater Lincolnshire Regional Defence and Security Clusters. Do not edit them
to make a build pass; raise the problem instead.
"""

import csv
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "cluster_directories_2026.json"
REPORT = ROOT / "reports" / "cluster-directories-2026.csv"
TAGS = {
    "South Central RDSC": "mbr-scrdsc",
    "Greater Lincolnshire RDSC": "mbr-glrdsc",
}
OUTCOMES = {"new", "matched", "skipped"}
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


class ClusterDirectories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.listed = json.loads(FIXTURE.read_text(encoding="utf-8"))["directories"]
        cls.taxonomy = json.loads((ROOT / "taxonomy.json").read_text(encoding="utf-8"))
        cls.rows = report_rows()
        cls.pages = {}
        for path in sorted((ROOT / "Companies").rglob("*.md")):
            cls.pages[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")

    def test_memberships_are_known(self):
        values = self.taxonomy["facets"]["memberships"]["values"]
        labels = {(v.get("slug") or v.get("value")): v.get("label") for v in values}
        taxonomy_md = (ROOT / "Taxonomy.md").read_text(encoding="utf-8")
        tagging_md = (ROOT / "Tagging.md").read_text(encoding="utf-8")
        for label, tag in TAGS.items():
            self.assertIn(tag, labels, f"{tag} is not a known membership")
            self.assertEqual(labels[tag], label)
            self.assertIn(f"`{tag}`", taxonomy_md, f"Taxonomy.md does not list {tag}")
            self.assertIn(f"`{tag}`", tagging_md, f"Tagging.md does not list {tag}")

    def test_every_listed_company_is_accounted_for(self):
        self.assertEqual(set(self.listed), set(TAGS))
        self.assertEqual(len(self.listed["South Central RDSC"]), 230)
        self.assertEqual(len(self.listed["Greater Lincolnshire RDSC"]), 119)
        self.assertTrue(REPORT.exists(), "reports/cluster-directories-2026.csv is missing")
        by_key = {}
        for row in self.rows:
            key = (row["directory"], row["listed"])
            self.assertNotIn(key, by_key, f"{key} is reported twice")
            by_key[key] = row
        problems = []
        for directory, names in self.listed.items():
            tag = TAGS[directory]
            for name in names:
                row = by_key.get((directory, name))
                if row is None:
                    problems.append((directory, name, "not reported"))
                elif row["outcome"] in {"matched", "new"}:
                    text = self.pages.get(row["page"])
                    if text is None:
                        problems.append((directory, name, f"no page {row['page']}"))
                    elif tag not in page_tags(text):
                        problems.append((directory, name, f"{row['page']} lacks {tag}"))
                elif row["outcome"] == "skipped":
                    if not row.get("reason", "").strip():
                        problems.append((directory, name, "skipped without a reason"))
                else:
                    problems.append((directory, name, f"unknown outcome {row['outcome']}"))
        extra = {k for k in by_key if k[0] not in self.listed or k[1] not in self.listed[k[0]]}
        self.assertEqual(extra, set(), f"report names companies not listed: {sorted(extra)[:5]}")
        self.assertEqual(problems, [], f"{len(problems)} listed companies not accounted for, e.g. {problems[:5]}")

    def test_new_pages_are_dated_clean_and_located(self):
        new = sorted({row["page"] for row in self.rows if row["outcome"] == "new"})
        self.assertTrue(new, "no new pages reported")
        bad = []
        for page in new:
            text = self.pages.get(page, "")
            if "defence" not in page_tags(text):
                bad.append((page, "no defence tag"))
            if not field(text, "sources-verified").startswith("2026-11"):
                bad.append((page, "sources-verified not 2026-11"))
            if EMAIL.search(text):
                bad.append((page, "email address"))
            if PHONE.search(text):
                bad.append((page, "phone number"))
            if field(text, "uk-region") == "Overseas":
                if not field(text, "country"):
                    bad.append((page, "overseas without a country"))
            elif field(text, "location-source") not in {"website", "companies-house", "town", "region"}:
                bad.append((page, "no location source"))
        self.assertEqual(bad, [], f"{len(bad)} new pages fail, e.g. {bad[:5]}")

    def test_every_tagged_page_is_listed(self):
        stray = []
        for directory, tag in TAGS.items():
            reported = {
                row["page"]
                for row in self.rows
                if row["directory"] == directory and row["outcome"] in {"matched", "new"}
            }
            stray += [(tag, p) for p, text in self.pages.items() if tag in page_tags(text) and p not in reported]
        self.assertEqual(stray, [], f"{len(stray)} pages carry a cluster tag without a report row, e.g. {stray[:5]}")

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
