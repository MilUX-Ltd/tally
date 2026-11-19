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
5. No tracked text file carries a blocked term. The terms are held only as SHA-256 hashes of
   their lower-case form, the same set tally-site holds in scripts/check-public-terms.mjs, and
   every one-, two- and three-word run of words is checked. To add a term, hash its lower-case
   form and add the hash to BLOCKED_HASHES here and in tally-site.

   Files that already carried a blocked term when the guard was added are held in
   BLOCKED_BASELINE, keyed by the SHA-256 of the file path, with the number of hits allowed.
   Any new file, or any extra hit in a baselined file, fails. Remove an entry once its file is
   clean.
"""

import hashlib
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
WORD = re.compile(r"[a-z0-9-]+")

BLOCKED_HASHES = frozenset(
    {
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
)

# Path hash -> blocked-term hits present when the guard was added (see the docstring).
BLOCKED_BASELINE = {
        "097c3e03d0e9d55cbb13dad55197fd9253c3813a11adfd92f49d1ebd5054f25f": 1,
        "0eee2053d91e935ff18b2678f279206479bb8e4a331f34d14ba62eec9bc062ba": 2,
        "47f7b7af2ead92deb859a7341ed041d3ae06d26b16ae2c0de47c3ef8cc39cc12": 1,
        "684411abe86fd014f899d7f8d292e3a3d304ec200c838c47027fb7942a4b0993": 2,
        "6a0a76598fd49023b72cceaf0ee58fd9feab91103794a79c14e80b32abde1523": 1,
        "7745efbfe4f8153265783aff68c86ffb9360db1cd2256c70677aed87de6cf636": 13,
        "7a5364bc6d4a32856887496595e940bb7977da3df58ec0554adf4d2c6fae711a": 1,
        "8e39553882b4623a507b4716d8cce21849f8ae48ae16912ddd7aa535ee47c264": 8,
        "9055ec7e8f67979a6adb590bc276fc65d2db4c8cc08628282925111a05e22ec2": 30,
        "d1c729171a8e7d4bf6683746587b1eca9ca2c5d105f08cb3b9fb685dae52f586": 1,
        "e964031dadc5fc22f8caeda041445c08f5662ec37759603ddadc157e64f2d184": 2,
        "ef1321500d1487b30baa22b0d9b6347394d543b31da47adcf0da86d3d8f698fc": 2,
}

failures = []


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_blocked(text, hashes=BLOCKED_HASHES):
    """Return (index, words) for every one-, two- or three-word run whose hash is blocked."""
    words = WORD.findall(text.lower())
    hits = []
    for i in range(len(words)):
        for n in (1, 2, 3):
            if i + n <= len(words) and sha256(" ".join(words[i : i + n])) in hashes:
                hits.append((i, n))
    return hits


def blocked_problems(paths):
    """Messages for tracked files carrying more blocked terms than their baseline allows."""
    problems = []
    for path in paths:
        text = read_text(path)
        if not text or "\0" in text:
            continue
        hits = len(find_blocked(text))
        allowed = BLOCKED_BASELINE.get(sha256(path), 0)
        if hits > allowed:
            problems.append(f"{path}: {hits - allowed} blocked term(s)")
    return problems


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
    failures.extend(blocked_problems(files))
    if failures:
        print(f"check.py: {len(failures)} problem(s)")
        for message in failures:
            print(f"  - {message}")
        return 1
    print(f"check.py: all checks pass ({len(files)} tracked files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
