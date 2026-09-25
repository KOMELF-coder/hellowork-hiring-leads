from .normalization import company_key, norm


def identity(job):
    if job.url:
        return ('url', job.url)
    if job.job_id:
        return ('id', job.job_id)
    return ('fallback', company_key(job.company), norm(job.title), norm(job.location.get('raw')), norm(job.contract_type))


def merge(existing, other):
    for name in ['matched_search_keywords', 'title_keyword_matches', 'description_keyword_matches', 'warnings', 'source_observations']:
        target = getattr(existing, name)
        for value in getattr(other, name):
            if value not in target:
                target.append(value)
    if other.source_match_type == 'exact':
        existing.source_match_type = 'exact'


class JobIndex:
    def __init__(self):
        self.jobs = {}
        self.ids = {}

    def add(self, job):
        key = identity(job)
        prior = self.jobs.get(key)
        if prior is None and job.job_id:
            prior = self.ids.get(job.job_id)
        if prior is not None:
            merge(prior, job)
            return False
        self.jobs[key] = job
        if job.job_id:
            self.ids[job.job_id] = job
        return True
