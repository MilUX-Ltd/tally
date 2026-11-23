# mod-spend.json

MOD's official direct spend with UK industry, by region and financial year. Built monthly by `scripts/build_mod_spend.py` in GitHub Actions. A new edition appears once a year; in other months the file is unchanged and nothing is proposed.

Source: Ministry of Defence, "MOD regional expenditure with industry", official statistics, Open Government Licence v3.0. Collection: https://www.gov.uk/government/collections/mod-regional-expenditure-with-industry-index

## Fields

- `generated`: the date of the run that last changed the file.
- `attribution`: the Open Government Licence line.
- `source`: `title`, `url` (the edition's GOV.UK page) and `published` (its first publication date).
- `years`: financial years in order, as `2025/26`.
- `breaks`: years whose heading in the source carries `[b]`, a break in series (2020/21, a method change).
- `uk`: `{year: pounds}`, the UK Total row.
- `regions`: `{year: {region: {"value": pounds, "per_person": pounds}}}` for the nine English regions, Northern Ireland, Scotland and Wales.

Values are whole pounds at current prices, exactly as published (£ million times 1,000,000). Nothing is estimated or adjusted.

## Rules

1. The GOV.UK Content API names the newest edition in the collection (latest `public_updated_at`); from that edition the ODS whose title begins "Data tables" is read, only from `assets.publishing.service.gov.uk`.
2. Only Table 2 (current prices, £ million) and Table 4 (per person, £) are read, by sheet name, numbers only. The ODS is opened as a zip and only `content.xml` is read, with a size cap and no document type declaration allowed; no formula, link or macro is evaluated.
3. The build refuses to write if any year lacks one of the 12 regions; a value is not a non-negative whole number; the English regions differ from the England row by more than £10m, or England and the three nations differ from the UK Total by more than £5m; the latest year is earlier than the last file's; or a year already in the last file moves its UK total by more than 10%.
