# Tally Guide

How Tally is structured and how to add to it. Follows the per-folder Guide pattern used across the MilUX and Foothold vaults.

## Purpose

A public directory of defence companies for situational awareness of the sector: who is out there, what they do, and how to find them. Public facts only, companies only.

## Structure

```
Tally/
├── CLAUDE.md                  Local scope and boundary (thin; defers to the Argos root file).
├── README.md                  Public-facing front page of the repo.
├── Tally Guide.md             This file.
├── Company Page Template.md   The template for a new company page.
├── Tagging.md                 The tag taxonomy.
└── Companies/                 One page per company, banded A-Z.
    ├── 0-9/
    ├── A-B/
    ├── C-D/
    ├── E-H/
    ├── I-N/
    ├── O-R/
    ├── S-T/
    └── U-Z/
```

The A-Z banding matches `MilUX/CRM/organisations/defence companies/` and Foothold, so the three reconcile easily. If a band grows too large, split it by individual letter later.

## How to add a company

1. Copy `Company Page Template.md` into the band folder that matches the first character of the company name.
2. Name the file after the company, for example `Companies/A-B/ARX Robotics UK Ltd.md`.
3. Fill the frontmatter and sections from public sources only: the company website, its LinkedIn page, the ADS members directory, public news.
4. Tag it per `Tagging.md`. Always include `defence`, a `size-` band, and whatever capability and facet tags apply.
5. Set `sources-verified` to the date you checked, and list the sources used.

## Add discipline

- Public sources only. Never lift content from the private MilUX CRM or from DEVONthink relationship material.
- No people. No named contacts, no personal data.
- Capabilities are what the company says about itself in public. No assessment.
- Date-stamp news. A stale, undated news line is worse than none.
- One company, one page. No relationship context, no opinion.

## Canonical example

`Companies/0-9/4GD.md` is the worked example. Use it as the reference for shape, depth, and tagging.
