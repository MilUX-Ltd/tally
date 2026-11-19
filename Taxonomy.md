# Tally tag taxonomy

_Authoritative controlled vocabulary. Generated 2026-11-19. Source of truth is `taxonomy.json`; this file is the human-readable mirror. The build (`bin/tally-build-web.py`) reads `taxonomy.json` to label the viewer facets and to validate tags._

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
| `accr-iso45001` | ISO 45001 |
| `accr-joscar` | JOSCAR |
| `accr-soc2` | SOC 2 |

JOSCAR is an accreditation. Framework and membership `joscar` tags were merged into `accr-joscar`. `accr-cyber-essentials` and `accr-cyber-essentials-plus` were merged into `accr-ce` / `accr-ce-plus`. `accr-cyberessentials` and `accr-cyberessentials-plus` are also aliases of `accr-ce` / `accr-ce-plus`. Removed as accreditation facets: Def Stan, ITAR, NCSC, NCSC Assured, SC21, CAA Approved.

## Membership

| slug | label |
|---|---|
| `mbr-ads` | ADS Group |
| `mbr-ciehf` | CIEHF |
| `mbr-glrdsc` | Greater Lincolnshire RDSC |
| `mbr-makeuk` | Make UK |
| `mbr-makeuk-defence` | Make UK Defence |
| `mbr-naudi` | NAUDI |
| `mbr-scrdsc` | South Central RDSC |
| `mbr-smi` | SMi |
| `mbr-techuk` | techUK |
| `mbr-walesdsc` | Defence Wales |

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

Capabilities sit in groups, based on the Defence Wales Capability Matrix 2026 and merged with Tally's earlier list. Each capability belongs to exactly one group. Sub-capabilities use `parent/child` slugs.

### Domains, platforms and weapons

Land, air and sea, the vehicles, ships and aircraft that operate there, weapons and CBRN protection.

| slug | label |
|---|---|
| `aerospace` | Aerospace |
| `air` | Air |
| `avionics` | Avionics |
| `cbrn` | CBRN |
| `land` | Land |
| `maritime` | Maritime |
| `missiles` | Missiles |
| `munitions` | Munitions |
| `shipbuilding` | Shipbuilding |
| `vehicles` | Vehicles |

### Command, control and communications

Command and control, and communications.

| slug | label |
|---|---|
| `c2` | C2 |
| `c2/battle-management` | C2 / Battle Management |
| `c2/integration` | C2 / Integration |
| `c2/mission-planning` | C2 / Mission Planning |
| `c2/situational-awareness` | C2 / Situational Awareness |
| `c2/targeting` | C2 / Targeting |
| `comms` | Comms |
| `comms/networking` | Comms / Networking |
| `comms/satcom` | Comms / SATCOM |
| `comms/secure-voice` | Comms / Secure Voice |
| `comms/tactical-radio` | Comms / Tactical Radio |
| `comms/waveforms` | Comms / Waveforms |

### Sensing, ISR and electronic warfare

Sensors, surveillance, intelligence, geospatial and the electromagnetic spectrum.

| slug | label |
|---|---|
| `acoustic` | Acoustic |
| `detection` | Detection |
| `ew` | EW |
| `ew/direction-finding` | EW / Direction Finding |
| `ew/eccm` | EW / ECCM |
| `ew/ecm` | EW / ECM |
| `ew/elint` | EW / ELINT |
| `ew/spectrum-management` | EW / Spectrum Management |
| `gis` | GIS |
| `isr` | ISR |
| `isr/fusion` | ISR / Fusion |
| `isr/geoint` | ISR / GEOINT |
| `isr/imint` | ISR / IMINT |
| `isr/osint` | ISR / OSINT |
| `isr/ped` | ISR / PED |
| `isr/sigint` | ISR / SIGINT |
| `optronics` | Optronics |
| `radar` | Radar |
| `rf` | RF |
| `sensors` | Sensors |
| `sensors/acoustic-sonar` | Sensors / Acoustic Sonar |
| `sensors/eo-ir` | Sensors / EO-IR |
| `sensors/pnt` | Sensors / PNT |
| `sensors/radar` | Sensors / Radar |
| `surveillance` | Surveillance |

### Cyber, data and software

Cyber security, data, software and IT.

| slug | label |
|---|---|
| `cloud` | Cloud |
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
| `it` | IT |
| `quantum` | Quantum |
| `software` | Software |

### AI, autonomy and robotics

Artificial intelligence, autonomous systems and robotics.

| slug | label |
|---|---|
| `ai` | AI |
| `ai/computer-vision` | AI / Computer Vision |
| `ai/decision-support` | AI / Decision Support |
| `ai/generative` | AI / Generative |
| `ai/ml-analytics` | AI / ML Analytics |
| `ai/nlp` | AI / NLP |
| `autonomy` | Autonomy |
| `autonomy/eod-robotics` | Autonomy / EOD Robotics |
| `autonomy/navigation` | Autonomy / Navigation |
| `autonomy/swarming` | Autonomy / Swarming |
| `autonomy/uxv-control` | Autonomy / UxV Control |
| `robotics` | Robotics |

### Uncrewed systems and counter-UAS

Drones and uncrewed systems, their parts, and countering them.

| slug | label |
|---|---|
| `counter-uas` | Counter-UAS |
| `counter-uas/detection` | Counter-UAS / Detection |
| `counter-uas/effector` | Counter-UAS / Effector |
| `fpv` | FPV |
| `uas` | UAS |
| `uas/airframe` | UAS / Airframe |
| `uas/airworthiness` | UAS / Airworthiness and Compliance |
| `uas/fixed-wing` | UAS / Fixed Wing |
| `uas/ground-control` | UAS / Ground Control |
| `uas/guidance` | UAS / Guidance |
| `uas/multirotor` | UAS / Multirotor |
| `uas/parts` | UAS / Parts Supply |
| `uas/payload` | UAS / Payload |
| `uas/platform` | UAS / Platform |
| `uas/propulsion` | UAS / Propulsion |

### Engineering, design and test

Engineering disciplines, design, research, simulation and test.

| slug | label |
|---|---|
| `civil-engineering` | Civil Engineering |
| `design` | Design |
| `electrical-engineering` | Electrical Engineering |
| `human-factors` | Human Factors |
| `integration` | Integration |
| `mechanical-engineering` | Mechanical Engineering |
| `research-development` | Research and Development |
| `simulation` | Simulation |
| `simulation/lvc` | Simulation / LVC |
| `simulation/synthetic-environment` | Simulation / Synthetic Environment |
| `structural-engineering` | Structural Engineering |
| `systems-engineering` | Systems Engineering |
| `test-equipment` | Test Equipment |
| `test-evaluation` | Test & Evaluation |

### Manufacturing

Making things: fabrication, materials, electronics and hardware.

| slug | label |
|---|---|
| `advanced-manufacturing` | Advanced Manufacturing |
| `cad-cam` | CAD/CAM |
| `composites` | Composites |
| `electronics` | Electronics |
| `hardware` | Hardware |
| `manufacturing` | Manufacturing |
| `metal-fabrication` | Metal Fabrication |
| `pcbs` | PCBs |
| `plastics` | Plastics |
| `precision-engineering` | Precision Engineering |

### Space

Satellites, ground systems and space operations.

| slug | label |
|---|---|
| `satellite` | Satellite |
| `space` | Space |
| `space/design-test` | Space / Design and Test |
| `space/ground-systems` | Space / Ground Systems |
| `space/mission-control` | Space / Mission Control |

### Training and support services

Training, logistics, through-life support and professional services.

| slug | label |
|---|---|
| `academia` | Academia |
| `construction-infrastructure` | Construction and Infrastructure |
| `consultancy` | Consultancy |
| `creative` | Creative |
| `distribution` | Distribution |
| `facilities-management` | Facilities Management |
| `finance` | Finance |
| `inspection-certification` | Inspection, Testing and Certification |
| `legal` | Legal |
| `logistics` | Logistics |
| `obsolescence` | Obsolescence Management |
| `packaging` | Packaging |
| `project-management` | Project Management |
| `services` | Services |
| `through-life-support` | Through-Life Support |
| `training` | Training |
| `training/courseware` | Training / Courseware |
| `training/instruction` | Training / Instruction |
| `workforce` | Workforce and Recruitment |

### Merged slugs

These slugs are kept as aliases so existing tags still resolve.

| old | now |
|---|---|
| `drones` | `uas` |
| `manufacturer` | `manufacturing` |
| `integrator` | `integration` |

### Defence Wales matrix mapping

Each column of the Defence Wales Capability Matrix 2026 and the Tally capability it maps to.

| matrix column | capability |
|---|---|
| Robotics | `robotics` |
| Cyber Security | `cyber` |
| Land | `land` |
| Air | `air` |
| Sea | `maritime` |
| ICT | `it` |
| Surveillance & Recon | `isr` |
| Systems Engineering | `systems-engineering` |
| Testing Equipment | `test-equipment` |
| Software Engineering | `software` |
| AI | `ai` |
| Hardware | `hardware` |
| Distribution | `distribution` |
| Construction & Infrastructure | `construction-infrastructure` |
| Design | `design` |
| Research & Development | `research-development` |
| Mechanical | `mechanical-engineering` |
| Structural | `structural-engineering` |
| Electrical | `electrical-engineering` |
| Civil | `civil-engineering` |
| Software | `software` |
| Systems | `systems-engineering` |
| Electronics | `electronics` |
| Metal Fabrication | `metal-fabrication` |
| Plastics | `plastics` |
| Composites | `composites` |
| Precision | `precision-engineering` |
| PCBs | `pcbs` |
| Obsolescence | `obsolescence` |
| Surveillance Technology | `uas/payload` |
| Counter UAV Technology | `counter-uas` |
| Guidance Systems | `uas/guidance` |
| Ground Control Systems | `uas/ground-control` |
| Software R&D | `software` |
| Electronics R&D | `electronics` |
| Electronics Installation | `electronics` |
| Test & Evaluation | `test-evaluation` |
| Airframe Manufacture | `uas/airframe` |
| Airframe R&D | `uas/airframe` |
| Propulsion Systems | `uas/propulsion` |
| Ancillary Part Supply | `uas/parts` |
| Compliance | `uas/airworthiness` |
| Multicopter | `uas/multirotor` |
| Fixed Wing | `uas/fixed-wing` |
| Legal | `legal` |
| Creative | `creative` |
| Workforce | `workforce` |
| Finance | `finance` |
| Project Management | `project-management` |
| Consultants | `consultancy` |
| Logistics | `logistics` |
| Packaging | `packaging` |
| Facilities Management | `facilities-management` |
| R&D (services) | `research-development` |
| Training | `training` |
| Through Life Support | `through-life-support` |
| Inspection, Testing & Certification | `inspection-certification` |
| CAD/CAM | `cad-cam` |
| Advanced Manufacturing | `advanced-manufacturing` |
| Command Centre | `space/mission-control` |
| Sensors & Satellites | `satellite` |
| Design Testing | `space/design-test` |
| Global Positioning | `sensors/pnt` |
| Ground Systems | `space/ground-systems` |
| R&D (space) | `space` |
