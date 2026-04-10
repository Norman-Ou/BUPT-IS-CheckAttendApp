"""
Scan all records via API, check OSS for each photo, and update photoUploaded accordingly.
Uses 10 concurrent async workers.

Usage:
    python sync_photos.py
    python sync_photos.py --api http://127.0.0.1:17800
    python sync_photos.py --dry-run
"""

import argparse
import asyncio
from datetime import date, timedelta

import aiohttp

DEFAULT_API  = 'http://127.0.0.1:17800'
OSS_BUCKET   = 'us-aisocial'
OSS_ENDPOINT = 'oss-accelerate.aliyuncs.com'
OSS_PREFIX   = 'imggen_ugc/as-loki/home/ruizhe.ou/as-loki/attend/'
MONTHS       = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
CONCURRENCY  = 10


def parse_date(date_str: str) -> date:
    dd, mon_str = date_str.split('-')
    return date(date.today().year, MONTHS.index(mon_str) + 1, int(dd))


def build_photo_url(date_str: str, time_str: str, room: str) -> str:
    dd, mon_str = date_str.split('-')
    mo = MONTHS.index(mon_str) + 1
    start_str = time_str[:time_str.rfind('-')]
    hh, mm = start_str.split(':')
    return f'https://{OSS_BUCKET}.{OSS_ENDPOINT}/{OSS_PREFIX}{mo}.{dd}_{hh}.{mm}_{room}.jpg'


async def process_record(session: aiohttp.ClientSession, api: str, date_str: str, r: dict,
                         sem: asyncio.Semaphore, dry_run: bool) -> int:
    """Returns 1 if DB was updated (or would be), 0 if already in sync."""
    db_value = bool(r.get('photoUploaded'))
    url = build_photo_url(date_str, r['time'], r['room'])

    async with sem:
        try:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as res:
                exists = res.status == 200
        except Exception as e:
            print(f'  [ERROR] HEAD {url}: {e}')
            return 0

    if exists == db_value:
        return 0

    status = 'FOUND  ' if exists else 'missing'
    print(f'  [{status}] {date_str} {r["time"]} {r["room"]} {r["moduleCode"]} -> photoUploaded={exists}')

    if dry_run:
        print(f'    -> (dry-run, skipped PATCH)')
        return 1

    async with sem:
        try:
            async with session.patch(
                f'{api}/records/{r["id"]}',
                json={'photoUploaded': exists},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as res:
                if res.ok:
                    print(f'    -> DB updated (id={r["id"]})')
                    return 1
                else:
                    text = await res.text()
                    print(f'    -> PATCH failed: {res.status} {text}')
                    return 0
        except Exception as e:
            print(f'    -> PATCH error: {e}')
            return 0


async def main_async(api: str, dry_run: bool):
    async with aiohttp.ClientSession() as session:
        # 1. Fetch all dates
        async with session.get(f'{api}/dates', timeout=aiohttp.ClientTimeout(total=10)) as res:
            res.raise_for_status()
            all_dates = await res.json()

        cutoff = date.today() + timedelta(days=1)
        dates = [d['date'] for d in all_dates if parse_date(d['date']) <= cutoff]
        print(f'Found {len(dates)} dates (up to {cutoff}).')

        # 2. Fetch all records for each date
        tasks_input = []
        for date_str in dates:
            async with session.get(
                f'{api}/records', params={'date': date_str},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as res:
                res.raise_for_status()
                records = await res.json()
            tasks_input.extend((date_str, r) for r in records)

        print(f'Total records to check: {len(tasks_input)}')

        # 3. Process all records concurrently (max 10)
        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = [
            process_record(session, api, date_str, r, sem, dry_run)
            for date_str, r in tasks_input
        ]
        results = await asyncio.gather(*tasks)

    updated = sum(results)
    skipped = len(results) - updated
    print(f'\nDone. In sync: {skipped}, Updated: {updated}.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default=DEFAULT_API)
    parser.add_argument('--dry-run', action='store_true', help='Check only, do not update DB')
    args = parser.parse_args()
    asyncio.run(main_async(args.api.rstrip('/'), args.dry_run))


if __name__ == '__main__':
    main()
