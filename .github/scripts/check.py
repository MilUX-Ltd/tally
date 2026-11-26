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
6. Every certification check a company page records (`certification-checks` in its
   frontmatter, see the company page template) is well formed: a list of checks, each with an
   `accreditation` the page carries in its tags and taxonomy.json knows, a plain-text
   `register` of 2 to 80 characters, a real `checked` date (YYYY-MM-DD) that is not in the
   future (UTC), and optionally an https `link`; no other keys, and one check per
   accreditation. The register may not carry negative or status wording (not, none, expired,
   revoked, found and the like). The block must be written exactly as in the template: the key
   alone on its line and once only, two-space list items, plain or simply quoted values, and no
   comments, block scalars, flow style, anchors, tags or backslashes, so a YAML reader cannot
   see a check the gate did not read.
7. countries.json keeps to its contract (docs/countries-data.md), and every company page
   carries a country-code it knows: GB for a UK page, whose region is one of the UK's regions;
   a country that is not live has region Overseas. Russia is never live and no page is in
   Russia; Belarus and Russia are never in the Europe bloc.
8. A Norwegian company page that carries `brreg` carries a valid Norwegian organisation number
   (nine digits, modulus 11 check digit). See docs/norway-data.md.
"""

import datetime
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

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.S)
CHECKS_KEY = "certification-checks:"
CHECK_KEYS = ("accreditation", "register", "checked", "link")
# The one form the gate accepts, as in the company page template: the key alone
# on its line, each check starting "  - key: value" and its other fields
# "    key: value". Anything else is refused, so a YAML reader can never see a
# check the gate did not read.
CHECK_ITEM = re.compile(r"^  - ([a-z]+):(?: (.*))?$")
CHECK_FIELD = re.compile(r"^    ([a-z]+):(?: (.*))?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HTTPS = re.compile(r"^https://[^\s<>\"\\]+$", re.I)
# Negative or status wording a register name may not carry. The same list is in
# tally-site's scripts/fetch-data.mjs; keep them alike.
REGISTER_DENIED = re.compile(
    r"\b(?:not|no|none|unverified|unconfirmed|uncertified|expired|revoked|lapsed|withdrawn|suspended|"
    r"fail|failed|failure|invalid|removed|found|missing|cancelled|canceled)\b|n['’]t\b",
    re.I,
)


def _frontmatter(text):
    match = FRONTMATTER.match(text.replace("\r\n", "\n"))
    return match.group(1) if match else ""


def _unquote(value):
    """A YAML plain or quoted scalar's text. Single-quoted '' is one quote."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _value_problem(raw):
    """Why a raw value is outside the canonical form, or None."""
    value = (raw or "").strip()
    if "\\" in value:
        return "must not contain a backslash"
    if re.search(r"(^|\s)#", value):
        return "must not carry a comment"
    if value[:1] in ("[", "{"):
        return "must not use flow style"
    if re.match(r"^[|>][-+0-9]*$", value):
        return "must not be a block scalar"
    if value[:1] in ("&", "*", "!", "%", "@", "`", "?"):
        return "must not start with an anchor, alias, tag or reserved character"
    if value[:1] == "'":
        inner = value[1:-1] if len(value) >= 2 and value[-1] == "'" else None
        if inner is None or "'" in inner.replace("''", ""):
            return "has broken single quotes"
    elif value[:1] == '"':
        inner = value[1:-1] if len(value) >= 2 and value[-1] == '"' else None
        if inner is None or '"' in inner:
            return "has broken double quotes"
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in value):
        return "must not contain control characters"
    return None


def frontmatter_name(text):
    """The page's frontmatter name, or an empty string."""
    match = re.search(r"^name:[ \t]*(.+)$", _frontmatter(text), re.M)
    return _unquote(match.group(1)) if match else ""


def _page_tags(meta):
    match = re.search(r"^tags:[ \t]*\n((?:[ \t]+- .*\n?)+)", meta, re.M)
    if not match:
        return set()
    return {_unquote(t) for t in re.findall(r"^[ \t]+- (.+)$", match.group(1), re.M)}


def _parse_checks(text):
    """(checks, problems) from the certification-checks block; checks is [] when there is none."""
    lines = _frontmatter(text).split("\n")
    mentions = [i for i, line in enumerate(lines) if "certification-checks" in line.lower()]
    problems = []
    for i in mentions:
        if lines[i] != CHECKS_KEY:
            problems.append(f"write the key exactly as '{CHECKS_KEY}' on its own line, not {lines[i].strip()[:40]!r}")
    keys = [i for i in mentions if lines[i] == CHECKS_KEY]
    if len(mentions) > 1:
        problems.append("certification-checks appears more than once")
    if not keys:
        return [], problems
    checks = []
    for line in lines[keys[0] + 1 :]:
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            problems.append("certification-checks must not contain comment lines")
            continue
        if not line[0].isspace():
            break
        item, field = CHECK_ITEM.match(line), CHECK_FIELD.match(line)
        match = item or field
        if not match:
            problems.append(f"certification-checks is not in the template's form: {line.strip()[:40]}")
            continue
        key, raw = match.group(1), match.group(2) or ""
        trouble = _value_problem(raw)
        if trouble:
            problems.append(f"certification check {key} {trouble}")
        if item:
            checks.append({key: _unquote(raw)})
        elif checks:
            if key in checks[-1]:
                problems.append(f"certification check repeats {key}")
            checks[-1][key] = _unquote(raw)
        else:
            problems.append(f"certification-checks is not a list of checks: {line.strip()[:40]}")
    if not checks:
        problems.append("certification-checks must list at least one check, or be left out")
    return checks, problems


def certification_checks(text):
    """The certification checks a company page records, as dicts of their fields."""
    return _parse_checks(text)[0]


def certification_check_problems(text, accreditations):
    """Problems with a page's certification checks, given the accreditation slugs taxonomy.json knows."""
    checks, problems = _parse_checks(text)
    tags = _page_tags(_frontmatter(text))
    seen = set()
    today = datetime.datetime.now(datetime.timezone.utc).date()
    for check in checks:
        accr = check.get("accreditation", "")
        label = accr or "a check"
        extra = sorted(set(check) - set(CHECK_KEYS))
        if extra:
            problems.append(f"{label}: unknown key(s) {', '.join(extra)}")
        if not accr.startswith("accr-") or accr not in accreditations:
            problems.append(f"{label}: not an accreditation taxonomy.json knows")
        elif accr not in tags:
            problems.append(f"{label}: the page does not carry this accreditation in its tags")
        if accr in seen:
            problems.append(f"{label}: checked more than once")
        seen.add(accr)
        register = check.get("register", "")
        if not 2 <= len(register) <= 80:
            problems.append(f"{label}: register must be 2 to 80 characters")
        if "://" in register or "www." in register.lower() or any(ord(c) < 0x20 or ord(c) == 0x7F for c in register):
            problems.append(f"{label}: register must be plain text, without a link")
        if REGISTER_DENIED.search(register):
            problems.append(f"{label}: register must name the register only, without negative or status wording")
        checked = check.get("checked", "")
        try:
            if not DATE.match(checked):
                raise ValueError
            date = datetime.date.fromisoformat(checked)
            if date > today:
                problems.append(f"{label}: checked date is in the future (UTC)")
        except ValueError:
            problems.append(f"{label}: checked must be a real date, YYYY-MM-DD")
        link = check.get("link", "")
        if link and not HTTPS.match(link):
            problems.append(f"{label}: link must be an https address")
    return problems


def known_accreditations():
    taxonomy = json.loads((ROOT / "taxonomy.json").read_text(encoding="utf-8"))
    return {v["slug"] for v in taxonomy["facets"]["accreditations"]["values"]}


COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
COUNTRY_BLOCS = {"europe", "north-america", "other"}
COUNTRY_KEYS = {"code", "name", "aliases", "bloc", "live", "bounds", "regions"}
NEVER_LIVE = {"RU"}
NEVER_EUROPE = {"BY", "RU"}


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def countries_problems(data):
    """Problems with countries.json: its shape, its live countries, and Russia never live."""
    problems = []
    if not isinstance(data, dict) or not isinstance(data.get("countries"), list):
        return ["countries.json: needs a countries list"]
    extra = set(data) - {"generated", "note", "countries"}
    if extra:
        problems.append(f"countries.json: unknown keys {sorted(extra)}")
    seen = set()
    for i, c in enumerate(data["countries"]):
        if not isinstance(c, dict):
            problems.append(f"countries.json: entry {i} is not an object")
            continue
        code = c.get("code")
        label = f"countries.json: {code if isinstance(code, str) else f'entry {i}'}"
        if set(c) - COUNTRY_KEYS:
            problems.append(f"{label}: unknown keys {sorted(set(c) - COUNTRY_KEYS)}")
        if not isinstance(code, str) or not COUNTRY_CODE.match(code):
            problems.append(f"{label}: code must be two upper-case letters")
        elif code in seen:
            problems.append(f"{label}: code appears twice")
        seen.add(code)
        name = c.get("name")
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 60:
            problems.append(f"{label}: name must be 2 to 60 characters")
        aliases = c.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() for a in aliases):
            problems.append(f"{label}: aliases must be a list of names")
        if c.get("bloc") not in COUNTRY_BLOCS:
            problems.append(f"{label}: bloc must be one of {sorted(COUNTRY_BLOCS)}")
        if code in NEVER_EUROPE and c.get("bloc") == "europe":
            problems.append(f"{label}: is not in Europe as decided")
        live = c.get("live")
        if not isinstance(live, bool):
            problems.append(f"{label}: live must be true or false")
            continue
        if live and code in NEVER_LIVE:
            problems.append(f"{label}: is never live on Tally")
        if live:
            bounds = c.get("bounds")
            if not (isinstance(bounds, list) and len(bounds) == 4 and all(_is_number(b) for b in bounds)
                    and -180 <= bounds[0] < bounds[2] <= 180 and -90 <= bounds[1] < bounds[3] <= 90):
                problems.append(f"{label}: a live country needs bounds [west, south, east, north]")
            regions = c.get("regions")
            if not (isinstance(regions, list) and regions and all(isinstance(r, str) and r.strip() for r in regions)
                    and len(regions) == len(set(regions))):
                problems.append(f"{label}: a live country needs a list of regions without repeats")
    return problems


def country_problems(text, countries):
    """Problems with a company page's country-code and region, against countries.json."""
    head = _frontmatter(text)
    def field(key):
        match = re.search(rf"^{key}:[ \t]*(.*)$", head, re.M)
        return _unquote(match.group(1)) if match else ""
    code = field("country-code")
    if not code:
        return ["needs a country-code"]
    if not COUNTRY_CODE.match(code):
        return [f"country-code {code!r} must be two upper-case letters"]
    if code in NEVER_LIVE:
        return [f"country-code {code} is never listed on Tally"]
    known = {c.get("code"): c for c in countries.get("countries", []) if isinstance(c, dict)}
    entry = known.get(code)
    if not entry:
        return [f"country-code {code} is not in countries.json"]
    region = field("region") or field("uk-region")
    if entry.get("live"):
        if region and region not in entry.get("regions", []):
            return [f"region {region!r} is not a region of {code}"]
    elif region != "Overseas":
        return [f"{code} is not live, so its region must be Overseas"]
    return []


ORG_WEIGHTS = (3, 2, 7, 6, 5, 4, 3, 2)


def org_number_valid(value):
    """A Norwegian organisation number: nine digits, the last a modulus 11 check digit."""
    if not re.fullmatch(r"\d{9}", value or ""):
        return False
    remainder = sum(int(d) * w for d, w in zip(value[:8], ORG_WEIGHTS)) % 11
    check = 0 if remainder == 0 else 11 - remainder
    return check != 10 and check == int(value[8])


def register_problems(text):
    """A Norwegian company page names its entry in the Norwegian register with a valid number."""
    head = _frontmatter(text)
    code = re.search(r"^country-code:[ \t]*(.*)$", head, re.M)
    if not code or _unquote(code.group(1)) != "NO":
        return []
    number = re.search(r"^brreg:[ \t]*(.*)$", head, re.M)
    if not number:
        return ["a Norwegian company needs its organisation number as brreg"]
    if not org_number_valid(_unquote(number.group(1))):
        return [f"brreg {_unquote(number.group(1))!r} is not a valid Norwegian organisation number"]
    return []


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
    accreditations = known_accreditations()
    try:
        countries = json.loads((ROOT / "countries.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        countries = {"countries": []}
        failures.append(f"countries.json: cannot be read ({exc})")
    failures.extend(countries_problems(countries))
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
            for problem in certification_check_problems(text, accreditations):
                failures.append(f"{path}: {problem}")
            for problem in country_problems(text, countries):
                failures.append(f"{path}: {problem}")
            # Every Norwegian page that names a register entry must name it correctly. That every
            # Norwegian page names one is held by tests/acceptance/test_norway.py from the first load.
            if re.search(r"^brreg:", _frontmatter(text), re.M):
                for problem in register_problems(text):
                    failures.append(f"{path}: {problem}")
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
