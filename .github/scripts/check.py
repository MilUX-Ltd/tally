#!/usr/bin/env python3
"""check.py: the directory's gate.

Runs on every pull request and on main (.github/workflows/checks.yml), and locally before a
commit:

    python3 .github/scripts/check.py

Standard library only, Python 3.9 or later. Exit 0 when every check passes, 1 otherwise.

1. Nothing local is tracked: a sync tool's index (.context/), Obsidian's per-user state, the
   Obsidian trash, macOS .DS_Store files, database files.
2. Every tracked JSON file parses.
3. No tracked text file carries an absolute home-folder path (/Users/...).
4. No company page carries personal data the gate can see: an email address or a personal
   LinkedIn profile (linkedin.com/in/). Tally is about companies, not people.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

FORBIDDEN = [
    (re.compile(r"(^|/)\.context/"), "a sync tool's local index"),
    (re.compile(r"(^|/)\.obsidian/"), "Obsidian per-user state"),
    (re.compile(r"(^|/)\.trash/"), "the Obsidian trash"),
    (re.compile(r"(^|/)\.DS_Store$"), "a macOS .DS_Store file"),
    (re.compile(r"\.(sqlite|sqlite3|db)$"), "a database file"),
]
HOME_PATH = re.compile(r"/Users/[A-Za-z0-9._-]+/")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PERSONAL_LINKEDIN = re.compile(r"linkedin\.com/in/", re.I)

failures = []


def tracked():
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.decode()
    return [p for p in out.split("\0") if p]


def read_text(path):
    try:
        return (ROOT / path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return None


def main():
    files = tracked()
    for path in files:
        for pattern, what in FORBIDDEN:
            if pattern.search(path):
                failures.append(f"{path}: {what} must not be tracked")
        if path.endswith(".json"):
            try:
                json.loads((ROOT / path).read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                failures.append(f"{path}: not valid JSON ({exc})")
        if path == ".github/scripts/check.py":
            continue
        text = read_text(path)
        if text and HOME_PATH.search(text):
            failures.append(f"{path}: carries an absolute /Users/ path")
        if text and path.startswith("Companies/") and path.endswith(".md"):
            if EMAIL.search(text):
                failures.append(f"{path}: carries an email address (company pages only)")
            if PERSONAL_LINKEDIN.search(text):
                failures.append(f"{path}: links a personal LinkedIn profile (company pages only)")
    if failures:
        print(f"check.py: {len(failures)} problem(s)")
        for message in failures:
            print(f"  - {message}")
        return 1
    print(f"check.py: all checks pass ({len(files)} tracked files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
