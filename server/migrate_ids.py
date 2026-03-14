"""
One-time migration: recompute all id values in attend.duckdb
from str(indexNo) → sha256(week|day|date|time|moduleCode|moduleName|lecturer)[:16]

Usage:
    python migrate_ids.py           # dry-run (shows collisions / changes)
    python migrate_ids.py --apply   # actually write to DB (backs up first)
"""

import hashlib
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path(__file__).parent / 'data' / 'attend.duckdb'


def make_id(week, day, date, time, room, moduleCode, moduleName, lecturer) -> str:
    key = f"{week}|{day}|{date}|{time}|{room}|{moduleCode}|{moduleName}|{lecturer}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def main():
    apply = '--apply' in sys.argv

    if not DB_PATH.exists():
        print(f'ERROR: {DB_PATH} not found')
        sys.exit(1)

    con = duckdb.connect(str(DB_PATH), read_only=not apply)
    df = con.execute('SELECT * FROM attend').df()

    df['new_id'] = df.apply(
        lambda r: make_id(r['week'], r['day'], r['date'], r['time'],
                          r['room'], r['moduleCode'], r['moduleName'], r['lecturer']),
        axis=1,
    )

    changed = df[df['id'] != df['new_id']]
    print(f'Total rows      : {len(df)}')
    print(f'IDs to update   : {len(changed)}')
    print(f'IDs unchanged   : {len(df) - len(changed)}')

    # Check for hash collisions
    dupes = df['new_id'].duplicated(keep=False)
    if dupes.any():
        print('\nWARNING: hash collisions detected:')
        print(df[dupes][['id', 'new_id', 'week', 'day', 'date', 'time', 'moduleCode']].to_string())
        sys.exit(1)
    else:
        print('No hash collisions.')

    if not apply:
        print('\n[DRY RUN] Sample of changes (first 10):')
        print(changed[['id', 'new_id', 'date', 'time', 'moduleCode']].head(10).to_string(index=False))
        print('\nRun with --apply to write changes.')
        con.close()
        return

    # Backup
    ts = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    backup = DB_PATH.with_name(f'attend.duckdb.bak.{ts}')
    con.close()
    shutil.copy2(DB_PATH, backup)
    print(f'\nBackup saved: {backup}')

    con = duckdb.connect(str(DB_PATH))
    for _, row in changed.iterrows():
        con.execute("UPDATE attend SET id=? WHERE id=?", [row['new_id'], row['id']])
    con.close()
    print(f'Done. Updated {len(changed)} IDs.')


if __name__ == '__main__':
    main()
