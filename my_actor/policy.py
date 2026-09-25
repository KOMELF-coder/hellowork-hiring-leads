"""Fail-closed URL policy, including every redirect target."""
import re
from urllib.parse import urlsplit, urlunsplit

from protego import Protego

USER_AGENT = 'FranceHiringSignals/1.0 (+https://github.com/KOMELF-coder/hellowork-hiring-leads)'
BASE = 'https://www.hellowork.com'
SEO = re.compile(r'/fr-fr/emploi/(?:mot-cle|metier)_[a-z0-9]+(?:[-_][a-z0-9]+)*\.html')
DETAIL = re.compile(r'/fr-fr/emplois/([0-9]+)\.html')


class PolicyError(ValueError):
    pass


def validate_url(url, kind='seo'):
    if not isinstance(url, str):
        raise PolicyError('URL must be a string')
    p = urlsplit(url)
    if (p.scheme != 'https' or p.netloc not in ('hellowork.com', 'www.hellowork.com')
            or '?' in url or '#' in url or '%' in url or '\\' in url):
        raise PolicyError(f'Unsafe public URL: {url}')
    pattern = SEO if kind == 'seo' else DETAIL
    if not pattern.fullmatch(p.path):
        raise PolicyError(f'Disallowed {kind} path: {p.path}')
    return urlunsplit(('https', 'www.hellowork.com', p.path, '', ''))


class RobotsPolicy:
    def __init__(self, text):
        if 'user-agent:' not in text.lower() or '<html' in text.lower():
            raise PolicyError('robots.txt is missing or not a robots document')
        self.rules = Protego.parse(text)

    def check(self, url, kind='seo'):
        url = validate_url(url, kind)
        if not self.rules.can_fetch(url, USER_AGENT):
            raise PolicyError(f'robots.txt disallows {url}')
        return url
