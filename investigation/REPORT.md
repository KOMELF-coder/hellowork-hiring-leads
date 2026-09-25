# Pre-development investigation

Historical report: superseded by the validated static SEO implementation documented in [SEO_REPORT.md](SEO_REPORT.md). The prohibited dynamic search routes remain unused.

Date: 2026-09-25. Target: https://www.hellowork.com/.

## Decision

STOP before product development. The requested general keyword search workflow cannot currently be validated while obeying the instruction to avoid paths disallowed by robots.txt. This is a source-access constraint, not evidence of an HTTP anti-bot block on listing pages.

## Direct HTTP evidence

Two sequential GET requests to https://www.hellowork.com/robots.txt returned HTTP 200. The second used the explicit User-Agent `FranceHiringSignals-Investigation/0.1`; its response body and headers are saved alongside this report. Requests had a 25-second timeout, used ordinary HTTPS, and did not use a browser, proxy, login, CAPTCHA bypass, or internal API.

The first restricted-environment attempt failed locally with Windows Schannel `SEC_E_NO_CREDENTIALS`. After authorized network access, the request succeeded. That initial error was not a HelloWork 403 or 429.

Relevant rules in the `User-Agent: *` group include:

```text
Disallow: /*?
Disallow: /fr-fr/emploi/recherche.html
Disallow: /fr-fr/entreprises/recherche.html
Disallow: /fr-fr/api/
Disallow: /fr-fr/search/
```

The file also disallows candidate, account, application, token and redirect paths. There are specific allowances for some tracking parameters and specific advertising bots; these are not a basis for disguising this Actor or modifying search URLs to circumvent the general search restriction.

No request was made to a disallowed search path. We have not established that every public SEO listing or job-detail page is disallowed. Some may be allowed and accessible; that does not establish a complete replacement for arbitrary keywords, location filtering, exact versus related results, and pagination. No substitute URL convention has been invented.

## Validation status

| Required investigation / deliverable | Actual result |
| --- | --- |
| robots.txt | Retrieved twice; HTTP 200; raw evidence saved |
| At least 10 public listing/detail pages | Not completed: access constraint identified first |
| Large, rare, cybersecurity, cloud/devops, developer searches | Not executed |
| Related results and pagination | Not inspected or inferred |
| Salary, remote, dates, contracts, expired details | Not inspected or inferred |
| HTML selectors and canonical job identifiers | Not validated |
| HTTP listing feasibility | Not tested on prohibited search paths |
| Persistent 403 / 429 / CAPTCHA | Not observed; no such claim is made |
| Actor / schemas / Docker / runtime | Not implemented |
| Fixtures / automated tests / Python compilation | Not implemented or run |
| Live large / rare / multi-keyword / location runs | Not executed |
| Raw jobs / unique jobs / final companies | N/A — no collection run, not a zero-result search |
| Apify dataset and input example ready to test | Unavailable until feasibility is resolved |
| Monetization | Not activated |

No scoring formula, extraction logic, deduplication logic or company signals are claimed to be validated. Synthetic fixtures would not satisfy the mandatory live investigation and would conceal the blocker if presented as a completed product.

## Robust next step

Obtain a documented, authorized HelloWork access route supporting keyword and location search plus pagination: for example, an official feed or a supported interface approved for this use. This would require revising the current public-HTML-only scope if the agreed route is not public HTML. Alternatively, obtain a documented permission and access arrangement for automated search collection before revising the present requirement to avoid disallowed paths.

Once a compatible route is established, resume the ten-page investigation, validate actual markup and pagination, and only then implement the separate fetching, parsing, normalization, deduplication, aggregation, scoring and Apify layers.

Adding Playwright, rotating IPs, impersonating an allowed bot, or routing through undocumented APIs would not resolve the current project constraint and was not attempted.
