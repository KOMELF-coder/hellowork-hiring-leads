import logging
from datetime import datetime, timezone

from .aggregation import aggregate
from .dedup import JobIndex
from .discovery import resolve
from .fetching import Fetcher
from .normalization import matches
from .parser import ParserRegressionError, enrich_detail, parse_listing
from .policy import PolicyError

log = logging.getLogger(__name__)


async def run(config, fetcher=None, now=None):
    now = now or datetime.now(timezone.utc)
    targets, warnings = resolve(config)
    if not targets:
        raise ValueError('No supported SEO sources. ' + '; '.join(warnings))
    own_fetcher = fetcher is None
    fetcher = fetcher or Fetcher()
    index = JobIndex()
    metrics = dict(raw_jobs=0, unique_jobs=0, retained_jobs=0, final_companies=0, pages=[], warnings=warnings)
    visited = set()
    try:
        await fetcher.initialize()
        for url, keywords in targets:
            if len(index.jobs) >= config.max_jobs:
                warnings.append('max_jobs reached; keyword coverage may be incomplete.')
                break
            if url in visited:
                warnings.append('Duplicate SEO source skipped.')
                continue
            visited.add(url)
            try:
                response = await fetcher.get(url)
            except PolicyError as error:
                if config.start_urls:
                    raise
                warnings.append(str(error))
                continue
            if response.status_code != 200:
                warnings.append(f'SEO source unavailable (HTTP {response.status_code}): {url}')
                continue
            try:
                jobs, page = parse_listing(response.text, str(response.url), keywords)
            except ParserRegressionError as error:
                # Never hide a broken parser behind a successful empty run.
                raise ParserRegressionError(f'SEO validation failed for {url}: {error}') from error
            page.update(url=url, status=200)
            metrics['pages'].append(page)
            metrics['raw_jobs'] += len(jobs)
            warnings.extend(page['warnings'])
            for job in jobs:
                if len(index.jobs) >= config.max_jobs:
                    break
                index.add(job)
        if not metrics['pages']:
            raise ValueError('No validated accessible SEO sources. ' + '; '.join(warnings))
        metrics['unique_jobs'] = len(index.jobs)
        if metrics['raw_jobs'] > config.max_jobs:
            warnings.append('max_jobs reached; returned signal is a bounded sample.')
        retained = []
        for job in index.jobs.values():
            # Excluded related observations cannot provide keywords or score evidence.
            evidence = [o for o in job.source_observations if o['match_type'] == 'exact' or config.include_related_results]
            if not evidence:
                continue
            job.matched_search_keywords = list(dict.fromkeys(k for o in evidence for k in o['keywords']))
            job.title_keyword_matches = matches(job.title, job.matched_search_keywords)
            if not job.company or (job.anonymous and not config.include_anonymous_companies):
                continue
            if config.contract_types and job.contract_type not in config.contract_types:
                continue
            if config.collect_job_details:
                try:
                    response = await fetcher.get(job.url, 'detail')
                except PolicyError:
                    job.is_active = None
                    job.warnings.append('Public job detail disallowed; activity cannot be verified.')
                else:
                    if response.status_code in (404, 410):
                        job.is_active = False
                        job.activity_evidence = f'http_{response.status_code}'
                    else:
                        enrich_detail(job, response.text, now)
            if not job.title_keyword_matches and not job.description_keyword_matches:
                if job.source_match_type != 'exact':
                    continue
                job.warnings.append('Exact HelloWork SEO result only; no textual keyword evidence.')
            if job.is_active is False:
                if config.include_expired_jobs:
                    retained.append(job)
                continue
            if job.is_active is not True:
                warnings.append('Jobs with unverified activity were excluded from scoring.')
                continue
            if job.posting_age_days is None or job.posting_age_days > config.posted_within_days:
                warnings.append('Jobs outside the date window or with unknown/lower-bound ages were excluded.')
                continue
            retained.append(job)
        metrics['retained_jobs'] = len(retained)
        metrics['warnings'] = sorted(set(warnings))
        rows = aggregate(retained, config, now.isoformat(), metrics['warnings'])
        metrics['final_companies'] = len(rows)
        metrics['http_requests'] = fetcher.requests
        for warning in metrics['warnings']:
            log.warning(warning)
        log.info('raw=%d unique=%d retained=%d companies=%d', metrics['raw_jobs'], metrics['unique_jobs'], len(retained), len(rows))
        return rows, metrics
    finally:
        if own_fetcher:
            await fetcher.close()
