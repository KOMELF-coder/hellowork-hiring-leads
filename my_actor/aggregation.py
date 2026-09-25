from dataclasses import asdict

from .normalization import company_key, role_family
from .scoring import score


def union(jobs, name):
    return sorted({v for j in jobs for v in getattr(j, name)}, key=lambda v: (v.casefold(), v))


def aggregate(jobs, config, collected_at, run_warnings=()):
    groups = {}
    for job in jobs:
        if not job.company or (job.anonymous and not config.include_anonymous_companies):
            continue
        key = f'anonymous:{job.job_id or job.url}' if job.anonymous else company_key(job.company)
        groups.setdefault(key, []).append(job)
    results = []
    for key, all_jobs in groups.items():
        possible_intermediary = True if any(j.possible_intermediary is True for j in all_jobs) else None
        if config.exclude_recruitment_agencies and possible_intermediary is True:
            continue
        active = [j for j in all_jobs if j.is_active is True]
        if len(active) < config.min_jobs_per_company:
            continue
        breakdown = score(active)
        total = round(sum(breakdown.values()), 2)
        level = 'very_high' if total >= 80 else 'high' if total >= 60 else 'medium' if total >= 35 else 'low'
        warnings = list(run_warnings)
        warnings.extend(union(all_jobs, 'warnings'))
        if possible_intermediary:
            warnings.append('Possible intermediary; final client unknown. These postings do not establish internal hiring.')
        if any(j.activity_evidence == 'observed_on_listing' for j in active):
            warnings.append('Activity inferred from public listing presence; detail validity not checked.')
        company = all_jobs[0].company
        locations = []
        for job in active:
            if job.location['raw'] and job.location not in locations:
                locations.append(job.location)
        locations.sort(key=lambda loc: loc['raw'])
        families = {role_family(j.title) for j in active} - {''}
        recent = {d: sum(j.posting_age_days is not None and j.posting_age_days <= d for j in active) for d in (3, 7, 14)}
        remote_states = [j.has_remote_option for j in active]
        remote_option = True if True in remote_states else False if all(v is False for v in remote_states) else None
        result = dict(company=company, company_normalized=key, posting_company=company,
                      possible_intermediary=possible_intermediary, hiring_score=total, hiring_level=level,
                      matching_open_jobs=len(active), historical_job_count=sum(j.is_active is False for j in all_jobs),
                      unique_role_families=len(families), recent_jobs_3d=recent[3], recent_jobs_7d=recent[7], recent_jobs_14d=recent[14],
                      locations=locations, contract_types=sorted({j.contract_type for j in active}),
                      has_remote_option=remote_option, remote_modes=union(active, 'remote_modes'),
                      salary_disclosed=any(j.salary['raw'] is not None for j in active),
                      matched_search_keywords=union(all_jobs, 'matched_search_keywords'),
                      title_keyword_matches=union(all_jobs, 'title_keyword_matches'),
                      description_keyword_matches=union(all_jobs, 'description_keyword_matches'),
                      score_breakdown=breakdown,
                      reasons=[f'{len(active)} relevant active job postings were observed',
                               f'{recent[7]} jobs were posted in the last 7 days',
                               f'{len(families)} distinct normalized role families detected',
                               f'Hiring observed across {len(locations)} locations'],
                      warnings=sorted(set(warnings)), roles=[asdict(j) for j in all_jobs],
                      job_urls=sorted({j.url for j in all_jobs if j.url}), source='HelloWork', collected_at=collected_at,
                      freshest_posting_age_days=min((j.posting_age_days for j in active if j.posting_age_days is not None), default=None))
        results.append(result)
    results.sort(key=lambda r: (-r['hiring_score'], -r['matching_open_jobs'],
                               r['freshest_posting_age_days'] if r['freshest_posting_age_days'] is not None else float('inf'),
                               r['company_normalized']))
    return results[:config.max_companies]
