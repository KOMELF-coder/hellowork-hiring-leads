# Static SEO investigation and implementation validation

Date: 2026-09-25. This supersedes the original blocked dynamic-search approach. No dynamic search route was requested.

## Access validation before development

Current robots.txt was retrieved over plain HTTPS: HTTP 200. The exact response and headers are stored as `seo-robots.txt` and `seo-robots.headers.txt`. The generic agent group excludes queries and dynamic search, but not the tested static `mot-cle_` / `metier_` paths or numeric `/fr-fr/emplois/<id>.html` details. The runtime rechecks robots and validates every redirect BEFORE fetching it. No excluded endpoint, API, account or application route is used.

Ten requested-format pages were fetched and inspected first, followed by the rare AS 400, Drupal and DevOps pages. All 13 responded HTTP 200 without redirects. Six additional cybersecurity city URLs and rare/DevOps URLs were discovered in observed public page links; the four requested URLs were provided in the specification. No arbitrary keyword slug generation is used.

The first cyber capture advertised 12,957 jobs; a later live run advertised 13,113. Counts can change or be cached. Counts shown on pages are not claims of coverage, and can include related offers.

## Live tests

The following are fresh HTTPX pipeline runs, all HTTP 200. For the per-page comparison the date window was 90 days and details were disabled, so activity is based on observed listing presence. Related and anonymous jobs were excluded by default. Topics were derived from each explicit URL. Numbers are observed samples, not forecasts.

| Exact URL | Raw cards | Unique jobs | Retained jobs | Final companies |
| --- | ---: | ---: | ---: | ---: |
| https://www.hellowork.com/fr-fr/emploi/metier_analyste-programmeur-as-400.html | 2 | 2 | 2 | 2 |
| https://www.hellowork.com/fr-fr/emploi/metier_developpeur-drupal.html | 20 | 20 | 19 | 11 |
| https://www.hellowork.com/fr-fr/emploi/metier_developpeur-region_hauts-de-france.html | 20 | 20 | 18 | 15 |
| https://www.hellowork.com/fr-fr/emploi/metier_developpeur.html | 20 | 20 | 20 | 19 |
| https://www.hellowork.com/fr-fr/emploi/metier_devops.html | 20 | 20 | 20 | 16 |
| https://www.hellowork.com/fr-fr/emploi/mot-cle_cybersecurite-ville_lille-59000.html | 20 | 20 | 20 | 14 |
| https://www.hellowork.com/fr-fr/emploi/mot-cle_cybersecurite-ville_lyon-69000.html | 20 | 20 | 20 | 19 |
| https://www.hellowork.com/fr-fr/emploi/mot-cle_cybersecurite-ville_nantes-44000.html | 20 | 20 | 20 | 16 |
| https://www.hellowork.com/fr-fr/emploi/mot-cle_cybersecurite-ville_nice-06000.html | 20 | 20 | 20 | 8 |
| https://www.hellowork.com/fr-fr/emploi/mot-cle_cybersecurite-ville_paris-75000.html | 20 | 20 | 20 | 16 |
| https://www.hellowork.com/fr-fr/emploi/mot-cle_cybersecurite-ville_rennes-35000.html | 20 | 20 | 18 | 15 |
| https://www.hellowork.com/fr-fr/emploi/mot-cle_cybersecurite-ville_toulouse-31000.html | 20 | 20 | 19 | 15 |
| https://www.hellowork.com/fr-fr/emploi/mot-cle_cybersecurite.html | 20 | 20 | 20 | 6 |

Additional multi-keyword discovery run, `cybersecurite` + `devops`, 14 days, no details: **40 raw / 40 unique / 40 retained / 30 companies**, three HTTP requests including robots. The absence of cross-source duplicate jobs in this particular sample is not a claim that duplicates cannot occur; shared-job multi-keyword merging is separately tested offline.

Real detail run, cybersecurity, `max_jobs=3`, 14 days: **20 raw cards / 3 bounded unique jobs / 3 retained / 3 companies**, five requests including robots. The full SDK entry point `python -m my_actor` also completed with exit code 0, wrote three company items to its local dataset and stored RUN_REPORT. Every dataset item passed `.actor/dataset_schema.json` field validation.

Machine-readable evidence: `live-report.json`, `live-detail-report.json`, `seo-validation.json`; complete multi-keyword sample dataset: `../examples/live-companies.json`. HTML fixtures and exact source URLs: `../fixtures/manifest.json`.

## HTML and pagination

Observed cards use `[data-cy=serpCard]`, numeric direct offer links under `[data-cy=offerTitle]`, title and company in `h3 > p`, location/contract data-cy tags, salary/remote badges and an age footer. Missing title/card structure is an error; absent noncritical fields produce warnings and nulls. Explicit zero results differ from an unrecognized page or a positive count with no cards.

On the Drupal fixture, the `<p>` containing “Résultats proches” appears between the 19th and 20th cards. DOM-order parsing labels the first 19 exact and the following card related. Excluded related observations provide no keywords or score evidence. Included related jobs still require title or description evidence.

`<form id="paginationForm">` has no method (HTML default GET); submit buttons use `name="p"`, `value="2"`, and empty `formaction`. Following it creates a query URL. It was NOT submitted. Current implementation fetches only first pages and emits exactly `Pagination unavailable under current robots-compliant crawling policy.` No invented pagination endpoint or browser fallback exists.

Anonymous publishers were observed twice on the regional developer fixture and once on the Toulouse cyber fixture. Annual, monthly and daily salary formats, remote modes and lower-bound ages were observed. Per-page company names, contracts and field coverage are in `seo-validation.json`.

The first public detail inspected was https://www.hellowork.com/fr-fr/emplois/83763446.html, linked from the cyber listing. Its canonical and public JobPosting JSON-LD contain `datePosted`, `validThrough`, description and location. `employmentType=FULL_TIME` is NOT interpreted as CDI, and `jobLocationType=TELECOMMUTE` is NOT interpreted as full remote: listing contract and remote badges remain authoritative for those classifications. No recommended-job links or application controls are followed.

## Architecture and scoring

Separate modules implement URL/robots policy, sequential HTTP, DOM/JSON-LD parsing, normalization, catalog discovery, global dedup, filtering, aggregation, scoring and Apify storage. No browser, proxy, LLM, external database or paid event code is present.

URL, then HelloWork ID, then strict normalized tuple identify jobs. Company normalization is conservative and never fuzzy. Anonymous identities are per job; missing publishers are excluded. Intermediary detection uses documented explicit wording, not a brand list, and never guesses a final client.

Score formula: volume lookup 6/12/18/22/25/28/28/30 for 1–8+ jobs; freshness 25×mean(weights 1/.8/.5/0 for ≤3/≤7/≤14/older-or-unknown days); role diversity min(15, 3×normalized families); locations 0/4/7/10 for 1/2/3/4+; CDI 10×proportion; match depth 5×mean(1 title/.6 description/.2 exact-only/0); transparency 2.5×(salary disclosures + remote disclosures)/n. All components have fixed caps, rounded to two decimals, with no redistribution. Full field/rounding/filter semantics are in the README.

## Automated verification

- 97 offline tests passed, zero failures in the final run.
- Python compilation passed for runtime, scripts and tests.
- All JSON files parsed; input and dataset JSON Schemas validated; actual dataset items validated.
- Actor file references and the documented output schema version were verified.
- `pip check`: no broken requirements.
- SDK local Actor run passed with real HTTP, exit code 0 and three company dataset records.
- Thirteen page-level live runs, one multi-keyword run and one detail run passed.

Coverage includes >20 advertised jobs, rare/related/anonymous pages, company and job dedup, contracts, salary periods, remote, expiry, dates, pagination restriction, 403/429/5xx/timeouts, retries, forbidden redirects, redirect loops, no cookie replay, missing selectors, explicit zero, caps, minimum counts, score boundaries, sorting, strict identity and no retained candidate data.

## Actual limitations and remaining risks

Only the first SEO page is reachable under this policy; no national exhaustiveness. Unsupported discovery combinations are skipped with warnings. Unknown ages cannot pass the recent-date filter. Details can fail or lack validThrough; unknown activity is excluded. Cached listings and title-signature heuristics limit precision. ESNs/agencies without explicit wording can remain undetected. Company/role/location synonyms are not merged.

No naturally expired live posting was found during this sample. Expiration handling was validated using elapsed validity on the real detail fixture, synthetic expiry text and simulated 404/410 logic. A failed initial HTTPX attempt exposed the local certificate-store mismatch; using `ssl.create_default_context()` solved it while retaining TLS verification. No certificate bypass was added.

Docker is not installed in this workspace, so the Docker image was not built here. No Apify cloud deployment or Store publication was performed. The successful SDK run is local, not a claim of cloud execution. Revalidate access and resource use on the deployment host.
