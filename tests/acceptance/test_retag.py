"""Acceptance tests: every company re-tagged against the grouped taxonomy.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for the re-tag. Do not edit them to make a build
pass; raise the problem instead.
"""

import csv
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TAGS_BLOCK = re.compile(r"^tags:\n((?:[ \t]+- .*\n?)+)", re.M)


def page_tags(text):
    match = TAGS_BLOCK.search(text)
    if not match:
        return []
    return [t.strip().strip("'\"") for t in re.findall(r"^[ \t]+- (.+)$", match.group(1), re.M)]


def page_name(text, path):
    match = re.search(r"^name:\s*(.+)$", text, re.M)
    return match.group(1).strip().strip("'\"") if match else path.stem


class Retag(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.taxonomy = json.loads((ROOT / "taxonomy.json").read_text(encoding="utf-8"))
        cls.pages = {}
        for path in sorted((ROOT / "Companies").rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            cls.pages[path] = (text, page_tags(text))
        known = set()
        for facet in cls.taxonomy["facets"].values():
            for value in facet["values"]:
                known.add(value.get("slug") or value.get("value"))
        retained = cls.taxonomy.get("retained_unfaceted", {})
        known.update(retained.get("type", []))
        known.update(retained.get("ownership", []))
        known.update({"defence", "listed"})
        cls.known = known

    def test_no_alias_or_removed_tags_on_pages(self):
        aliases = set(self.taxonomy.get("aliases", {}))
        removed = set(self.taxonomy.get("removed_tags", []))
        bad = [(p.name, t) for p, (_, tags) in self.pages.items() for t in tags if t in aliases or t in removed]
        self.assertEqual(bad, [], f"{len(bad)} merged or removed tags remain, e.g. {bad[:5]}")

    def test_every_page_tag_is_known(self):
        bad = [(p.name, t) for p, (_, tags) in self.pages.items() for t in tags if t not in self.known]
        self.assertEqual(bad, [], f"{len(bad)} unknown tags, e.g. {bad[:5]}")

    def test_sub_capabilities_carry_their_parent(self):
        bad = []
        for path, (_, tags) in self.pages.items():
            for tag in tags:
                if "/" in tag and tag.split("/")[0] not in tags:
                    bad.append((path.name, tag))
        self.assertEqual(bad, [], f"{len(bad)} sub-capabilities without parent, e.g. {bad[:5]}")

    def test_viewer_data_matches_pages(self):
        data = json.loads((ROOT / "tally-data.json").read_text(encoding="utf-8"))
        companies = data["companies"]
        self.assertEqual(len(companies), len(self.pages))
        by_name = {c["name"]: c for c in companies}
        mismatched = []
        for path, (text, tags) in self.pages.items():
            record = by_name.get(page_name(text, path))
            if record is None or sorted(record["tags"]) != sorted(tags):
                mismatched.append(path.name)
        self.assertEqual(mismatched, [], f"{len(mismatched)} companies differ, e.g. {mismatched[:5]}")

    def test_added_tags_have_evidence(self):
        report = ROOT / "reports" / "retag-2026-11.csv"
        self.assertTrue(report.exists(), "reports/retag-2026-11.csv is missing")
        by_file = {str(p.relative_to(ROOT)): (text, tags) for p, (text, tags) in self.pages.items()}
        rows = list(csv.DictReader(report.read_text(encoding="utf-8").splitlines()))
        self.assertTrue(rows, "the evidence report is empty")
        for row in rows:
            self.assertIn(row["page"], by_file, f"unknown page {row['page']}")
            text, tags = by_file[row["page"]]
            self.assertIn(row["tag"], tags, f"{row['page']} lacks {row['tag']}")
            self.assertIn(row["phrase"].lower(), text.lower(), f"phrase not found in {row['page']}")


if __name__ == "__main__":
    unittest.main()
