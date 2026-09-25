import asyncio
import logging
import random
import ssl
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import httpx

from .policy import BASE, USER_AGENT, PolicyError, RobotsPolicy

log = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


class Fetcher:
    def __init__(self, client=None, sleep=asyncio.sleep, jitter=True):
        self.client = client or httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False,
                                                  verify=ssl.create_default_context(),
                                                  headers={'User-Agent': USER_AGENT},
                                                  limits=httpx.Limits(max_connections=4, max_keepalive_connections=4))
        self.sleep, self.jitter = sleep, jitter
        self.policy = None
        self.requests = 0
        self._pace_lock = asyncio.Lock()
        self._last_request_started = 0.0

    async def _pace(self):
        """Globally pace request starts while still allowing several in-flight requests."""
        if not self.jitter:
            return
        async with self._pace_lock:
            loop = asyncio.get_running_loop()
            # Keep aggregate traffic around 2–3 requests/second, with slight jitter
            # to avoid synchronized bursts when multiple detail tasks are waiting.
            min_interval = random.uniform(0.35, 0.50)
            elapsed = loop.time() - self._last_request_started
            if elapsed < min_interval:
                await self.sleep(min_interval - elapsed)
            self._last_request_started = loop.time()

    async def close(self):
        await self.client.aclose()

    async def _request(self, url):
        for attempt in range(3):
            await self._pace()
            try:
                # Public unauthenticated HTTP only; never replay Set-Cookie.
                self.client.cookies.clear()
                self.requests += 1
                response = await self.client.get(url, headers={'User-Agent': USER_AGENT}, follow_redirects=False)
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt == 2:
                    raise FetchError(f'HTTP timeout/network failure after 3 attempts: {url}') from error
                log.warning('Transient network error on %s; retry %d', url, attempt + 1)
                await self.sleep(2 ** (attempt + 1))
                continue
            if response.status_code not in (403, 429) and response.status_code < 500:
                if len(response.content) > 5_000_000:
                    raise FetchError('Response exceeds 5 MB safety limit')
                return response
            if attempt == 2:
                raise FetchError(f'Persistent HTTP {response.status_code} after 3 attempts: {url}')
            delay = 2 ** (attempt + 1)
            retry = response.headers.get('Retry-After', '')
            if retry:
                try:
                    seconds = float(retry)
                except ValueError:
                    try:
                        seconds = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                    except (ValueError, TypeError):
                        seconds = 0
                if seconds > 60:
                    raise FetchError(f'Server requests long Retry-After ({retry}); stopping politely')
                delay = max(delay, seconds)
            log.warning('HTTP %d on %s; retry %d', response.status_code, url, attempt + 1)
            await self.sleep(delay)
        raise FetchError('Retry limit exhausted')

    async def initialize(self):
        response = await self._request(BASE + '/robots.txt')
        if response.status_code != 200:
            raise PolicyError(f'Cannot validate robots.txt: HTTP {response.status_code}')
        self.policy = RobotsPolicy(response.text)

    async def get(self, url, kind='seo'):
        if self.policy is None:
            raise PolicyError('robots.txt must be checked first')
        visited = set()
        for _ in range(4):
            url = self.policy.check(url, kind)
            if url in visited:
                raise FetchError(f'Redirect loop: {url}')
            visited.add(url)
            response = await self._request(url)
            if response.is_redirect:
                target = response.headers.get('Location')
                if not target:
                    raise FetchError('Redirect without Location')
                url = urljoin(url, target)
                self.policy.check(url, kind)  # Reject BEFORE fetching the target.
                continue
            if response.status_code not in (200, 404, 410):
                raise FetchError(f'Unexpected HTTP {response.status_code}: {url}')
            return response
        raise FetchError('Redirect limit reached')
