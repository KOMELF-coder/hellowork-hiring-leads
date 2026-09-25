# Fixture provenance

These are minimized fragments of real public HelloWork responses captured on 2026-09-25. `manifest.json` records each exact URL. All 13 listing requests and the direct detail request returned HTTP 200 without query strings, login, cookies, proxy or browser. The original public robots snapshot is in `investigation/seo-robots.txt`.

Only canonical links, headings, job cards, the related-results marker and pagination form are retained. Analytics attributes, account controls and unrelated page content were removed. `detail.html` retains the canonical URL, title and public JobPosting JSON-LD. Fixtures contain job-publication information, not candidate profiles.

They cover >20 advertised results, a two-job rare page, related results, anonymous publishers, CDI/Stage/Intérim/Alternance/Freelance, salaries and remote options. Unit tests explicitly mutate these fragments for absent selectors, zero counts, expiry, unknown data and malformed structures; these synthetic cases are not claimed as naturally observed live cases.
