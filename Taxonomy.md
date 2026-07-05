# Tally tag taxonomy

_Authoritative controlled vocabulary. Generated 2026-07-05. Source of truth is `taxonomy.json`; this file is the human-readable mirror. The build (`bin/tally-build-web.py`) reads `taxonomy.json` to label the viewer facets and to validate tags._

The directory filters on six facets only: **Capability, Size, Region, Framework, Accreditation, Membership**. Type and ownership tags are retained on records but not shown as filters. Programme tags have been removed entirely.

## Framework

| slug | label |
|---|---|
| `fw-ccs` | CCS |
| `fw-dips` | DIPS |
| `fw-dos` | DOS |
| `fw-gcloud` | G-Cloud |

## Accreditation

| slug | label |
|---|---|
| `accr-as9100` | AS9100 |
| `accr-ce` | Cyber Essentials |
| `accr-ce-plus` | Cyber Essentials Plus |
| `accr-crest` | CREST |
| `accr-iso9001` | ISO 9001 |
| `accr-iso13485` | ISO 13485 |
| `accr-iso14001` | ISO 14001 |
| `accr-iso27001` | ISO 27001 |
| `accr-joscar` | JOSCAR |

JOSCAR is an accreditation. Framework and membership `joscar` tags were merged into `accr-joscar`. `accr-cyber-essentials` and `accr-cyber-essentials-plus` were merged into `accr-ce` / `accr-ce-plus`. Removed as accreditation facets: Def Stan, ITAR, NCSC, NCSC Assured, SC21, CAA Approved.

## Membership

| slug | label |
|---|---|
| `mbr-ads` | ADS Group |
| `mbr-ciehf` | CIEHF |
| `mbr-makeuk` | Make UK |
| `mbr-makeuk-defence` | Make UK Defence |
| `mbr-naudi` | NAUDI |
| `mbr-scrdsc` | SCRDSC |
| `mbr-smi` | SMi |
| `mbr-techuk` | techUK |

## Size

| slug | label |
|---|---|
| `size-micro` | Micro |
| `size-small` | Small |
| `size-medium` | Medium |
| `size-large` | Large |

## Region

Recognised UK regions plus an Overseas bucket for non-UK head offices:

- North East
- North West
- Yorkshire and The Humber
- East Midlands
- West Midlands
- East of England
- London
- South East
- South West
- Scotland
- Wales
- Northern Ireland
- Overseas

Region is derived from the `uk-region` frontmatter field, canonicalised on build. Vague values ("Midlands", "United Kingdom", "Multiple (...)") are resolved from the HQ town where possible, set to Overseas for non-UK head offices, otherwise left blank.

## Capability

The capability vocabulary (top-level and sub-capabilities, `parent/child`):

| slug | label |
|---|---|
| `academia` | Academia |
| `acoustic` | Acoustic |
| `aerospace` | Aerospace |
| `ai` | AI |
| `ai/computer-vision` | AI / Computer Vision |
| `ai/decision-support` | AI / Decision Support |
| `ai/generative` | AI / Generative |
| `ai/ml-analytics` | AI / ML Analytics |
| `ai/nlp` | AI / NLP |
| `air` | Air |
| `autonomy` | Autonomy |
| `autonomy/eod-robotics` | Autonomy / EOD Robotics |
| `autonomy/navigation` | Autonomy / Navigation |
| `autonomy/swarming` | Autonomy / Swarming |
| `autonomy/uxv-control` | Autonomy / UxV Control |
| `avionics` | Avionics |
| `c2` | C2 |
| `c2/battle-management` | C2 / Battle Management |
| `c2/integration` | C2 / Integration |
| `c2/mission-planning` | C2 / Mission Planning |
| `c2/situational-awareness` | C2 / Situational Awareness |
| `c2/targeting` | C2 / Targeting |
| `cbrn` | CBRN |
| `cloud` | Cloud |
| `comms` | Comms |
| `comms/networking` | Comms / Networking |
| `comms/satcom` | Comms / SATCOM |
| `comms/secure-voice` | Comms / Secure Voice |
| `comms/tactical-radio` | Comms / Tactical Radio |
| `comms/waveforms` | Comms / Waveforms |
| `consultancy` | Consultancy |
| `counter-uas` | Counter-UAS |
| `counter-uas/detection` | Counter-UAS / Detection |
| `counter-uas/effector` | Counter-UAS / Effector |
| `cyber` | Cyber |
| `cyber/cross-domain` | Cyber / Cross Domain |
| `cyber/digital-forensics` | Cyber / Digital Forensics |
| `cyber/encryption` | Cyber / Encryption |
| `cyber/grc` | Cyber / GRC |
| `cyber/idam` | Cyber / IDAM |
| `cyber/incident-response` | Cyber / Incident Response |
| `cyber/ot-security` | Cyber / OT Security |
| `cyber/pen-testing` | Cyber / Pen Testing |
| `cyber/red-team` | Cyber / Red Team |
| `cyber/soc-monitoring` | Cyber / SOC Monitoring |
| `cyber/threat-intel` | Cyber / Threat Intel |
| `cyber/vuln-management` | Cyber / Vuln Management |
| `data` | Data |
| `data/analytics` | Data / Analytics |
| `data/engineering` | Data / Engineering |
| `data/labelling` | Data / Labelling |
| `data/visualisation` | Data / Visualisation |
| `detection` | Detection |
| `drones` | Drones |
| `electronics` | Electronics |
| `ew` | EW |
| `ew/direction-finding` | EW / Direction Finding |
| `ew/eccm` | EW / ECCM |
| `ew/ecm` | EW / ECM |
| `ew/elint` | EW / ELINT |
| `ew/spectrum-management` | EW / Spectrum Management |
| `fpv` | FPV |
| `gis` | GIS |
| `hardware` | Hardware |
| `human-factors` | Human Factors |
| `integration` | Integration |
| `integrator` | Integrator |
| `isr` | ISR |
| `isr/fusion` | ISR / Fusion |
| `isr/geoint` | ISR / GEOINT |
| `isr/imint` | ISR / IMINT |
| `isr/osint` | ISR / OSINT |
| `isr/ped` | ISR / PED |
| `isr/sigint` | ISR / SIGINT |
| `it` | IT |
| `land` | Land |
| `logistics` | Logistics |
| `manufacturer` | Manufacturer |
| `manufacturing` | Manufacturing |
| `maritime` | Maritime |
| `missiles` | Missiles |
| `munitions` | Munitions |
| `optronics` | Optronics |
| `quantum` | Quantum |
| `radar` | Radar |
| `rf` | RF |
| `robotics` | Robotics |
| `satellite` | Satellite |
| `sensors` | Sensors |
| `sensors/acoustic-sonar` | Sensors / Acoustic Sonar |
| `sensors/eo-ir` | Sensors / EO-IR |
| `sensors/pnt` | Sensors / PNT |
| `sensors/radar` | Sensors / Radar |
| `services` | Services |
| `shipbuilding` | Shipbuilding |
| `simulation` | Simulation |
| `simulation/lvc` | Simulation / LVC |
| `simulation/synthetic-environment` | Simulation / Synthetic Environment |
| `software` | Software |
| `space` | Space |
| `surveillance` | Surveillance |
| `systems-engineering` | Systems Engineering |
| `test-evaluation` | Test & Evaluation |
| `training` | Training |
| `training/courseware` | Training / Courseware |
| `training/instruction` | Training / Instruction |
| `uas` | UAS |
| `uas/payload` | UAS / Payload |
| `uas/platform` | UAS / Platform |
| `vehicles` | Vehicles |
