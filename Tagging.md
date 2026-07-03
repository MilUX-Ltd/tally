# Tally Tagging

How tags work in Tally. Tags carry the facets the search viewer filters on, so consistency matters more here than anywhere.

## Principles

1. **Public fact only.** Every tag describes something publicly verifiable about the company. No relationship tags. The MilUX relationship tags (`client`, `partner`, `prospect`, and the rest) describe MilUX's private position and never appear in Tally.
2. **Lowercase kebab-case.** Multi-word tags are hyphenated.
3. **Capability tags are bare at the top level; capability subsets nest with a slash (`parent/child`); other facets carry a short prefix** so everything groups cleanly in the tag pane and in search.
4. **Additive.** New tags can be introduced, but document them here first and reuse consistently.

## Capability and domain (bare)

`defence` always, plus what applies:

`ai`, `cyber`, `drones`, `uas`, `counter-uas`, `comms`, `isr`, `c2`, `ew`, `autonomy`, `robotics`, `simulation`, `training`, `sensors`, `optronics`, `rf`, `space`, `maritime`, `land`, `air`, `logistics`, `munitions`, `data`, `software`, `hardware`, `manufacturing`, `gis`, `quantum`, `test-evaluation`, `human-factors`.

## Capability subsets (`parent/child`, v2)

The top-level capability tags above are coarse. A single `cyber` bucket cannot tell a buyer whether a company does pen testing or governance, so the broad, high-traffic buckets carry a second tier of subsets. A company keeps its top-level tag and adds one or more subsets beneath it: a page tagged `cyber/pen-testing` also carries `cyber`, so coarse search stays complete.

Subsets are native Obsidian nested tags, so they group under their parent automatically, and the viewer picks them up as capabilities with no code change. Assign a subset only where the company's own public text supports it; leave the parent bare where it does not.

**cyber:** `cyber/pen-testing`, `cyber/red-team`, `cyber/soc-monitoring`, `cyber/incident-response`, `cyber/threat-intel`, `cyber/digital-forensics`, `cyber/vuln-management`, `cyber/idam`, `cyber/grc`, `cyber/encryption`, `cyber/cross-domain`, `cyber/ot-security`.

**ai:** `ai/ml-analytics`, `ai/computer-vision`, `ai/nlp`, `ai/decision-support`, `ai/generative`.

**isr:** `isr/geoint`, `isr/sigint`, `isr/imint`, `isr/osint`, `isr/fusion`, `isr/ped`.

**comms:** `comms/tactical-radio`, `comms/satcom`, `comms/waveforms`, `comms/networking`, `comms/secure-voice`.

**c2:** `c2/battle-management`, `c2/mission-planning`, `c2/situational-awareness`, `c2/targeting`, `c2/integration`.

**ew:** `ew/elint`, `ew/ecm`, `ew/eccm`, `ew/direction-finding`, `ew/spectrum-management`.

**autonomy:** `autonomy/navigation`, `autonomy/swarming`, `autonomy/uxv-control`, `autonomy/eod-robotics`.

**drones / uas / counter-uas:** `uas/platform`, `uas/payload`, `counter-uas/detection`, `counter-uas/effector`.

**data:** `data/analytics`, `data/engineering`, `data/visualisation`, `data/labelling`.

**simulation / training:** `simulation/synthetic-environment`, `simulation/lvc`, `training/courseware`, `training/instruction`.

**sensors / optronics:** `sensors/eo-ir`, `sensors/radar`, `sensors/acoustic-sonar`, `sensors/pnt`.

The domain facets (`land`, `air`, `maritime`, `space`) and the make facets (`manufacturing`, `hardware`, `software`, `munitions`, `logistics`, `rf`, `quantum`, `gis`, `robotics`) stay flat. A company is in a domain, it does not have it as a component.

## Company size (`size-`)

`size-micro`, `size-small`, `size-medium`, `size-large`.

A priority facet. A specific aim of Tally is to surface micro and small businesses, so size must be filterable. Record the actual `headcount` in frontmatter where it can be found publicly; the tag is the band for filtering.

## Organisation type (`type-`)

`type-prime`, `type-sme`, `type-startup`, `type-scaleup`, `type-consultancy`, `type-manufacturer`, `type-integrator`, `type-academia`, `type-non-profit`, `type-investor`.

## Ownership and funding (`owned-` / `backed-`)

`owned-veteran`, `owned-uk`, `owned-foreign`, `owned-founder`, `backed-vc`, `backed-pe`, `listed`.

## Sovereignty and supply chain (`sov-`, documented, not yet populated)

A distinctive facet almost no directory carries: where a company designs, builds and delivers, beyond who owns it. Scoped hard to public fact, Companies House ownership and the company's own public statements. Where a value cannot be verified from those, leave it untagged rather than inferred.

`sov-uk-designed`, `sov-uk-manufactured`, `sov-uk-delivered`, `sov-offshore-delivery`, `sov-foreign-parent`, `sov-sovereign-claim` (self-description, not a Tally endorsement).

Not yet populated. Two prerequisites first: the viewer needs a `sov-` facet added (and `sov-` excluded from the capability test, or these tags will show as capabilities), and a sourcing pass against Companies House. Held as a separate piece of work.

## Frameworks (`fw-`)

The procurement vehicles a company sits on. The facet that makes the directory worth searching.

`fw-joscar` (Hellios JOSCAR register), `fw-gcloud` (CCS G-Cloud), `fw-dos` (Digital Outcomes and Specialists), `fw-ccs` (other Crown Commercial Service framework), plus named MOD frameworks as they appear.

## Accreditations and standards (`accr-`)

`accr-ce` (Cyber Essentials), `accr-ce-plus` (Cyber Essentials Plus), `accr-iso9001`, `accr-iso27001`, `accr-iso14001`, `accr-listx` (List X facility), `accr-def-stan`, `accr-itar`.

## Programmes and accelerators (`prog-`)

`prog-dasa` (DASA-funded), `prog-diana` (NATO DIANA), `prog-nssif` (NSSIF-backed), `prog-spark`.

## Memberships and clusters (`mbr-`)

`mbr-ads` (ADS Group), `mbr-techuk`, `mbr-makeuk-defence`, `mbr-ndi`, `mbr-scrdsc`, `mbr-swrdsc`, and other regional clusters as encountered.

## Location for filtering

Location is held in frontmatter (`hq`, `uk-region`), not as a tag, so the viewer can filter by region (for example, an additive-manufacturing SME in Hampshire). Keep `uk-region` values consistent.
