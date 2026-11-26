# Countries

Every company in Tally has a country, and Tally knows which countries are switched on.

## On each company page

`country-code`: the company's country as an ISO 3166-1 alpha-2 code in capitals. UK companies are `GB`. A company whose country is not known is `ZZ`. Overseas pages keep `country`, the country's English name, beside the code; UK pages leave `country` out.

`tally-data.json` carries the same code as `country_code` for every company. `country` is unchanged, so anything that read the file before still works.

## countries.json

```json
{
  "generated": "2026-11-26",
  "note": "...",
  "countries": [
    { "code": "GB", "name": "United Kingdom", "bloc": "europe", "live": true,
      "bounds": [-8.7, 49.8, 1.9, 60.9], "regions": ["North East", "..."] },
    { "code": "US", "name": "United States", "aliases": ["USA"], "bloc": "north-america", "live": false }
  ]
}
```

- `code`: ISO 3166-1 alpha-2, unique. Every code a page uses is listed.
- `name`: the English short name; `aliases`: other names pages use for the same country.
- `bloc`: `europe` (the EU, the EEA, the UK, Switzerland, the Western Balkans, Ukraine, Moldova and Türkiye), `north-america`, or `other`.
- `live`: whether the country shows on the Tally site. A live country needs `bounds` (west, south, east, north, in degrees) and `regions`, its first-level regions in order.

## Regions

While a country is live, each of its companies has a region from that country's `regions`, or none. UK pages hold it as `uk-region`; pages in other live countries as `region`. While a country is not live, its companies' region is `Overseas`.

## Never

Russia is never live and no company is listed in Russia. Belarus and Russia are never in the Europe bloc.

`.github/scripts/check.py` checks all of this on every pull request, and `tests/acceptance/test_country_aware.py` holds the contract.
