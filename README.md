<p align="center">
  <img src="assets/tally-banner.png" alt="Tally" width="720">
</p>

# Tally

In air combat, "tally" is the call a pilot makes the moment they have the other aircraft in sight. You cannot act on what you cannot see.

For a defence-sector business, the same problem is knowing who is actually out there. The sector is wide and moves quickly: primes, SMEs, micro-businesses and new entrants, each with capabilities that are hard to find unless you already know where to look. The information is public, but it is scattered across hundreds of company websites, LinkedIn pages, framework registers and trade-body directories. The smallest and most specialist firms, often the most interesting, are the hardest to surface.

Tally is the call sign for "I have visual". It is an open directory of defence companies: what they do, what they can offer, and how to reach them, in one place you can search.

It is a companion to [Foothold](https://github.com/MilUX-Ltd/foothold). Foothold helps a defence-sector founder stand up a working second brain; Tally tells them who else is in the sector.

Built and maintained by [MilUX](https://milux.co.uk), a defence-focused user-centred design consultancy.

## What is in it

One markdown page per company, under `Companies/`, banded A-Z. Each page holds public information only:

- What the company does and the capabilities it offers.
- The company website and company LinkedIn page.
- Frameworks the company is on (e.g. JOSCAR, G-Cloud), and accreditations it holds (e.g. Cyber Essentials Plus, ISO 27001).
- Company size, with a deliberate effort to surface micro and small businesses, not only the primes.
- Location.
- A dated recent-news summary linking to public announcements, awarded contracts, and events.

Tally is about companies, not people. It carries no personal data, no named contacts, and no opinion or assessment. Everything in it is drawn from public sources.

## How to use it

You do not need to download anything. Three ways in:

- **The Tally viewer.** Open [milux-ltd.github.io/tally](https://milux-ltd.github.io/tally/) and filter the whole directory live in your browser by capability, size, location, framework and accreditation. It reads straight from this repo, so it is always current. Exact matches first, near-misses below.
- **Read it here on GitHub.** Every company page is plain markdown and reads directly in the browser under `Companies/`.
- **Point your AI at it.** The pages are small, plain markdown with structured tags, so an assistant like Claude can read the whole directory and answer questions such as "which additive-manufacturing SMEs near Hampshire hold Cyber Essentials Plus?"

If you use Obsidian, you can also clone the repo and open the folder as a vault.

## Tags

Companies are tagged by capability and by a set of prefixed facets: size (`size-`), organisation type (`type-`), ownership (`owned-` / `backed-`), frameworks (`fw-`), accreditations (`accr-`), programmes (`prog-`), and memberships (`mbr-`). See `Tagging.md` for the full list.

## Get listed, corrected, or removed

- **Not listed and want to be?** Email [contact@milux.co.uk](mailto:contact@milux.co.uk) with anything you would like made public, and we will add you in the next update.
- **Listed and need a change?** Email the same address to have a detail corrected or your entry removed.

## Licence

Two parts, licensed differently:

- **The company directory** (everything under `Companies/`) is free for anyone to use, under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). Use it, share it, build on it; just credit MilUX.
- **The MilUX-authored materials** (the company page template, the tag taxonomy, the guide, and the forthcoming search viewer) are licensed under [Creative Commons Attribution-NonCommercial 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Free to use and adapt for non-commercial purposes with attribution; commercial use needs permission from MilUX.

See [LICENSE](LICENSE) for the full statement.
