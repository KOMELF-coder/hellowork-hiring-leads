"""Selectors grounded in the 2026-09-25 SEO HTML captures."""
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import Job
from .normalization import age, contract, intermediary, location, matches, norm, remote, salary
from .policy import BASE, validate_url

log = logging.getLogger(__name__)
PAGINATION_WARNING = 'Pagination unavailable under current robots-compliant crawling policy.'


class ParserRegressionError(RuntimeError):
    pass


def text(node):
    return (node.get_text(' ', strip=True) or None) if node else None


def parse_listing(html, url, keywords):
    soup = BeautifulSoup(html, 'html.parser')
    heading = text(soup.h1) or ''
    if not norm(heading).startswith('emploi '):
        raise ParserRegressionError(f'Expected HelloWork SEO heading missing: {url}')
    canonical = soup.select_one('link[rel=canonical]')
    if not canonical or validate_url(urljoin(url, canonical.get('href', ''))) != validate_url(url):
        raise ParserRegressionError(f'Unexpected SEO canonical: {url}')
    expected = None
    for h in soup.select('h2'):
        m = re.search(r'([\d\s\u202f\u00a0]+)\s+offres? d[’\x27]emploi', text(h) or '')
        if m:
            expected = int(re.sub(r'\s', '', m[1]))
            break
    cards = soup.select('[data-cy=serpCard]')
    if not cards:
        cards = [li for li in soup.select('li[data-id-storage-item-id]') if li.select_one('[data-cy=offerTitle]')]
    if not cards and expected != 0:
        raise ParserRegressionError(f'Expected jobs ({expected}); parsed cards=0: {url}')
    card_ids = {id(c) for c in cards}
    source_type = 'exact'
    jobs, warnings = [], []
    for node in soup.descendants:
        if not getattr(node, 'name', None):
            continue
        if node.name in ('p', 'h2', 'h3', 'span') and norm(text(node)) == 'resultats proches':
            source_type = 'related'
        if id(node) not in card_ids:
            continue
        anchor = node.select_one('[data-cy=offerTitle]')
        if not anchor:
            raise ParserRegressionError('Job card lost its offerTitle selector')
        url_job = validate_url(urljoin(BASE, anchor.get('href', '')), 'detail')
        h3 = anchor.select_one('h3')
        parts = h3.find_all('p', recursive=False) if h3 else []
        title = text(parts[0]) if parts else None
        company = text(parts[1]) if len(parts) > 1 else None
        raw = text(node) or ''
        anonymous = 'souhaite rester anonyme' in norm(raw) or norm(company) in ('anonyme', 'entreprise anonyme', 'confidentiel')
        if anonymous:
            company = 'Anonymous company'
        job_warnings = []
        if not title:
            raise ParserRegressionError('Job title structure changed')
        if not company:
            job_warnings.append('Missing company; excluded from company aggregation.')
        loc = text(node.select_one('[data-cy=localisationCard]'))
        if not loc:
            job_warnings.append('Missing location.')
        contract_raw = text(node.select_one('[data-cy=contractCard]'))
        if not contract_raw:
            job_warnings.append('Missing contract.')
        tags = node.select('.tag-secondary-s')
        salary_raw = next((text(t) for t in tags if '€' in (text(t) or '') or 'EUR' in (text(t) or '')), None)
        salary_value = salary(salary_raw)
        if salary_raw and salary_value['min'] is None:
            job_warnings.append('Unknown salary format.')
        remote_raw = ' '.join(text(t) or '' for t in tags if 'teletravail' in norm(text(t)) or 'remote' in norm(text(t)))
        has_remote, modes = remote(remote_raw)
        age_node = node.select_one('div.text-grey-500.pl-1')
        age_raw = text(age_node)
        if age_raw is None:
            age_raw = next((s.strip() for s in node.stripped_strings if re.match(r"(?:il y a|moins d|plus de) ", norm(s))), None)
        days, lower = age(age_raw)
        if days is None:
            job_warnings.append('Unknown or lower-bound posting age; no freshness points.')
        job_id = re.search(r'/([0-9]+)\.html$', url_job)[1]
        job = Job(url=url_job, job_id=job_id, title=title, company=company, location=location(loc),
                  contract_type=contract(contract_raw), salary=salary_value, posting_age_raw=age_raw,
                  posting_age_days=days, posting_age_lower_bound_days=lower, has_remote_option=has_remote,
                  remote_modes=modes, anonymous=anonymous, source_match_type=source_type,
                  matched_search_keywords=list(keywords), title_keyword_matches=matches(title, keywords),
                  source_observations=[{'url': url, 'match_type': source_type, 'keywords': list(keywords)}],
                  warnings=job_warnings, possible_intermediary=intermediary(company))
        jobs.append(job)
    if cards and len(jobs) != len(cards):
        raise ParserRegressionError('Not all job cards could be parsed')
    for job in jobs:
        for warning in job.warnings:
            log.warning('%s: %s', job.job_id, warning)
    if soup.select_one('#paginationForm'):
        warnings.append(PAGINATION_WARNING)
    return jobs, {'expected_jobs': expected, 'parsed_cards': len(cards), 'warnings': warnings}


def parse_datetime(value):
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
    except (ValueError, AttributeError):
        return None


def enrich_detail(job, html, now=None):
    now = now or datetime.now(timezone.utc)
    soup = BeautifulSoup(html, 'html.parser')
    # Restrict expiry detection to visible notice headings, never recommended jobs.
    notices = ' '.join(text(n) or '' for n in soup.select('h1,h2,[role=alert]'))
    if re.search(r"(?:offre|annonce).{0,35}(?:expiree|n.est plus disponible|n.est plus en ligne|pourvue)", norm(notices)):
        job.is_active = False
        job.activity_evidence = 'explicit_expiry_notice'
        return
    postings = []
    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            if value.get('@type') == 'JobPosting':
                postings.append(value)
            if '@graph' in value:
                walk(value['@graph'])
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue
    canonical = soup.select_one('link[rel=canonical]')
    if not canonical or validate_url(urljoin(job.url, canonical.get('href', '')), 'detail') != job.url:
        raise ParserRegressionError(f'Unexpected detail canonical for {job.url}')
    def normalized_detail_url(value):
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            candidate = validate_url(urljoin(job.url, value), 'detail')
        except Exception:
            return value.strip().rstrip('/')
        return candidate.rstrip('/')

    expected_url = normalized_detail_url(job.url)
    data = next(
        (
            p for p in postings
            if normalized_detail_url(p.get('url')) == expected_url
            or normalized_detail_url(p.get('@id')) == expected_url
        ),
        None,
    )

    # HelloWork can expose a valid JobPosting whose URL serialization differs from
    # the listing URL. Fall back to the stable numeric offer id before considering
    # a single unambiguous JobPosting on the page.
    if data is None and job.job_id:
        id_pattern = re.compile(rf'(?:/|\\b){re.escape(str(job.job_id))}(?:\\.html)?(?:$|[/?#])')
        candidates = []
        for posting in postings:
            references = [posting.get('url'), posting.get('@id')]
            identifier = posting.get('identifier')
            if isinstance(identifier, str):
                references.append(identifier)
            elif isinstance(identifier, dict):
                references.extend([identifier.get('value'), identifier.get('name')])
            if any(isinstance(ref, str) and id_pattern.search(ref) for ref in references):
                candidates.append(posting)
        if len(candidates) == 1:
            data = candidates[0]

    if data is None and len(postings) == 1:
        data = postings[0]
        job.warnings.append('JobPosting JSON-LD URL did not match exactly; used the single unambiguous JobPosting on the page.')

    if data is None:
        job.is_active = None
        job.activity_evidence = 'missing_or_ambiguous_jobposting_jsonld'
        job.warnings.append('No unambiguous matching public JobPosting JSON-LD; activity could not be verified and this job was excluded from scoring.')
        return False

    valid = parse_datetime(data.get('validThrough'))
    job.is_active = valid > now if valid else None
    job.activity_evidence = 'jsonld_validThrough' if valid else 'unknown_validity'
    if valid is None:
        job.warnings.append('Detail has no usable validThrough; activity unverified and excluded from scoring.')
    posted = parse_datetime(data.get('datePosted'))
    if posted and posted <= now:
        job.posting_age_days = (now - posted).days
        job.posting_age_lower_bound_days = None
        job.posting_age_raw = data['datePosted']
        job.warnings = [w for w in job.warnings if w != 'Unknown or lower-bound posting age; no freshness points.']
    elif posted:
        job.warnings.append('Future datePosted ignored.')
    description = BeautifulSoup(data.get('description', ''), 'html.parser').get_text(' ', strip=True)
    job.description_keyword_matches = matches(description, job.matched_search_keywords)
    job.possible_intermediary = intermediary(job.company, description)
    # Description is inspected only for keyword/intermediary evidence, never retained.
    places = data.get('jobLocation')
    if isinstance(places, dict):
        address = places.get('address', {})
        if isinstance(address, dict):
            job.location['city'] = address.get('addressLocality') or job.location['city']
            job.location['region'] = address.get('addressRegion') or None
            country = address.get('addressCountry')
            if isinstance(country, str):
                job.location['country'] = 'France' if country == 'FR' else country
    return True
