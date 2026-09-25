"""Unredistributed deterministic 0–100 observed activity score."""
from .normalization import norm, role_family


def score(jobs):
    n = len(jobs)
    if not n:
        return {k: 0 for k in ('volume', 'freshness', 'role_diversity', 'locations', 'permanent_contracts', 'keyword_depth', 'offer_transparency')}
    volume = [0, 6, 12, 18, 22, 25, 28, 28, 30][min(n, 8)]
    weights = [0 if j.posting_age_days is None else
               1 if j.posting_age_days <= 3 else .8 if j.posting_age_days <= 7 else
               .5 if j.posting_age_days <= 14 else 0 for j in jobs]
    families = {role_family(j.title) for j in jobs} - {''}
    locations = {norm(j.location['raw']) for j in jobs if j.location['raw']}
    depth = [1 if j.title_keyword_matches else .6 if j.description_keyword_matches else
             .2 if j.source_match_type == 'exact' else 0 for j in jobs]
    transparency = [int(j.salary['raw'] is not None) + int(j.has_remote_option is not None) for j in jobs]
    return dict(volume=volume, freshness=round(25 * sum(weights) / n, 2),
                role_diversity=min(15, len(families) * 3),
                locations=[0, 0, 4, 7, 10][min(4, len(locations))],
                permanent_contracts=round(10 * sum(j.contract_type == 'CDI' for j in jobs) / n, 2),
                keyword_depth=round(5 * sum(depth) / n, 2),
                offer_transparency=round(2.5 * sum(transparency) / n, 2))
