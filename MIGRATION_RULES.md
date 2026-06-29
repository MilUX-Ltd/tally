# Tally Migration Rules

## Curation filter
INCLUDE: genuine defence product, capability, or service. Foreign HQs ok — set owned-foreign.
SKIP: recruiters, law firms, accountants, generic management consultants, generic IT resellers, media/PR, events, trade bodies, universities, councils, pure investors, individuals, dissolved companies.
SET ASIDE: large general IT/consulting firms where defence relevance is unclear (e.g. Fujitsu, IBM, Oracle, Google DeepMind, Experian, Big Four, Cognizant, Deloitte).

## Hard rules
- British English. NO em-dashes. Use commas, full stops, or semicolons.
- Public sources only. No named individuals; no /in/ LinkedIn URLs; no emails or phone numbers.
- Omit unconfirmed facts. Sparse and correct beats complete and guessed.
- sources-verified: use today's date (YYYY-MM-DD).
- Recent news: omit any item missing BOTH a specific date AND a source URL.
- Frameworks section: omit entirely if nothing confirmed. Never write "Not publicly confirmed."
- Both `size: X` in frontmatter AND `size-X` in tags must be present.
- LinkedIn must be /company/ URL, never /in/.
- uk-region: use full region name (e.g. Greater London, not London; South West England, not South West).

## Size bands
micro <10 | small 10-49 | medium 50-249 | large 250+

## File band by first character of company name
0-9 → Companies/0-9/
A-B → Companies/A-B/
C-D → Companies/C-D/
E-H → Companies/E-H/
I-N → Companies/I-N/
O-R → Companies/O-R/
S-T → Companies/S-T/
U-Z → Companies/U-Z/

Full path: /Users/matt/Argos/Obsidian Vaults/Tally/Companies/<band>/<Company Name>.md

## Template
```
---
type: organisation
name: 
website: 
linkedin: 
companies-house: 
hq: 
uk-region: 
founded: 
size: 
headcount: 
sources-verified: 
tags:
  - defence
  - [capability tags]
  - size-[band]
  - [prefixed tags]
---
# Name
> One-line description.
## What they do
2-3 sentences.
## Products and solutions
- **Product** - description.
## Frameworks, accreditations and memberships
- **Frameworks:** ...
- **Accreditations:** ...
- **Memberships:** ...
## Recent news
- **YYYY-MM-DD** - summary. [source](url)
## Links
- Website: 
- LinkedIn: 
## Sources
Public information verified YYYY-MM-DD.
```

## Capability tags (bare, only from this list)
ai, cyber, drones, uas, counter-uas, comms, isr, c2, ew, autonomy, robotics, simulation, training, sensors, optronics, rf, space, maritime, land, air, logistics, munitions, data, software, hardware, manufacturing, gis, quantum, test-evaluation

## Prefixed tags (evidence required)
size-micro/small/medium/large
type-prime/sme/startup/scaleup/consultancy/manufacturer/integrator/academia/investor
owned-uk/foreign/veteran/founder | backed-vc/pe | listed
fw-joscar/gcloud/dos/ccs
accr-ce/ce-plus/iso9001/iso27001/iso14001/listx
prog-dasa/diana/nssif
mbr-ads/techuk/makeuk-defence/ndi/scrdsc/swrdsc
