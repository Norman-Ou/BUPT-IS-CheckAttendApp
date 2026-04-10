"""
Scan all records via API, check OSS for each photo, and update photoUploaded=True if found.

Usage:
    python sync_photos.py
    python sync_photos.py --api http://127.0.0.1:17800
    python sync_photos.py --dry-run
"""

import argparse
import requests

DEFAULT_API    = 'http://127.0.0.1:17800'
OSS_BUCKET     = 'us-aisocial'
OSS_ENDPOINT   = 'oss-accelerate.aliyuncs.com'
OSS_PREFIX     = 'imggen_ugc/as-loki/home/ruizhe.ou/as-loki/attend/'

MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']


def build_photo_url(date_str: str, time_str: str, room: str) -> str:
    dd, mon_str = date_str.split('-')
    mo = MONTHS.index(mon_str) + 1
    start_str = time_str[:time_str.rfind('-')]
    hh, mm = start_str.split(':')
    filename = f'{mo}.{dd}_{hh}.{mm}_{room}.jpg'
    return f'https://{OSS_BUCKET}.{OSS_ENDPOINT}/{OSS_PREFIX}{filename}'


def oss_exists(url: str) -> bool:
    try:
        res = requests.head(url, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f'  [ERROR] HEAD {url}: {e}')
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default=DEFAULT_API)
    parser.add_argument('--dry-run', action='store_true', help='Check only, do not update DB')
    args = parser.parse_args()

    api = args.api.rstrip('/')

    # 1. Get all dates
    dates_res = requests.get(f'{api}/dates', timeout=10)
    dates_res.raise_for_status()
    dates = [d['date'] for d in dates_res.json()]
    print(f'Found {len(dates)} dates.')

    updated = 0
    skipped = 0

    for date in dates:
        records_res = requests.get(f'{api}/records', params={'date': date}, timeout=10)
        records_res.raise_for_status()
        records = records_res.json()

        for r in records:
            if r.get('photoUploaded'):
                skipped += 1
                continue  # already marked, skip

            url = build_photo_url(date, r['time'], r['room'])
            exists = oss_exists(url)

            status = 'FOUND' if exists else 'missing'
            print(f'  [{status}] {date} {r["time"]} {r["room"]} {r["moduleCode"]}  {url}')

            if exists and not args.dry_run:
                patch_res = requests.patch(
                    f'{api}/records/{r["id"]}',
                    json={'photoUploaded': True},
                    timeout=10,
                )
                if patch_res.ok:
                    print(f'    -> DB updated (id={r["id"]})')
                    updated += 1
                else:
                    print(f'    -> PATCH failed: {patch_res.status_code} {patch_res.text}')
            elif exists and args.dry_run:
                print(f'    -> (dry-run, skipped PATCH)')
                updated += 1

    print(f'\nDone. Already marked: {skipped}, Updated: {updated}.')


if __name__ == '__main__':
    main()
