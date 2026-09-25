# France Hiring Signals — HelloWork

Turn French job postings into company-level hiring signals.

## 1. What it does

Find companies with observable hiring activity around your topic without sorting through repeated advertisements. This Python Apify Actor deduplicates job postings, groups them by posting company, and returns an explainable hiring score from 0 to 100.

This Actor uses publicly accessible HelloWork SEO job pages and does not use HelloWork's disallowed dynamic search routes.

This Actor measures observed hiring activity, not company growth, financial health, purchasing intent, or commercial qualification.

## 2. What you get

One dataset row per company: active relevant job counts, recent posting counts, role families, locations, contracts, salary disclosure, remote options, evidence URLs, seven score components, reasons and warnings. Structured `roles` make each signal auditable. Export JSON or CSV for your research workflows.

Example interpretation: “8 relevant active job postings were observed.” Public hiring activity may be useful as a commercial research signal; it does not establish that a company needs your services.

## 3. Who is this for

Recruitment agencies, B2B sales teams, IT consultancies, cybersecurity consultancies, training providers, HR software vendors and market researchers. Automation workflows, developers and AI agents can consume the company dataset and its source evidence.

## 4. How it works

1. Supply supported keywords and a location, or explicit SEO URLs.
2. Check current robots.txt and validate every URL and redirect before fetching it.
3. Parse public HTML, identify exact/related cards, deduplicate across sources.
4. Optionally read each unique public job detail once for validity, date and description match evidence.
5. Apply filters, aggregate by company, score, sort, then limit company results.

Current SEO pagination uses a GET form with `p`; query URLs are excluded. Only the accessible first page is collected, with a warning. Coverage depends on public SEO pages; there is no promise of exhaustive national coverage.

## 5. Example input

```json
{
  "start_urls": [
    "https://www.hellowork.com/fr-fr/emploi/mot-cle_cybersecurite.html",
    "https://www.hellowork.com/fr-fr/emploi/metier_devops.html"
  ],
  "keywords": ["cybersecurite", "cloud", "devops"],
  "posted_within_days": 14,
  "max_jobs": 40,
  "max_companies": 20,
  "min_jobs_per_company": 1,
  "include_related_results": false,
  "include_expired_jobs": false,
  "include_anonymous_companies": false,
  "exclude_recruitment_agencies": false,
  "collect_job_details": true
}
```

Discovery example: `{"keywords": ["cybersecurite"], "location": "Lille"}`. Supported combinations are listed in `my_actor/seo_catalog.json`. Accents and case are normalized; English aliases are not translated. Unsupported combinations produce warnings and are skipped; if none remain the run fails explicitly.

In URL mode, `start_urls` overrides discovery and `location` is ignored. Optional `keywords` provides textual match terms; otherwise the topic is derived from each SEO slug. Here `matched_search_keywords` means source-associated topics, not evidence of a dynamic query. `source_observations` records the actual source URLs and classifications.

## 6. Example output

Illustrative excerpt, not a real company. Full live rows are saved in `examples/live-companies.json`.

```json
{
  "company": "Example SAS",
  "company_normalized": "example sas",
  "posting_company": "Example SAS",
  "possible_intermediary": null,
  "hiring_score": 71.37,
  "hiring_level": "high",
  "matching_open_jobs": 4,
  "historical_job_count": 0,
  "unique_role_families": 3,
  "recent_jobs_3d": 2,
  "recent_jobs_7d": 3,
  "recent_jobs_14d": 4,
  "score_breakdown": {
    "volume": 22,
    "freshness": 20.62,
    "role_diversity": 9,
    "locations": 4,
    "permanent_contracts": 7.5,
    "keyword_depth": 4.5,
    "offer_transparency": 3.75
  },
  "reasons": ["4 relevant active job postings were observed"],
  "warnings": ["Pagination unavailable under current robots-compliant crawling policy."],
  "source": "HelloWork"
}
```

## 7. Pricing placeholder

Future target: **$0.005 per company result = $5 / 1,000 company signals**. No custom paid events or monetization are enabled. Each returned dataset item could support one billable company event later. Platform compute costs are separate.

## 8. Input reference

| Field | Default | Meaning / bounds |
| --- | --- | --- |
| `keywords` | — | Required in discovery mode: 1–10 trimmed strings, ≤200 characters, case-insensitive deduplication |
| `start_urls` | `[]` | Up to 20 HTTPS HelloWork SEO URLs; no query strings or fragments |
| `location` | France | Supported catalog location; no geocoding |
| `posted_within_days` | 14 | Integer 1–90, inclusive cutoff |
| `contract_types` | `[]` | Optional normalized filter, up to 20 strings |
| `max_jobs` | 250 | Integer 1–500, unique discovered jobs before filters/details |
| `max_companies` | 100 | Integer 1–500, after scoring/sorting |
| `min_jobs_per_company` | 1 | Positive integer, minimum retained active relevant jobs |
| `include_related_results` | false | Related jobs still require title/description topic evidence |
| `include_expired_jobs` | false | Retain relevant expired jobs as history, never score them |
| `include_anonymous_companies` | false | Separate identity for each anonymous job |
| `exclude_recruitment_agencies` | false | Exclude explicitly identified possible intermediaries |
| `collect_job_details` | true | False sends no detail requests |

Unknown or lower-bound ages cannot verify the date window and are excluded from active counts. Expired history can be older than the window; its company still needs enough recent active jobs. `max_jobs` bounds discovery, not surviving output. Keyword order matters when the cap is reached; later-source evidence may be incomplete.

## 9. Output reference

| Fields | Meaning |
| --- | --- |
| `company`, `company_normalized`, `posting_company` | Observed publisher and normalized identity; no invented client |
| `possible_intermediary` | True for explicit evidence; otherwise null, not assumed false |
| `hiring_score`, `hiring_level` | Score 0–100 and low / medium / high / very_high |
| `matching_open_jobs`, `historical_job_count` | Retained active relevant jobs; retained expired jobs |
| `unique_role_families` | Distinct normalized title signatures |
| `recent_jobs_3d`, `recent_jobs_7d`, `recent_jobs_14d` | Inclusive known-age active-job counts |
| `locations`, `contract_types` | Structured raw locations and normalized active-job contracts |
| `has_remote_option`, `remote_modes` | True if any explicit option; false only if all explicitly say no; otherwise null |
| `salary_disclosed` | At least one active job discloses salary |
| `matched_search_keywords`, `title_keyword_matches`, `description_keyword_matches` | Source topics versus textual evidence, including retained history |
| `score_breakdown`, `reasons`, `warnings` | Components, observed facts and caveats |
| `roles`, `job_urls` | Structured job evidence and direct public URLs |
| `source`, `collected_at` | HelloWork and UTC collection timestamp |
| `freshest_posting_age_days` | Best known active age, used for tie-breaking |

Roles retain URL/ID, title, company, source match type, per-source provenance, matches, raw/parsed age, salary, contract, location, remote and activity evidence. Salary has `raw`, `min`, `max`, `currency`, `period`, without annualization. Full descriptions and candidate profiles are not stored. Activity evidence distinguishes listing presence, JSON-LD validity, expiry notices and 404/410. With details enabled, unknown validity is excluded.

The default key-value store's `RUN_REPORT` records raw cards, unique jobs, retained jobs, final companies, pages, HTTP requests and warnings, including empty runs.

## 10. Scoring methodology

Only retained active relevant jobs enter the score. Let `n` be their count. Components and their sum are rounded to two decimals with Python `round`; no missing points are redistributed.

| Component | Exact formula | Max |
| --- | --- | --- |
| Volume | 1→6, 2→12, 3→18, 4→22, 5→25, 6–7→28, 8+→30 | 30 |
| Freshness | `25 × sum(weight) / n`; ≤3d=1, ≤7d=0.8, ≤14d=0.5, older/unknown=0 | 25 |
| Role diversity | `min(15, 3 × distinct_role_signatures)` | 15 |
| Locations | Distinct nonempty normalized raw locations: 0–1→0, 2→4, 3→7, 4+→10 | 10 |
| Permanent contracts | `10 × CDI_count / n`; only CDI | 10 |
| Keyword depth | `5 × mean(depth)`; title=1, else description=0.6, else exact SEO only=0.2, else=0 | 5 |
| Transparency | `2.5 × (salary_disclosed_count + remote_disclosed_count) / n`; explicit no-remote counts as disclosure | 5 |

Thresholds: ≥80 very_high, ≥60 high, ≥35 medium, otherwise low. Sort by score descending, active count descending, best known age ascending, normalized company name ascending.

Role signatures remove accents, punctuation, H/F and seniority tokens junior, senior, jr, sr, confirmé(e), expert, expérimenté(e), then sort remaining tokens. Senior Java Developer and Java Developer Senior coincide. C++, C# and .NET remain distinct. This is a deterministic title signature, not a semantic occupation taxonomy.

## 11. Responsible use

Only unauthenticated public SEO and direct job pages are fetched. Current robots rules and a stricter path allowlist are checked before requests and redirects. No dynamic search, query strings, internal API, candidate accounts, applications, candidate personal data, user cookies, proxy rotation or CAPTCHA bypass. A descriptive User-Agent is used. No LLM or external enrichment database.

Company normalization uses trim, case, accents, HTML entities and whitespace. Only explicitly separated decorative recruitment suffixes are removed. Orange and Orange Business are different. Anonymous identities are `anonymous:<job_id>`. Intermediaries require explicit organization wording or explicit recruitment-for-client wording; no brand list is used. A possible intermediary's client and internal hiring are never inferred.

## 12. Limitations

Public SEO availability and first-page ordering determine coverage. Displayed totals may include related results. Cached listings, unknown age/validity, incomplete fields and anonymous publishers can reduce the dataset. Weeks/months use 7/30-day displayed-age approximations; “plus de 1 mois” remains a lower bound, never an exact age. Valid detail `datePosted` takes precedence.

No fuzzy employer merging, synonym translation or geocoding. Company aliases, role synonyms and location variants can remain separate. Intermediaries can be missed when explicit evidence is absent. With details disabled, activity relies on listing presence and is disclosed as such.

Natural expired offers may not be available during live investigation; tests use elapsed validThrough on a real fixture plus synthetic expiry notices and 404 responses. Local SDK execution does not prove deployment on Apify cloud or a Docker build in the target environment.

## 13. Technical details

Python 3.12, HTTPX, BeautifulSoup's standard HTML parser, Protego robots handling, Apify SDK. Verified TLS uses the system trust store. Sequential requests, timeout 25 seconds, jitter 1–2 seconds, maximum 3 attempts, exponential backoff and bounded Retry-After. Persistent 403/429/5xx/timeouts fail explicitly. No browser is needed: job cards and public JobPosting JSON-LD are server-rendered.

Selectors: `[data-cy=serpCard]`, `[data-cy=offerTitle] h3 > p`, `[data-cy=localisationCard]`, `[data-cy=contractCard]`, `.tag-secondary-s`, age footer. The “Résultats proches” DOM marker changes all following cards to related. Direct numeric offer paths provide canonical URLs/IDs; details require matching canonical and JobPosting JSON-LD.

Dedup uses canonical URL, then HelloWork ID, then strict company/title/location/contract tuple. Missing critical structure raises `ParserRegressionError`, including positive/unknown expected counts with zero parsed cards; explicit zero is legitimate. Missing noncritical fields become null with warnings. No pagination form is submitted; visited sets, source caps and unique-job caps bound work and prevent loops.

Modules separate URL policy, HTTP, parsing, normalization, deduplication, discovery, input validation, filtering, aggregation, scoring and Apify integration. See `my_actor/`, `.actor/`, `tests/` and `fixtures/manifest.json`.

```bash
python -m venv .venv
# Activate the virtual environment for your shell.
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q my_actor scripts tests
python scripts/live_validation.py
# Save input at storage/key_value_stores/default/INPUT.json, then:
python -m my_actor
```

Offline tests use minimized real HTML and synthetic failure cases; live tests are separate. See `investigation/SEO_REPORT.md` for results and `investigation/REPORT.md` for the superseded dynamic-search stop.

Apify references: [Actor definition](https://docs.apify.com/actors/development/actor-definition/actor-json), [input](https://docs.apify.com/actors/development/actor-definition/input-schema/specification/v1), [dataset](https://docs.apify.com/storage/dataset-schema), [output](https://docs.apify.com/actors/development/actor-definition/output-schema).
