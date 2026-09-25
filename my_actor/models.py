from dataclasses import dataclass, field

from .normalization import contract


@dataclass
class Job:
    url: str | None
    job_id: str | None
    title: str | None
    company: str | None
    location: dict
    contract_type: str
    salary: dict
    posting_age_raw: str | None
    posting_age_days: int | None
    posting_age_lower_bound_days: int | None
    has_remote_option: bool | None
    remote_modes: list
    is_active: bool | None = True
    anonymous: bool = False
    source_match_type: str | None = 'exact'
    matched_search_keywords: list = field(default_factory=list)
    title_keyword_matches: list = field(default_factory=list)
    description_keyword_matches: list = field(default_factory=list)
    source_observations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    possible_intermediary: bool | None = None
    activity_evidence: str = 'observed_on_listing'


@dataclass
class Config:
    keywords: list = field(default_factory=list)
    start_urls: list = field(default_factory=list)
    location: str = ''
    posted_within_days: int = 14
    contract_types: list = field(default_factory=list)
    max_jobs: int = 250
    max_companies: int = 100
    min_jobs_per_company: int = 1
    include_related_results: bool = False
    include_expired_jobs: bool = False
    include_anonymous_companies: bool = False
    exclude_recruitment_agencies: bool = False
    collect_job_details: bool = True

    @classmethod
    def parse(cls, data):
        if not isinstance(data, dict):
            raise ValueError('Input must be an object')
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f'Unknown input fields: {sorted(unknown)}')
        c = cls(**data)
        for name, maximum in [('keywords', 10), ('start_urls', 20), ('contract_types', 20)]:
            values = getattr(c, name)
            if not isinstance(values, list) or len(values) > maximum:
                raise ValueError(f'{name}: expected array, max {maximum}')
            output, seen = [], set()
            for item in values:
                if not isinstance(item, str) or not item.strip() or len(item.strip()) > (2048 if name == 'start_urls' else 200):
                    raise ValueError(f'Invalid {name} value')
                item = item.strip()
                if item.casefold() not in seen:
                    output.append(item)
                    seen.add(item.casefold())
            setattr(c, name, output)
        if not c.keywords and not c.start_urls:
            raise ValueError('Provide keywords or start_urls')
        if not isinstance(c.location, str) or len(c.location) > 200:
            raise ValueError('location must be a string up to 200 characters')
        c.location = c.location.strip()
        for name, maximum in [('posted_within_days', 90), ('max_jobs', 500), ('max_companies', 500), ('min_jobs_per_company', None)]:
            v = getattr(c, name)
            if type(v) is not int or v < 1 or (maximum and v > maximum):
                raise ValueError(f'Invalid {name}')
        for name in ['include_related_results', 'include_expired_jobs', 'include_anonymous_companies', 'exclude_recruitment_agencies', 'collect_job_details']:
            if type(getattr(c, name)) is not bool:
                raise ValueError(f'{name} must be boolean')
        c.contract_types = list(dict.fromkeys(contract(v) for v in c.contract_types))
        return c
