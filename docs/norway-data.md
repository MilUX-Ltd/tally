# Norway

Norwegian companies are checked against the Brønnøysund Register Centre's Central Coordinating Register for Legal Entities (Enhetsregisteret), through its open API (`https://data.brreg.no/enhetsregisteret/api/enheter/<organisation number>`, no key). Contains data under the Norwegian licence for Open Government data (NLOD) distributed by the Brønnøysund Register Centre.

Norway is in `countries.json` with its mainland bounds and its 15 counties. It is not live: Norwegian companies are listed as overseas companies until it is switched on.

## On each Norwegian company page

- `country-code: NO` and `country: Norway`.
- `brreg`: the organisation number, nine digits, quoted (`brreg: "943753709"`). The last digit is a modulus 11 check digit; the gate refuses a wrong one.
- Once placed: `postcode` (four digits), `lat`, `lon` and `location-source`: `register` for the registered business address postcode, `website` for an address the company gives, `town` for a confirmed town. The street address is never written.
- Only legal persons are listed. A sole proprietorship (`ENK`) is a person trading under their own name and is never listed.

## Counties

The county comes from the first two digits of the municipality number on the register entry, on the structure in force since 1 January 2024: 03 Oslo, 11 Rogaland, 15 Møre og Romsdal, 18 Nordland, 31 Østfold, 32 Akershus, 33 Buskerud, 34 Innlandet, 39 Vestfold, 40 Telemark, 42 Agder, 46 Vestland, 50 Trøndelag, 55 Troms, 56 Finnmark. Svalbard and Jan Mayen are in no county and get no point.

## Points

From the postcode, using GeoNames postal codes for Norway (`download.geonames.org/export/zip/NO.zip`, CC BY 4.0), read when pages are written; never fetched by the site. A postcode outside mainland Norway gets no point.

## norway-register.json

Written weekly by `scripts/build_norway_register.py` (`.github/workflows/norway-register-refresh.yml`, Monday 03:30 UTC).

```json
{
  "generated": "2026-12-07",
  "attribution": "Contains data under the Norwegian licence for Open Government data (NLOD) distributed by the Brønnøysund Register Centre.",
  "source": "Brønnøysund Register Centre, Central Coordinating Register for Legal Entities",
  "checked": { "companies": 0, "found": 0, "not_found": 0, "failed": 0 },
  "closed": [{ "name": "...", "brreg": "...", "status": "deleted", "date": "YYYY-MM-DD" }],
  "flagged": [{ "name": "...", "brreg": "...", "status": "bankruptcy", "date": null }],
  "not_found": ["<organisation number>"]
}
```

- `closed`: deleted from the register (`deleted`, with the deletion date). Closed companies leave the Tally site.
- `flagged`: `bankruptcy`, `winding-up` or `compulsory-dissolution`. They stay listed, flagged, as UK companies in an insolvency process do.
- `not_found`: a number the register does not know. The number may be wrong in Tally, so the company is not treated as closed.
- Only Tally companies, and only these fields. The register's answer also carries email addresses, phone numbers, street addresses and free text; none of it is read into the file.

The run refuses to write if more than 2% of lookups fail, or if closed companies jump (more than double, and more than three more). A run that changes only the date proposes nothing. Otherwise it opens a pull request that merges itself when the checks pass, unless the set of closed companies changed, which waits for review.

## Accuracy sample

Each first load of a country's companies comes as one pull request with a sample of 50 companies, drawn by `accuracy_sample` with the pull request's date as the seed, each checked by hand against the company's own website and the register. At least 47 of 50 must be right on name, defence relevance, county and capabilities before the country is switched on.

`tests/acceptance/test_norway.py` holds the contract.
