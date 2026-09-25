"""Explicit network validation, intentionally separate from offline pytest."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jsonschema

from my_actor.fetching import Fetcher
from my_actor.models import Config
from my_actor.scraper import run


async def main():
    manifest = json.loads(Path('fixtures/manifest.json').read_text(encoding='utf-8'))
    schema = json.loads(Path('.actor/dataset_schema.json').read_text(encoding='utf-8'))['fields']
    reports = []
    for entry in manifest:
        data = {'start_urls': [entry['url']], 'posted_within_days': 90, 'collect_job_details': False}
        rows, report = await run(Config.parse(data))
        for row in rows:
            jsonschema.validate(row, schema)
        report['input'] = data
        reports.append(report)
        print(json.dumps({'url': entry['url'], 'raw': report['raw_jobs'], 'unique': report['unique_jobs'], 'companies': len(rows)}), flush=True)
    rows, report = await run(Config.parse({'keywords': ['cybersecurite', 'devops'], 'collect_job_details': False}))
    report['name'] = 'multi_keyword_14d'
    reports.append(report)
    for row in rows:
        jsonschema.validate(row, schema)
    Path('investigation/live-report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    Path('examples/live-companies.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    # A bounded real detail run (no recommended-job traversal).
    rows, detail_report = await run(Config.parse({'keywords': ['cybersecurite'], 'max_jobs': 3}))
    for row in rows:
        jsonschema.validate(row, schema)
    Path('investigation/live-detail-report.json').write_text(json.dumps(detail_report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'detail': detail_report}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
