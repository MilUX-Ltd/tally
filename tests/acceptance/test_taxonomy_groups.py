"""Acceptance tests: the grouped capability taxonomy.

Standard library only. Run with:

    python3 -m unittest discover -s tests -t .

These tests are the contract for the grouped taxonomy. Do not edit them to make
a build pass; raise the problem instead.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class GroupedTaxonomy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.taxonomy = load(ROOT / "taxonomy.json")
        cls.capability = cls.taxonomy["facets"]["capability"]
        cls.values = cls.capability["values"]
        cls.slugs = {v["slug"] for v in cls.values}
        cls.groups = cls.capability.get("groups", [])
        cls.group_slugs = {g.get("slug") for g in cls.groups}

    def test_every_capability_has_a_declared_group(self):
        self.assertTrue(self.groups, "facets.capability.groups is missing or empty")
        for group in self.groups:
            for key in ("slug", "label", "order"):
                self.assertIn(key, group, f"group {group} lacks {key}")
        for value in self.values:
            self.assertIn("group", value, f"{value['slug']} has no group")
            self.assertIn(value["group"], self.group_slugs, f"{value['slug']} names an undeclared group")

    def test_groups_are_balanced(self):
        self.assertGreaterEqual(len(self.groups), 6)
        self.assertLessEqual(len(self.groups), 10)
        for group in self.groups:
            members = [v for v in self.values if v.get("group") == group["slug"]]
            self.assertGreaterEqual(len(members), 1, f"group {group['slug']} is empty")
            self.assertLessEqual(len(members), 30, f"group {group['slug']} holds {len(members)}")

    def test_every_matrix_column_maps_to_a_capability(self):
        columns = load(FIXTURES / "defence_wales_matrix_2026.json")["columns"]
        matrix_map = self.capability.get("matrix_map", {})
        for column in columns:
            self.assertIn(column, matrix_map, f"matrix column '{column}' has no mapping")
            self.assertIn(matrix_map[column], self.slugs, f"'{column}' maps to unknown slug {matrix_map[column]}")

    def test_no_existing_capability_is_orphaned(self):
        old = load(FIXTURES / "capability_slugs_2026_07.json")["slugs"]
        aliases = self.taxonomy.get("aliases", {})
        for slug in old:
            if slug in self.slugs:
                continue
            self.assertIn(slug, aliases, f"existing slug {slug} was removed without an alias")
            self.assertIn(aliases[slug], self.slugs, f"{slug} aliases to unknown slug {aliases[slug]}")

    def test_slugs_and_labels_are_clean(self):
        seen = set()
        for value in self.values:
            slug, label = value["slug"], value.get("label", "")
            self.assertNotIn(slug, seen, f"duplicate slug {slug}")
            seen.add(slug)
            self.assertRegex(slug, r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)?$")
            self.assertTrue(label.strip(), f"{slug} has an empty label")
            self.assertNotIn("—", label, f"{slug} label uses an em dash")
        for group in self.groups:
            self.assertNotIn("—", group["label"])
            self.assertNotRegex(group["label"], r"(?i)\b(defense|organization|center)\b")

    def test_taxonomy_md_mirrors_the_groups(self):
        self.assertTrue(self.groups, "no groups declared, so Taxonomy.md cannot mirror them")
        text = (ROOT / "Taxonomy.md").read_text(encoding="utf-8")
        headings = [(m.start(), m.group(1).strip()) for m in re.finditer(r"^#{2,4} (.+)$", text, re.M)]
        for group in self.groups:
            starts = [pos for pos, title in headings if title == group["label"]]
            self.assertTrue(starts, f"Taxonomy.md has no heading '{group['label']}'")
            start = starts[0]
            following = [pos for pos, _ in headings if pos > start]
            end = min(following) if following else len(text)
            section = text[start:end]
            for value in self.values:
                if value.get("group") == group["slug"]:
                    self.assertIn(f"`{value['slug']}`", section, f"{value['slug']} not under '{group['label']}'")


if __name__ == "__main__":
    unittest.main()
