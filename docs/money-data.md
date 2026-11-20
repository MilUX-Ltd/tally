# Money data

`money.json` shows where UK defence contract money goes: by UK region, to which Tally companies, and to suppliers overseas. It is built by `scripts/build_money.py` from public award notices. It holds no company revenue figures.

Contains public sector information licensed under the Open Government Licence v3.0.

## Sources

- **Contracts Finder** (OCDS search API), award notices.
- **Find a Tender** (OCDS release packages API), award notices. Since 24 February 2025 notices above the procurement thresholds are published here rather than on Contracts Finder. `money.json` lists it under `sources` only when its notices were read; see the coverage note below.
- **postcodes.io**, to place a supplier's postcode in a region.

All three are free and need no key. Contracts Finder and Find a Tender are published under the Open Government Licence v3.0, and the attribution above must stay with the data wherever it is shown.

## Period

Awards dated from 1 January 2023 to the build date, by award date. Years are calendar years. The period actually covered by the current file is stated in its `period` field and in the coverage note below.

## Rules

1. **Defence buyers only.** A notice counts when its buyer name matches an explicit allowlist: Ministry of Defence (MOD), Defence Equipment and Support, Defence Infrastructure Organisation, Submarine Delivery Agency, Dstl, Defence Digital, the Defence and Security Accelerator and UK Defence Innovation, UK Hydrographic Office, Royal Navy, British Army, Royal Air Force, Atomic Weapons Establishment, Defence Nuclear Organisation, Defence Electronics and Components Agency, and the Single Source Regulations Office. The list is at the top of the script.
2. **Value.** Award values in pounds only, rounded to whole pounds. Awards in other currencies are counted in `excluded.non_gbp` and left out of totals. An award shared by several suppliers is split equally between them.
3. **Frameworks.** Framework agreements and dynamic purchasing systems carry a ceiling, not spend. Their award notices are counted in `excluded.frameworks` and left out of totals. Call-offs from a framework or a dynamic purchasing system are real orders and are counted.
4. **Place.** A UK supplier is placed in one of the 12 Tally regions by its postcode (postcodes.io, with terminated postcodes and outcodes as fallbacks). Without a usable postcode, the build uses the NUTS region code Find a Tender gives, then the town, but only when every city or town of that name is in the same region. A supplier whose address names another country, in the country field or at the end of the address, is shown under `overseas` by country; Jersey, Guernsey, the Isle of Man and Gibraltar are not UK regions. A supplier that cannot be placed counts under `unplaced`.
5. **Duplicates.** Since 24 February 2025 an above-threshold award can appear on both services. The same supplier within three days of the same award date on both counts once, with the Find a Tender value.
6. **Tally companies.** A supplier is matched to a Tally company by Companies House number where the notice gives one, otherwise by normalised name (lower case, punctuation and suffixes such as Ltd, Limited, PLC, LLP, UK, Group and Holdings removed). A name shared by two Tally companies is not used. A missed match is preferred to a wrong one.
7. **No personal data.** A supplier is named only when it is clearly a registered organisation: it has a Companies House number, its name ends in a legal form such as Ltd, PLC, LLP, GmbH or AB, or it is a university or public body. Other suppliers count in the totals but are never named.

## Fields

- `regions.<year>.<region>`: total value and number of awards, the part won by Tally companies (`tally_value`, `tally_count`), and up to five top suppliers.
- `overseas.<year>.<country>`: the same for suppliers outside the UK.
- `unplaced.<year>`: value and count that could not be placed.
- `companies.<Tally company>`: each award with date, value, buyer, title and the public notice link.
- `excluded`: the number of framework or DPS awards and non-sterling awards left out.

## Known gaps

- **Award values are whole-contract values, not annual spend.** A five-year contract counts in full in the year it was awarded, so one large award can dominate a year or a region.
- **Frameworks are excluded.** Their ceilings are not spend. Spend through a framework appears only when a call-off is published as its own notice, and many are not.
- **Government-to-government purchases do not appear**, such as equipment bought from the United States through Foreign Military Sales.
- **Only notices published on Contracts Finder and Find a Tender are counted.** Contracts exempt from publication for security reasons, and spend that is never published as an award notice, are not here.
- **Place is the supplier's notice address**, usually a registered office, not where the work is done. Groups with a London or South East head office pull value there.
- **Some notices published under a defence buyer are subcontracts** let by a prime contractor (for example infrastructure supply chain notices). They are counted as published.
- **Coverage.** Both services limit how fast they can be read. The period and sources actually covered by the current file are recorded below.

## Coverage of the current file

Built on 20 November 2026. Preview build, not yet the full period.

- **Period covered: awards dated 16 April 2026 to 20 November 2026.** Both services rate-limit by address (HTTP 429 with a two-minute wait after a few dozen requests, about four to six requests a minute sustained), so the full period from 1 January 2023 would have taken many hours of fetching. The fetch ran most recent first and stopped after about 90 minutes; the build starts the period where both services are complete in the cache.
- Contracts Finder: 328 pages of award notices (about 21,000 notices, all buyers, some read twice where a window was split), one window per weekday and one per weekend, each window halved when it reached the service's limit of five pages per query.
- Find a Tender: 97 pages (7,912 notices, all buyers), weekly windows from 13 April 2026. Find a Tender gives the value and signature date on the contract rather than the award, and the build reads them from there.
- Requests: about 550 in all, including retries after rate limiting, plus a handful of postcodes.io lookups.
- Awards dated before 16 April 2026 but published inside the window are left out, so a year is never partly counted.
- A rerun with the same cache folder extends the period backwards without fetching again what it already holds.

## Rebuilding

```
python3 scripts/build_money.py all --cache <folder outside the repository>
```

Raw downloads stay in the cache folder and are never committed. A rerun reads pages already in the cache and does not fetch them again.
