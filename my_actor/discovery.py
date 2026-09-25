"""Small observed URL catalog; never guess unknown slugs or city codes."""
import json
import re
from pathlib import Path

from .normalization import norm
from .policy import BASE, validate_url


def url_keywords(url):
    slug = url.rsplit('/', 1)[-1].removesuffix('.html')
    topic = re.split(r'-(?:ville|region)_', re.sub(r'^(mot-cle|metier)_', '', slug))[0]
    return [topic.replace('-', ' ')]


def resolve(config):
    if config.start_urls:
        return [(validate_url(u), config.keywords or url_keywords(u)) for u in config.start_urls], []
    catalog = json.loads(Path(__file__).with_name('seo_catalog.json').read_text(encoding='utf-8'))
    targets, warnings = [], []
    locality = norm(config.location) or 'france'
    for keyword in config.keywords:
        path = catalog.get(norm(keyword), {}).get(locality)
        if not path:
            warnings.append(f'Unsupported SEO keyword/location ignored: {keyword} / {config.location or "France"}')
            continue
        targets.append((validate_url(BASE + path), [keyword]))
    return targets, warnings
