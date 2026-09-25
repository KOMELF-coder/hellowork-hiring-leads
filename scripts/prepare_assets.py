"""Developer utility: create schemas and minimized fixtures from investigation captures."""
import json
from pathlib import Path

from bs4 import BeautifulSoup


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


properties = {}
for key, default, maximum in [('posted_within_days', 14, 90), ('max_jobs', 250, 500),
                              ('max_companies', 100, 500), ('min_jobs_per_company', 1, None)]:
    properties[key] = dict(title=key.replace('_', ' ').title(), type='integer', editor='number',
                           description='See README for filtering and bounds.', default=default, minimum=1)
    if maximum:
        properties[key]['maximum'] = maximum
for key, default in [('include_related_results', False), ('include_expired_jobs', False),
                     ('include_anonymous_companies', False), ('exclude_recruitment_agencies', False),
                     ('collect_job_details', True)]:
    properties[key] = dict(title=key.replace('_', ' ').title(), type='boolean', editor='checkbox',
                           description='See README for evidence and exclusion rules.', default=default)
properties = {
    'keywords': dict(title='Keywords', type='array', editor='stringList', items={'type': 'string', 'maxLength': 200, 'minLength': 1},
                     maxItems=10, description='Required in discovery mode (1–10). Trimmed and case-insensitive deduplicated. Optional textual match terms in URL mode.',
                     prefill=['cybersecurite', 'devops']),
    'start_urls': dict(title='Public SEO URLs', type='array', editor='stringList', items={'type': 'string'}, maxItems=20,
                       description='Optional. Takes priority. HTTPS HelloWork /fr-fr/emploi/ SEO URLs, no query or fragment.'),
    'location': dict(title='Location', type='string', editor='textfield', maxLength=200, description='Supported catalog location only; ignored in explicit URL mode.'),
    'contract_types': dict(title='Contracts', type='array', editor='stringList', items={'type': 'string'}, maxItems=20,
                           description='Optional normalized contracts: CDI, CDD, Alternance, Stage, Intérim, Freelance, Fonctionnaire, Other, Unknown.'),
    **properties,
}
save('.actor/input_schema.json', dict(title='France Hiring Signals — HelloWork', type='object', schemaVersion=1,
                                    description='Provide keywords or explicit public SEO start_urls. Runtime validates both modes.', properties=properties))
save('.actor/actor.json', dict(actorSpecification=1, name='france-hiring-signals-hellowork',
     title='France Hiring Signals — HelloWork', description='Turn French job postings into company-level hiring signals.',
     version='0.1', buildTag='latest', dockerfile='../Dockerfile', readme='../README.md',
     input='./input_schema.json', output='./output_schema.json', storages={'dataset': './dataset_schema.json'},
     defaultMemoryMbytes=256))
save('.actor/output_schema.json', dict(actorOutputSchemaVersion=1, title='Company signals and coverage report', properties={
    'companies': {'title': 'Company hiring signals', 'template': '{{links.apiDefaultDatasetUrl}}/items'},
    'report': {'title': 'Coverage and warnings', 'template': '{{links.apiDefaultKeyValueStoreUrl}}/records/RUN_REPORT'},
}))
string = {'type': 'string'}
nullable_string = {'type': ['string', 'null']}
boolean = {'type': ['boolean', 'null']}
strings = {'type': 'array', 'items': string}
count = {'type': 'integer', 'minimum': 0}
location = {'type': 'object', 'required': ['raw', 'city', 'department', 'region', 'country'],
            'additionalProperties': False, 'properties': {k: nullable_string for k in ['raw', 'city', 'department', 'region', 'country']}}
salary = {'type': 'object', 'additionalProperties': False, 'required': ['raw', 'min', 'max', 'currency', 'period'],
          'properties': {'raw': nullable_string, 'min': {'type': ['number', 'null']}, 'max': {'type': ['number', 'null']},
                         'currency': nullable_string, 'period': {'enum': ['year', 'month', 'day', 'hour', 'unknown']}}}
job_fields = {k: nullable_string for k in ['url', 'job_id', 'title', 'company', 'posting_age_raw']}
job_fields.update(location=location, salary=salary, contract_type=string, posting_age_days={'type': ['integer', 'null'], 'minimum': 0},
                  posting_age_lower_bound_days={'type': ['integer', 'null'], 'minimum': 0}, has_remote_option=boolean,
                  is_active=boolean, anonymous={'type': 'boolean'}, possible_intermediary=boolean,
                  source_match_type={'enum': ['exact', 'related', None]}, activity_evidence=string,
                  source_observations={'type': 'array', 'items': {'type': 'object', 'required': ['url', 'match_type', 'keywords'],
                    'properties': {'url': string, 'match_type': {'enum': ['exact', 'related', None]}, 'keywords': strings}, 'additionalProperties': False}})
for key in ['remote_modes', 'matched_search_keywords', 'title_keyword_matches', 'description_keyword_matches', 'warnings']:
    job_fields[key] = strings
fields = {k: string for k in ['company', 'company_normalized', 'posting_company', 'source', 'collected_at']}
fields.update(possible_intermediary=boolean, hiring_score={'type': 'number', 'minimum': 0, 'maximum': 100},
              hiring_level={'enum': ['low', 'medium', 'high', 'very_high']}, locations={'type': 'array', 'items': location},
              has_remote_option=boolean, salary_disclosed={'type': 'boolean'},
              freshest_posting_age_days={'type': ['integer', 'null'], 'minimum': 0},
              roles={'type': 'array', 'items': {'type': 'object', 'properties': job_fields, 'required': list(job_fields), 'additionalProperties': False}})
for key in ['matching_open_jobs', 'historical_job_count', 'unique_role_families', 'recent_jobs_3d', 'recent_jobs_7d', 'recent_jobs_14d']:
    fields[key] = count
for key in ['contract_types', 'remote_modes', 'matched_search_keywords', 'title_keyword_matches', 'description_keyword_matches', 'reasons', 'warnings', 'job_urls']:
    fields[key] = strings
caps = dict(volume=30, freshness=25, role_diversity=15, locations=10, permanent_contracts=10, keyword_depth=5, offer_transparency=5)
fields['score_breakdown'] = {'type': 'object', 'required': list(caps), 'additionalProperties': False,
                            'properties': {k: {'type': 'number', 'minimum': 0, 'maximum': v} for k, v in caps.items()}}
save('.actor/dataset_schema.json', {'actorSpecification': 1,
    'fields': {'type': 'object', 'properties': fields, 'required': list(fields), 'additionalProperties': False},
    'views': {'companies': {'title': 'Company signals', 'transformation': {'fields': ['company', 'hiring_score', 'hiring_level', 'matching_open_jobs', 'recent_jobs_7d', 'possible_intermediary', 'warnings']},
        'display': {'component': 'table', 'properties': {k: {'label': k.replace('_', ' ').title()} for k in ['company', 'hiring_score', 'hiring_level', 'matching_open_jobs', 'recent_jobs_7d', 'possible_intermediary', 'warnings']}}}}})

Path('fixtures').mkdir(exist_ok=True)
manifest = []
for path in sorted(Path('investigation').glob('*.html')):
    if path.name == 'detail.html':
        continue
    soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
    nodes = [soup.select_one('link[rel=canonical]'), soup.h1, soup.h2]
    for node in soup.find_all():
        if node.get('data-cy') == 'serpCard' or (node.name == 'p' and node.get_text(strip=True) == 'Résultats proches'):
            nodes.append(node)
    if soup.select_one('#paginationForm'):
        nodes.append(soup.select_one('#paginationForm'))
    reduced = BeautifulSoup('<html><body>' + ''.join(str(n) for n in nodes if n) + '</body></html>', 'html.parser')
    for node in reduced.find_all():
        node.attrs = {k: v for k, v in node.attrs.items() if k in ['href', 'rel', 'data-cy', 'class', 'id', 'name', 'value', 'form', 'formaction', 'type', 'method']}
    output = Path('fixtures') / path.name
    output.write_text(str(reduced), encoding='utf-8')
    manifest.append({'fixture': path.name, 'url': soup.select_one('link[rel=canonical]')['href'], 'captured_at': '2026-09-25', 'kind': 'real HTML, minimized to public job cards and pagination'})
soup = BeautifulSoup(Path('investigation/detail.html').read_text(encoding='utf-8'), 'html.parser')
Path('fixtures/detail.html').write_text('<html>' + str(soup.select_one('link[rel=canonical]')) + str(soup.h1) + ''.join(str(n) for n in soup.select('script[type="application/ld+json"]')) + '</html>', encoding='utf-8')
save('fixtures/manifest.json', manifest)
save('examples/input.json', dict(start_urls=['https://www.hellowork.com/fr-fr/emploi/mot-cle_cybersecurite.html',
    'https://www.hellowork.com/fr-fr/emploi/metier_devops.html'], keywords=['cybersecurite', 'cloud', 'devops'],
    posted_within_days=14, max_jobs=40, max_companies=20, collect_job_details=True))
