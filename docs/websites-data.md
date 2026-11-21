# websites.json

Tally company websites that are dead, or whose page has moved. Built weekly by `scripts/check_websites.py` in GitHub Actions.

## Fields

- `generated`: the date of the run.
- `checked`: `websites` checked, and how many pages were `ok`, `gone` or `uncertain` in this run.
- `dead`: websites that are gone, confirmed in two runs in a row. Each row: `name` (as in Tally), `url`, `reason` (`no-such-host`, `refused` or `not-found`), `since` (the first run that found it).
- `moved`: deep links that are gone while the company's home page works, confirmed in two runs. Each row: `name`, `url`, `home`, `since`. The site links to `home`.
- `pending`: results seen in one run only, waiting for the next. Each row: `name`, `url`, `result`, `reason` or `home`, `since`.

## Rules

1. Each website is fetched once with redirects followed, as `TallyLinkCheck/1.0` naming Tally's About page.
2. Gone: the host does not exist, the connection is refused, or the page answers 404 or 410. Ok: any answer below 400. Uncertain: everything else (403, 429, 5xx, timeouts, dropped connections, certificate errors). Uncertain results are never acted on, because many sites block automated checks.
3. A gone page that is not the home page has its home page checked. A working home page makes the result moved; a gone one makes it dead; an uncertain one leaves the result uncertain.
4. A result is published when the previous run had the same result for the same company and URL. Correcting a URL in Tally starts again.
5. The run refuses to write if more than 10% of pages are gone in one run: that points to a network fault on the runner.
6. Companies whose name appears twice in Tally are not checked. No page content is stored.
