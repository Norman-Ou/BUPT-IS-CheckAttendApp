"""
Update attend.duckdb from a new Excel export (produced by export_xlsx.py).

Only rows with date >= cutoff are touched in the DB.
Rows before the cutoff remain completely untouched.

Usage:
    python update_duckdb.py                              # dry-run by default
    python update_duckdb.py --update                     # actually write to DB
    python update_duckdb.py --xlsx /path/to/file.xlsx
    python update_duckdb.py --cutoff 2026-03-10          # change cutoff (inclusive)
    python update_duckdb.py --until 2026-03-06           # only update up to this date
    python update_duckdb.py --year 2026                  # year used to parse "D-Mon" dates
"""

import hashlib
import shutil
import sys
import argparse
import duckdb
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
from config import SERVER_DB_PATH, SERVER_UPDATE_XLSX_PATH


def make_id(week, day, date, time, room, moduleCode, moduleName, lecturer) -> str:
    """Stable hash ID derived from immutable session fields."""
    key = f"{week}|{day}|{date}|{time}|{room}|{moduleCode}|{moduleName}|{lecturer}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

DB_PATH      = SERVER_DB_PATH
XLSX_DEFAULT = SERVER_UPDATE_XLSX_PATH

CUTOFF_DEFAULT = (datetime.now(timezone(timedelta(hours=8))) + timedelta(days=1)).date()  # next day UTC+8
YEAR_DEFAULT   = 2026


# ── Column maps ────────────────────────────────────────────────────────────────
# Supports both the raw-import format and the export_xlsx.py format.
RENAME_ORIGINAL = {
    'Index No.':                   'indexNo',
    'Week':                        'week',
    'Day':                         'day',
    'Date':                        'date',
    'Time':                        'time',
    'Room':                        'room',
    'Module Code':                 'moduleCode',
    'Module Name':                 'moduleName',
    'Lecturer':                    'lecturer',
    'Year':                        'year',
    'Programme':                   'programme',
    'Class':                       'class_',
    'Total student num':           'totalStudentNum',
    'Student number in classroom': 'studentNumInClassroom',
    'Percent':                     'percent',
    'By':                          'by',
    'Remark':                      'remark',
}

RENAME_EXPORT = {
    'ID':                       'id',
    'Index No.':                'indexNo',
    'Week':                     'week',
    'Day':                      'day',
    'Date':                     'date',
    'Time':                     'time',
    'Room':                     'room',
    'Module Code':              'moduleCode',
    'Module Name':              'moduleName',
    'Lecturer':                 'lecturer',
    'Year':                     'year',
    'Programme':                'programme',
    'Class':                    'class_',
    'Total Student Num':        'totalStudentNum',
    'Student Num In Classroom': 'studentNumInClassroom',
    'Percent (%)':              'percent',
    'Filled By':                'by',
    'Photo Uploaded':           'photoUploaded',
    'Remark':                   'remark',
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--xlsx',    default=str(XLSX_DEFAULT))
    p.add_argument('--cutoff',  default=str(CUTOFF_DEFAULT),
                   help='Cutoff date YYYY-MM-DD (inclusive). Rows on/after are updated.')
    p.add_argument('--until',   default=None,
                   help='Upper bound date YYYY-MM-DD (inclusive). Rows after are skipped.')
    p.add_argument('--year',    type=int, default=YEAR_DEFAULT,
                   help='Year assumed when parsing "D-Mon" date strings (default: 2026)')
    p.add_argument('--update', action='store_true',
                   help='Actually write changes to DB (default is dry-run)')
    return p.parse_args()


def parse_dmon(series: pd.Series, year: int) -> pd.Series:
    """Parse "D-Mon" strings (e.g. "10-Mar") into pd.Timestamp using a fixed year."""
    def _parse(val):
        if pd.isna(val) or str(val).strip() == '':
            return pd.NaT
        try:
            return pd.to_datetime(f"{val}-{year}", format='%d-%b-%Y')
        except Exception:
            return pd.NaT
    return series.apply(_parse)


def load_xlsx(xlsx_path: Path, year: int) -> pd.DataFrame:
    print(f'Reading {xlsx_path} ...')
    df = pd.read_excel(xlsx_path)
    cols = set(df.columns)

    # ── Detect format and rename ───────────────────────────────────────────────
    is_export = 'ID' in cols or 'Filled By' in cols or 'Percent (%)' in cols
    if is_export:
        print('Detected: export_xlsx.py format')
        df = df.rename(columns=RENAME_EXPORT)
    else:
        print('Detected: original attendance.xlsx format')
        df = df.rename(columns=RENAME_ORIGINAL)

    # ── Date parsing ──────────────────────────────────────────────────────────
    # Regardless of how pandas read the date column (string "D-Mon" or datetime
    # with a wrong/missing year), we always extract only day+month and rebuild
    # the date using the explicit --year argument.
    if df['date'].dtype == object:
        raw_dt = parse_dmon(df['date'], year)
    else:
        # pandas read it as datetime (possibly with wrong year like 0001)
        raw_dt = pd.to_datetime(df['date'], errors='coerce')

    # Re-anchor to the correct year using only day+month from whatever was parsed
    def anchor_year(dt, yr):
        if pd.isna(dt):
            return pd.NaT
        try:
            return pd.Timestamp(yr, dt.month, dt.day)
        except Exception:
            return pd.NaT

    df['_date_dt'] = raw_dt.apply(lambda d: anchor_year(d, year))
    df['date']     = df['_date_dt'].apply(
        lambda d: f"{d.day}-{d.strftime('%b')}" if pd.notna(d) else ''
    )

    # ── Common field cleanup ──────────────────────────────────────────────────
    df['day']    = df['day'].fillna('').astype(str)
    df['remark'] = df['remark'].fillna('').astype(str)

    # Always recompute id from session fields (ignore any id column in xlsx)
    df['id'] = df.apply(
        lambda r: make_id(r['week'], r['day'], r['date'], r['time'],
                          r['room'], r['moduleCode'], r['moduleName'], r['lecturer']),
        axis=1,
    )

    df['studentNumInClassroom'] = df.get('studentNumInClassroom',
                                         pd.Series(dtype=float)).fillna(0).astype(int)
    df['percent']               = df.get('percent',
                                         pd.Series(dtype=float)).fillna(0.0).astype(float)
    df['by']                    = df.get('by',
                                         pd.Series(dtype=str)).fillna('').astype(str)
    if 'photoUploaded' not in df.columns:
        df['photoUploaded'] = False

    return df


def main():
    args = parse_args()
    xlsx_path = Path(args.xlsx)
    cutoff    = pd.Timestamp(args.cutoff).date()
    until     = pd.Timestamp(args.until).date() if args.until else None

    if not xlsx_path.exists():
        print(f'ERROR: {xlsx_path} not found')
        sys.exit(1)
    if not DB_PATH.exists():
        print(f'ERROR: {DB_PATH} not found — run import_xlsx.py first')
        sys.exit(1)

    df = load_xlsx(xlsx_path, args.year)

    # ── Show date range in xlsx for debugging ─────────────────────────────────
    valid_dates = df['_date_dt'].dropna()
    if not valid_dates.empty:
        print(f'Date range in xlsx: {valid_dates.min().date()} → {valid_dates.max().date()}')
    else:
        print('WARNING: No valid dates found in xlsx!')

    # ── Filter: only rows within [cutoff, until] ──────────────────────────────
    mask = df['_date_dt'].notna() & (df['_date_dt'].dt.date >= cutoff)
    if until:
        mask &= df['_date_dt'].dt.date <= until
    df_new  = df[mask].copy()
    df_skip = df[~mask]

    range_str = f'{cutoff} → {until}' if until else f'{cutoff} → (no limit)'
    print(f'\nDate range: {range_str} (inclusive)')
    print(f'  Rows in xlsx total        : {len(df)}')
    print(f'  Rows outside range (skip) : {len(df_skip)}')
    print(f'  Rows in range             : {len(df_new)}')

    if df_new.empty:
        print('Nothing to update.')
        return

    cols = [
        'id', 'indexNo', 'week', 'day', 'date', 'time', 'room',
        'moduleCode', 'moduleName', 'lecturer', 'year', 'programme',
        'class_', 'totalStudentNum', 'studentNumInClassroom',
        'percent', 'by', 'photoUploaded', 'remark',
    ]
    df_new = df_new[cols]

    if not args.update:
        con_ro = duckdb.connect(str(DB_PATH), read_only=True)
        con_ro.register('df_new', df_new)
        existing_dry = con_ro.execute('''
            SELECT COUNT(*) FROM attend a
            JOIN df_new n ON a.date=n.date AND a.time=n.time AND a.room=n.room
        ''').fetchone()[0]
        con_ro.close()
        print('\n[DRY RUN] Would upsert:')
        print(df_new[['id', 'date', 'day', 'time', 'moduleCode']].to_string(index=False))
        print(f'\n  Matched by (date,time,room) : {existing_dry} existing rows would be replaced')
        print(f'  New rows to insert         : {len(df_new) - existing_dry}')
        print(f'\nTotal: {len(df_new)} rows — no changes written. Pass --update to apply.')
        return

    # ── Backup DuckDB before writing ──────────────────────────────────────────
    ts = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    backup_path = DB_PATH.with_name(f'attend.duckdb.bak.{ts}')
    shutil.copy2(DB_PATH, backup_path)
    print(f'\nBackup saved: {backup_path}')

    # ── Write to DuckDB ───────────────────────────────────────────────────────
    con = duckdb.connect(str(DB_PATH))

    # Match by natural key (date, time, room) — stable across xlsx re-exports
    # with different indexNo numbering.
    con.register('df_new', df_new)

    existing = con.execute('''
        SELECT COUNT(*) FROM attend a
        JOIN df_new n ON a.date=n.date AND a.time=n.time AND a.room=n.room
    ''').fetchone()[0]
    new_inserts = len(df_new) - existing

    print(f'\n  Existing rows to overwrite : {existing}')
    print(f'  New rows to insert         : {new_inserts}')

    # Carry over mutable fields from DB into df_new where DB has real data
    # (so filled attendance numbers are not lost when static fields are refreshed)
    mutable = ['studentNumInClassroom', 'percent', 'by', 'photoUploaded']
    if existing:
        db_mutable = con.execute('''
            SELECT a.date, a.time, a.room,
                   a.studentNumInClassroom, a.percent, a.by, a.photoUploaded
            FROM attend a
            JOIN df_new n ON a.date=n.date AND a.time=n.time AND a.room=n.room
            WHERE a.studentNumInClassroom > 0 OR a.by != '' OR a.photoUploaded = true
        ''').df()

        if not db_mutable.empty:
            df_new = df_new.merge(
                db_mutable.rename(columns={c: f'_db_{c}' for c in mutable}),
                on=['date', 'time', 'room'], how='left'
            )
            for col in mutable:
                db_col = f'_db_{col}'
                if db_col not in df_new.columns:
                    continue
                filled = df_new[db_col].notna()
                if col == 'studentNumInClassroom':
                    filled &= df_new[db_col] > 0
                elif col == 'by':
                    filled &= df_new[db_col] != ''
                elif col == 'photoUploaded':
                    filled &= df_new[db_col] == True
                df_new.loc[filled, col] = df_new.loc[filled, db_col]
                df_new.drop(columns=[db_col], inplace=True)
            print(f'  Mutable data carried over  : {len(db_mutable)} rows')
            con.unregister('df_new')
            con.register('df_new', df_new)

        con.execute('''
            DELETE FROM attend WHERE (date, time, room) IN (
                SELECT date, time, room FROM df_new
            )
        ''')

    con.execute("INSERT INTO attend SELECT * FROM df_new")

    total = con.execute("SELECT COUNT(*) FROM attend").fetchone()[0]
    print(f'\nDone. attend table now has {total} rows.')

    sample = con.execute(
        "SELECT id, date, day, time, moduleCode FROM attend ORDER BY indexNo DESC LIMIT 5"
    ).fetchdf()
    print('\nSample (last 5 by indexNo):')
    print(sample.to_string(index=False))

    con.close()


if __name__ == '__main__':
    main()
