"""Apify integration: one dataset item per company, no paid events."""
from apify import Actor

from .models import Config
from .scraper import run


async def main():
    async with Actor:
        config = Config.parse(await Actor.get_input() or {})
        rows, metrics = await run(config)
        await Actor.set_value('RUN_REPORT', metrics)
        if rows:
            await Actor.push_data(rows)
        Actor.log.info('Published %d company signals', len(rows))
