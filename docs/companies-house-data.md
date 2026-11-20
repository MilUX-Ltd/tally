# companies-house.json

Closed Tally companies, and defence companies formed and dissolved each year. Built weekly by `scripts/build_companies_house.py` from the Companies House Public Data API. Contains public sector information licensed under the Open Government Licence v3.0.

## Fields

- `generated`: the date of the run.
- `attribution`, `source`: the licence line and the source.
- `checked`: `companies` (Companies House numbers looked up), `found`, `not_found`, `failed`.
- `closed`: Tally companies whose status is `dissolved`, `converted-closed`, `removed` or `closed`. Each row: `name` (as in Tally), `ch`, `status`, and `date` (date of cessation) when Companies House gives one.
- `flagged`: Tally companies still on the register but in `liquidation`, `administration`, `receivership`, `insolvency-proceedings` or `voluntary-arrangement`, or active with a proposal to strike off. Each row: `name`, `ch`, `status`, and `detail` when given.
- `not_found`: numbers Companies House does not know. Not treated as closed: the number may be wrong in Tally. Check these by hand.
- `trend.codes`: the three activity (SIC) codes counted.
- `trend.years`: one row per calendar year from 2010: `year`, `partial` (true for this year, which runs to yesterday), and `formed` and `dissolved`, each with `total` and a count per code.

## Rules

1. Only Tally companies with a Companies House number are looked up. A company without one is not checked.
2. Two Tally pages that carry the same number both appear.
3. The trend counts companies incorporated, or dissolved, in each year whose registered activity codes include the code. `total` is one search across the three codes, so a company with two of them counts once. The build refuses a total below the largest code or above their sum.
4. The build refuses to write if more than 2% of lookups fail for reasons other than "not found", or if closed companies more than double from the last published file.
5. Officers, addresses and every other field are never written.

## Caveats

- Activity codes are self-declared. Many defence firms register under general engineering, electronics or IT codes, so the trend covers only firms that call themselves defence.
- Companies House removes dissolved companies from its records after a number of years, so older years undercount companies that formed and later closed.
- Closure and insolvency are as Companies House records them on the day of the run.
