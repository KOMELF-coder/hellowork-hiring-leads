"""Conservative deterministic normalization; no enrichment or inferred clients."""
import html
import re
import unicodedata


def norm(value):
    text = unicodedata.normalize('NFKD', html.unescape(value or '').casefold())
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


def company_key(value):
    # Only an explicitly separated decorative suffix, not a word in a legal name.
    return re.sub(r'\s+[|–-]\s+recrutement$', '', norm(value))


def role_family(title):
    text = re.sub(r'\bh\s*/\s*f\b|\bf\s*/\s*h\b', '', norm(title))
    text = text.replace('c++', 'cplusplus').replace('c#', 'csharp').replace('.net', 'dotnet')
    words = re.findall(r'[a-z0-9]+', text)
    ignored = {'senior', 'junior', 'sr', 'jr', 'confirme', 'confirmee', 'expert', 'experimente', 'experimentee'}
    return ' '.join(sorted(w for w in words if w not in ignored))


def contract(value):
    n = norm(value)
    choices = {'cdi': 'CDI', 'cdd': 'CDD', 'alternance': 'Alternance', 'apprentissage': 'Alternance',
               'stage': 'Stage', 'stage de lycee': 'Stage', 'interim': 'Intérim', 'travail temporaire': 'Intérim',
               'freelance': 'Freelance', 'independant': 'Freelance', 'fonctionnaire': 'Fonctionnaire',
               'unknown': 'Unknown', 'other': 'Other'}
    return choices.get(n, 'Other' if n else 'Unknown')


def age(value):
    n = norm(value).replace('’', "'")
    if not n:
        return None, None
    if "moins d'une heure" in n or "moins de 1 heure" in n:
        return 0, None
    m = re.search(r'(\d+)\s*(minute|heure|jour|semaine|mois)', n)
    if not m:
        return None, None
    count, unit = int(m[1]), m[2]
    days = count * {'minute': 1 / 1440, 'heure': 1 / 24, 'jour': 1, 'semaine': 7, 'mois': 30}[unit]
    if 'plus de' in n:
        return None, int(days)
    return int(days), None


def salary(value):
    raw = value or None
    result = dict(raw=raw, min=None, max=None, currency=None, period='unknown')
    if not raw:
        return result
    n = norm(raw)
    if '€' in n or 'eur' in n:
        result['currency'] = 'EUR'
    for unit, period in [('an', 'year'), ('annuel', 'year'), ('mois', 'month'), ('mensuel', 'month'),
                         ('jour', 'day'), ('journalier', 'day'), ('heure', 'hour'), ('horaire', 'hour')]:
        if re.search(r'\b' + unit + r'\b', n):
            result['period'] = period
            break
    numbers = re.findall(r'\d+(?:[ \u202f\u00a0]\d{3})*(?:[,.]\d+)?\s*[kK]?', raw)
    amounts = []
    for token in numbers[:2]:
        compact = re.sub(r'\s', '', token).lower()
        amounts.append(float(compact.rstrip('k').replace(',', '.')) * (1000 if compact.endswith('k') else 1))
    if amounts and result['currency']:
        result.update(min=min(amounts), max=max(amounts))
    return result


def remote(value):
    n = norm(value)
    if not n or ('teletravail' not in n and 'remote' not in n):
        return None, []
    if any(t in n for t in ['pas de teletravail', 'sans teletravail', 'teletravail non']):
        return False, []
    modes = []
    for words, mode in [(['partiel', 'hybride'], 'partial'), (['occasionnel'], 'occasional'),
                        (['complet', '100%', '100 %', 'full remote', 'total'], 'full')]:
        if any(w in n for w in words):
            modes.append(mode)
    return True, modes


def location(value):
    result = dict(raw=value or None, city=None, department=None, region=None, country=None)
    # A displayed French department code is evidence; a bare city name is not geocoded.
    m = re.fullmatch(r'(.+?)\s+-\s+(\d{2}|2[AB]|97\d|98\d)', value or '')
    if m:
        result.update(city=m[1], department=m[2], country='France')
    elif norm(value) == 'france':
        result['country'] = 'France'
    return result


def matches(text, keywords):
    n = norm(text)
    return [k for k in keywords if re.search(r'(?<!\w)' + re.escape(norm(k)) + r'(?!\w)', n)]


def intermediary(company, description=''):
    # No brand list: evidence must explicitly describe the posting organization.
    n = norm(company)
    markers = ['cabinet de recrutement', "agence d'interim", 'agence interim', 'travail temporaire',
               'entreprise de services du numerique']
    if any(m in n for m in markers) or re.search(r'\besn\b', n):
        return True
    d = norm(description).replace('’', "'")
    patterns = [r'nous (?:sommes|recrutons pour) (?:un |une |le compte de )?(?:cabinet de recrutement|agence d.interim|nos clients|notre client)',
                r'notre (?:cabinet de recrutement|agence d.interim|esn)\b']
    return True if any(re.search(p, d) for p in patterns) else None
