import asyncio
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jsonschema
import pytest

from my_actor.aggregation import aggregate
from my_actor.dedup import JobIndex
from my_actor.discovery import resolve
from my_actor.fetching import FetchError, Fetcher
from my_actor.models import Config
from my_actor.normalization import age, company_key, contract, intermediary, location, remote, role_family, salary
from my_actor.parser import PAGINATION_WARNING, ParserRegressionError, enrich_detail, parse_listing
from my_actor.policy import BASE, PolicyError, RobotsPolicy, validate_url
from my_actor.scoring import score
from my_actor.scraper import run

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'fixtures'
URL = BASE + '/fr-fr/emploi/mot-cle_cybersecurite.html'
NOW = datetime(2026, 9, 25, 16, tzinfo=timezone.utc)


def html(name='seo-cyber.html'):
    return (FIX / name).read_text(encoding='utf-8')


def parsed(name='seo-cyber.html', keywords=None):
    url = URL if name == 'seo-cyber.html' else BASE + '/fr-fr/emploi/' + name
    return parse_listing(html(name), url, keywords or ['cybersecurite'])


def job():
    return copy.deepcopy(parsed()[0][0])


def config(**kw):
    return Config.parse({'keywords': ['cybersecurite'], **kw})


@pytest.mark.parametrize('raw,expected,lower', [
    ("moins d'une heure", 0, None), ('il y a 2 heures', 0, None), ('il y a 3 jours', 3, None),
    ('il y a 2 semaines', 14, None), ('il y a 2 mois', 60, None), ('plus de 1 mois', None, 30),
    ('hier?', None, None), (None, None, None)])
def test_ages(raw, expected, lower):
    assert age(raw) == (expected, lower)


@pytest.mark.parametrize('raw,lo,hi,period', [
    ('30\u202f000 - 35\u202f000 € / an', 30000, 35000, 'year'),
    ('800 - 1 867,02 € / mois', 800, 1867.02, 'month'),
    ('480 - 550 € / jour', 480, 550, 'day'), ('15,50 € / heure', 15.5, 15.5, 'hour'),
    ('45k € annuel', 45000, 45000, 'year'), (None, None, None, 'unknown'),
    ('Selon profil €', None, None, 'unknown')])
def test_salary(raw, lo, hi, period):
    s = salary(raw)
    assert (s['min'], s['max'], s['period']) == (lo, hi, period)


@pytest.mark.parametrize('raw,expected', [('CDI', 'CDI'), ('Stage', 'Stage'), ('Intérim', 'Intérim'),
    ('apprentissage', 'Alternance'), ('CDD', 'CDD'), ('freelance', 'Freelance'), ('fonctionnaire', 'Fonctionnaire'),
    ('autre chose', 'Other'), (None, 'Unknown')])
def test_contracts(raw, expected):
    assert contract(raw) == expected


@pytest.mark.parametrize('raw,flag,modes', [('Télétravail partiel', True, ['partial']),
    ('Télétravail occasionnel', True, ['occasional']), ('Télétravail complet', True, ['full']),
    ('Sans télétravail', False, []), ('', None, [])])
def test_remote(raw, flag, modes):
    assert remote(raw) == (flag, modes)


@pytest.mark.parametrize('entry', json.loads((FIX / 'manifest.json').read_text(encoding='utf-8')))
def test_every_real_fixture(entry):
    jobs, info = parse_listing(html(entry['fixture']), entry['url'], ['cybersecurite', 'developpeur', 'devops'])
    assert len(jobs) == (2 if 'as-400' in entry['url'] else 20)
    assert all(j.company and j.title and j.url and j.job_id and j.location['raw'] for j in jobs)
    assert all(j.contract_type != 'Unknown' for j in jobs)
    assert info['expected_jobs'] > 0


def test_high_volume_and_pagination():
    jobs, meta = parsed('metier_developpeur.html')
    assert meta['expected_jobs'] > 20 and len(jobs) == 20
    assert PAGINATION_WARNING in meta['warnings']


def test_rare():
    jobs, meta = parsed('metier_analyste-programmeur-as-400.html')
    assert len(jobs) == meta['expected_jobs'] == 2
    assert not meta['warnings']


def test_related_breakpoint():
    jobs, _ = parsed('metier_developpeur-drupal.html')
    assert [j.source_match_type for j in jobs] == ['exact'] * 19 + ['related']


def test_anonymous_independent():
    jobs, _ = parsed('metier_developpeur-region_hauts-de-france.html')
    anonymous = [j for j in jobs if j.anonymous]
    assert len(anonymous) == 2
    assert aggregate(anonymous, config(), NOW.isoformat()) == []
    result = aggregate(anonymous, config(include_anonymous_companies=True), NOW.isoformat())
    assert len(result) == 2
    assert len({r['company_normalized'] for r in result}) == 2


def test_multi_keyword_dedup():
    a, b = job(), job()
    b.matched_search_keywords = ['cloud']
    idx = JobIndex()
    assert idx.add(a) and not idx.add(b)
    assert len(idx.jobs) == 1
    assert a.matched_search_keywords == ['cybersecurite', 'cloud']


def test_strict_dedup_priority():
    a, b = job(), job()
    b.url = None
    idx = JobIndex()
    idx.add(a)
    assert not idx.add(b)
    a, b = job(), job()
    a.url = b.url = a.job_id = b.job_id = None
    idx = JobIndex()
    idx.add(a)
    assert not idx.add(b)
    b = copy.deepcopy(b)
    b.title += ' Python'
    assert idx.add(b)


def test_company_normalization_and_no_fuzzy():
    assert company_key('  École &amp; Co  - recrutement ') == 'ecole & co'
    assert company_key('Orange') != company_key('Orange Business')
    a, b = job(), job()
    a.company, b.company = 'École & Co', ' ECOLE &amp; CO '
    b.url += 'different'
    assert len(aggregate([a, b], config(), NOW.isoformat())) == 1


def test_missing_selectors():
    with pytest.raises(ParserRegressionError):
        parse_listing(html().replace('serpCard', 'changed').replace('offerTitle', 'changed'), URL, ['cloud'])


def test_empty_and_broken_are_different():
    empty = f'<link rel="canonical" href="{URL}"><h1>Emploi Cybersecurite</h1><h2>0 offres d\'emploi</h2>'
    assert parse_listing(empty, URL, ['cybersecurite'])[0] == []
    with pytest.raises(ParserRegressionError):
        parse_listing(empty.replace('0 offres', '10 offres'), URL, ['cloud'])
    with pytest.raises(ParserRegressionError):
        parse_listing('', URL, ['cloud'])


def test_missing_company_and_location():
    source = html().replace('PÔLE FORMATION BRETAGNE UIMM', '')
    jobs, _ = parse_listing(source, URL, ['cybersecurite'])
    assert jobs[0].company is None
    assert jobs[0].warnings
    assert location('Mystery') == dict(raw='Mystery', city=None, department=None, region=None, country=None)


def test_detail_real_and_expired():
    j = job()
    enrich_detail(j, html('detail.html'), NOW)
    assert j.is_active is True and j.posting_age_days == 0
    assert j.location['country'] == 'France'
    j = job()
    enrich_detail(j, html('detail.html'), datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert j.is_active is False
    assert score([])['volume'] == 0


def test_expiry_notice_and_history():
    j = job()
    enrich_detail(j, '<h1>Cette offre n’est plus disponible</h1>', NOW)
    assert j.is_active is False
    a = job()
    row = aggregate([a, j], config(), NOW.isoformat())[0]
    assert row['matching_open_jobs'] == 1 and row['historical_job_count'] == 1
    assert row['hiring_score'] == sum(score([a]).values())


def test_intermediary_evidence():
    assert intermediary('Cabinet de recrutement ABC') is True
    assert intermediary('Example') is None
    assert intermediary('Example', 'Nous recrutons pour notre client') is True
    j = job()
    j.possible_intermediary = True
    assert not aggregate([j], config(exclude_recruitment_agencies=True), NOW.isoformat())


def test_role_families_and_score():
    assert role_family('Senior Java Developer') == role_family('Java Developer Senior')
    j = job()
    j.posting_age_days = None
    j.contract_type = 'Stage'
    s = score([j])
    assert s['freshness'] == s['permanent_contracts'] == 0
    for n in range(1, 501):
        total = sum(score([j] * n).values())
        assert 0 <= total <= 100


def test_exact_score_formula():
    a, b = job(), job()
    a.posting_age_days, b.posting_age_days = 0, 7
    b.contract_type = 'Stage'
    a.salary = salary('500 € / jour')
    b.salary = salary(None)
    a.has_remote_option, b.has_remote_option = True, None
    b.title = a.title
    b.location = location('Paris - 75')
    a.title_keyword_matches = ['cybersecurite']
    b.title_keyword_matches = []
    b.description_keyword_matches = ['cybersecurite']
    assert score([a, b]) == dict(volume=12, freshness=22.5, role_diversity=3, locations=4,
                               permanent_contracts=5, keyword_depth=4, offer_transparency=2.5)


def test_limits_sort_and_schema():
    a, b, c = job(), job(), job()
    a.company, b.company, c.company = 'B', 'A', 'A'
    rows = aggregate([a, b, c], config(max_companies=1), NOW.isoformat())
    assert len(rows) == 1 and rows[0]['company'] == 'A'
    assert len(aggregate([a, b, c], config(min_jobs_per_company=2), NOW.isoformat())) == 1
    schema = json.loads((ROOT / '.actor/dataset_schema.json').read_text(encoding='utf-8'))['fields']
    for row in aggregate([a, b, c], config(), NOW.isoformat()):
        jsonschema.validate(row, schema)
    assert rows[0]['hiring_score'] == round(sum(rows[0]['score_breakdown'].values()), 2)


def test_no_candidate_data_retained():
    j = job()
    source = html('detail.html').replace('Les missions du poste', 'candidate@example.test +33 612345678')
    enrich_detail(j, source, NOW)
    output = json.dumps(aggregate([j], config(), NOW.isoformat()))
    assert 'candidate@example.test' not in output and '+33 612345678' not in output
    assert 'description"' not in output


@pytest.mark.parametrize('url', ['http://www.hellowork.com/fr-fr/emploi/metier_devops.html',
    BASE + '/fr-fr/emploi/recherche.html', URL + '?p=2', URL + '#fragment',
    'https://www.hellowork.com.evil.test/fr-fr/emploi/metier_devops.html',
    BASE + '/fr-fr/emploi/../compte/', BASE + '/fr-fr/emploi/%72echerche.html',
    BASE + '/fr-fr/emplois/candidature.html', 'https://user@www.hellowork.com/fr-fr/emploi/metier_devops.html'])
def test_url_policy(url):
    with pytest.raises(PolicyError):
        validate_url(url)


def test_robots_and_discovery():
    policy = RobotsPolicy((ROOT / 'investigation/seo-robots.txt').read_text(encoding='utf-8'))
    assert policy.check(URL) == URL
    with pytest.raises(PolicyError):
        RobotsPolicy('User-agent: *\nDisallow: /').check(URL)
    targets, warnings = resolve(config(keywords=['madeup']))
    assert not targets and warnings
    assert resolve(config(start_urls=[URL], location='ignored'))[0][0][0] == URL


def test_input_validation():
    assert config(keywords=[' cloud ', 'CLOUD']).keywords == ['cloud']
    for data in [{}, {'keywords': []}, {'keywords': ['a' * 201]}, {'keywords': ['a'], 'max_jobs': True},
                 {'keywords': ['a'], 'posted_within_days': 91}, {'keywords': ['a'], 'collect_job_details': 'false'}]:
        with pytest.raises(ValueError):
            Config.parse(data)


async def no_sleep(_):
    pass


def transport(handler):
    return Fetcher(httpx.AsyncClient(transport=httpx.MockTransport(handler)), sleep=no_sleep, jitter=False)


@pytest.mark.parametrize('status', [403, 429, 500, 503])
def test_limited_retries(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status)
    f = transport(handler)
    with pytest.raises(FetchError):
        asyncio.run(f.initialize())
    assert len(calls) == 3


def test_retry_recovery():
    codes = iter([429, 503, 200])
    f = transport(lambda req: httpx.Response(next(codes), text='User-agent: *\nAllow: /'))
    asyncio.run(f.initialize())
    assert f.requests == 3


def test_timeout():
    def handler(request):
        raise httpx.ReadTimeout('slow')
    f = transport(handler)
    with pytest.raises(FetchError):
        asyncio.run(f.initialize())
    assert f.requests == 3


def test_redirect_blocked_before_network():
    calls = []
    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(302, headers={'Location': '/fr-fr/emploi/recherche.html?k=cyber'})
    f = transport(handler)
    f.policy = RobotsPolicy('User-agent: *\nAllow: /')
    with pytest.raises(PolicyError):
        asyncio.run(f.get(URL))
    assert calls == [URL]


def test_redirect_loop():
    f = transport(lambda req: httpx.Response(302, headers={'Location': URL}))
    f.policy = RobotsPolicy('User-agent: *\nAllow: /')
    with pytest.raises(FetchError, match='loop'):
        asyncio.run(f.get(URL))
    assert f.requests == 1


def pipeline(config, source=None, detail_status=200):
    calls = []
    def handler(req):
        calls.append(str(req.url))
        if req.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow: /*?')
        if '/emplois/' in req.url.path:
            return httpx.Response(detail_status, text=html('detail.html'))
        return httpx.Response(200, text=source or html())
    f = transport(handler)
    return asyncio.run(run(config, f, NOW)), calls


def test_pipeline_max_jobs_no_details():
    (rows, report), calls = pipeline(config(max_jobs=1, collect_job_details=False))
    assert len(rows) == report['unique_jobs'] == 1
    assert report['raw_jobs'] == 20
    assert len(calls) == 2


def test_pipeline_details_and_404():
    (rows, report), calls = pipeline(config(max_jobs=1))
    assert len(rows) == 1 and len(calls) == 3
    (rows, report), _ = pipeline(config(max_jobs=1), detail_status=404)
    assert not rows


def test_related_only_excluded():
    source = html().replace('<body>', '<body><p>Résultats proches</p>')
    (rows, _), _ = pipeline(config(collect_job_details=False), source)
    assert not rows


def test_global_duplicate_storm():
    from my_actor.dedup import JobIndex
    idx = JobIndex()
    for _ in range(100):
        idx.add(job())
    assert len(idx.jobs) == 1


def test_schemas_are_valid_json_schema():
    for path in (ROOT / '.actor').glob('*.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        if path.name == 'dataset_schema.json':
            jsonschema.Draft202012Validator.check_schema(data['fields'])
        if path.name == 'input_schema.json':
            jsonschema.Draft202012Validator.check_schema(data)
            jsonschema.validate(json.loads((ROOT / 'examples/input.json').read_text(encoding='utf-8')), data)


def test_description_match_is_distinct():
    j = job()
    j.matched_search_keywords = ['cloud']
    j.title_keyword_matches = []
    enrich_detail(j, html('detail.html'), NOW)
    assert j.description_keyword_matches == ['cloud']
    assert j.title_keyword_matches == []
    assert score([j])['keyword_depth'] == 3


def test_future_and_unknown_validity():
    j = job()
    source = html('detail.html').replace('2026-09-25T11:40:22Z', '2030-09-25T11:40:22Z')
    enrich_detail(j, source, NOW)
    assert 'Future datePosted ignored.' in j.warnings
    j = job()
    source = html('detail.html').replace('2026-10-25T11:40:22Z', 'unknown')
    enrich_detail(j, source, NOW)
    assert j.is_active is None


def test_missing_detail_structure_fails():
    with pytest.raises(ParserRegressionError):
        enrich_detail(job(), '<html><h1>Oops</h1></html>', NOW)


def test_unknown_age_excluded_from_pipeline():
    source = html().replace("moins d'une heure", 'unknown date')
    (rows, report), _ = pipeline(config(max_jobs=1, collect_job_details=False), source)
    assert not rows and report['unique_jobs'] == 1


def test_filtered_contract_and_related_opt_in():
    (rows, _), _ = pipeline(config(max_jobs=1, contract_types=['Stage'], collect_job_details=False))
    assert not rows
    source = html().replace('<body>', '<body><p>Résultats proches</p>')
    (rows, _), _ = pipeline(config(max_jobs=1, include_related_results=True, collect_job_details=False), source)
    assert rows[0]['roles'][0]['source_match_type'] == 'related'


def test_source_evidence_union_across_two_keywords():
    from my_actor.normalization import matches
    first = job()
    second = copy.deepcopy(first)
    second.matched_search_keywords = ['cloud']
    second.source_match_type = 'related'
    second.source_observations = [{'url': URL, 'match_type': 'related', 'keywords': ['cloud']}]
    idx = JobIndex()
    idx.add(first)
    idx.add(second)
    assert first.source_match_type == 'exact'
    assert first.matched_search_keywords == ['cybersecurite', 'cloud']
    assert len(first.source_observations) == 2
    assert matches('cloudnative cloud devops', ['cloud', 'dev']) == ['cloud']


def test_salary_and_remote_disclosure_do_not_impute_amounts():
    j = job()
    j.salary = salary('Selon profil €')
    j.has_remote_option = False
    assert score([j])['offer_transparency'] == 5
    assert j.salary['min'] is None


def test_large_retry_after_stops_without_early_retry():
    f = transport(lambda req: httpx.Response(429, headers={'Retry-After': '3600'}))
    with pytest.raises(FetchError, match='long Retry-After'):
        asyncio.run(f.initialize())
    assert f.requests == 1


def test_no_cookies_replayed():
    seen = []
    def handler(req):
        seen.append(req.headers.get('cookie'))
        return httpx.Response(200, text='User-agent: *\nAllow: /', headers={'Set-Cookie': 'user=secret'})
    f = transport(handler)
    async def check():
        await f.initialize()
        await f.get(URL)
    asyncio.run(check())
    assert seen == [None, None]


def test_sort_ties_are_stable():
    a, b = job(), job()
    a.company, b.company = 'Zulu', 'Alpha'
    rows = aggregate([a, b], config(), NOW.isoformat())
    assert [r['company'] for r in rows] == ['Alpha', 'Zulu']
    a.posting_age_days = 1
    b.posting_age_days = 2
    rows = aggregate([b, a], config(), NOW.isoformat())
    assert rows[0]['company'] == 'Zulu'


def test_related_no_text_never_gets_search_only_points():
    j = job()
    j.source_match_type = 'related'
    j.title_keyword_matches = []
    assert score([j])['keyword_depth'] == 0


def test_csharp_cpp_roles_remain_distinct():
    assert role_family('C++ Developer') != role_family('C# Developer')


def test_detail_replaces_unknown_age_warning():
    j = job()
    j.posting_age_days = None
    j.warnings.append('Unknown or lower-bound posting age; no freshness points.')
    enrich_detail(j, html('detail.html'), NOW)
    assert j.posting_age_days == 0
    assert not any('Unknown or lower-bound' in w for w in j.warnings)


def test_actor_file_references_and_output_version():
    folder = ROOT / '.actor'
    actor = json.loads((folder / 'actor.json').read_text(encoding='utf-8'))
    for key in ['dockerfile', 'readme', 'input', 'output']:
        assert (folder / actor[key]).is_file()
    output = json.loads((folder / actor['output']).read_text(encoding='utf-8'))
    assert output['actorOutputSchemaVersion'] == 1 and output['title']
    assert (folder / actor['storages']['dataset']).is_file()
