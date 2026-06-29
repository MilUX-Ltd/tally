# Tally (local vault CLAUDE.md)

Tally is a public, read-only directory of defence companies. The name is the air-combat brevity call for "I have visual", a nod to the air domain alongside the land-specific Foothold. It is a derivative deliverable consumed by Foothold users and anyone who wants situational awareness of who is in the defence sector. Public repo: `github.com/milux-ltd/tally`.

This file is deliberately thin. The cross-vault architecture, the agent write boundaries, the tool roles, and the communication preferences all live in the parent file at `/Users/matt/Argos/CLAUDE.md`. Read that first. The full initiative brief is `MilUX/Initiatives/active/tally/tally.md`.

## Scope

In:

- Defence companies, one markdown page each, under `Companies/` (banded A-Z, matching MilUX and Foothold).
- Public facts only: what the company does, its capabilities, company website and company LinkedIn page, frameworks, accreditations, company size, location, and a dated recent-news summary.

Out:

- People. Tally is about companies, not individuals. No named contacts, no personal LinkedIn profiles, no emails or phone numbers.
- Any relationship state, deal data, opinion, or assessment. Tally is not a CRM.

## Data-handling boundary (read before editing)

- Build only from public sources. Never seed Tally from the private MilUX CRM or DEVONthink relationship content.
- No personal data of any kind. Company-level information and company-level links only.
- Keep capability text to what a company publicly states about itself, to stay clear of export-control sensitivity.
- No `obsidian://` or path links from a Tally page back into any private vault. The link is one-directional: a private MilUX page may link out to its Tally mirror, never the reverse.

## Structure and conventions

- Company pages: `Companies/<band>/<Company Name>.md`. Use the band that matches the first character of the company name.
- New pages follow `Company Page Template.md`.
- Tagging follows `Tagging.md`. Relationship tags are excluded by design.
- Canonical example: `Companies/0-9/4GD.md`.

## Sync

- Obsidian Sync across the two MacBook Airs.
- Standard git push to the public repo `github.com/milux-ltd/tally`. No four-hourly job.
- Not pushed to the Mac Mini or NUC.

## Scheduled tasks

None yet. A freshness-refresh task (Bob researches news into Notion, Matt or Argos promote into Tally) is proposed in the initiative brief and not yet built.

Parent: `/Users/matt/Argos/CLAUDE.md`.
