"""
Update attend.duckdb from a new Excel export (produced by export_xlsx.py).

Only rows with date >= cutoff are touched in the DB.
Rows before the cutoff remain completely untouched.

Usage:
    python update_duckdb.py                              # default xlsx / cutoff
    python update_duckdb.py --xlsx /path/to/file.xlsx
    python update_duckdb.py --cutoff 2026-03-10          # change cutoff (inclusive)
    python update_duckdb.py --year 2026                  # year used to parse "D-Mon" dates
    python update_duckdb.py --dry-run                    # preview without writing
"""

import sys
import argparse
import duckdb
import pandas as pd
from pathlib import Path
from datetime import date

DB_PATH      = Path(__file__).parent / 'data' / 'attend.duckdb'
XLSX_DEFAULT = Path(__file__).parent / '2026-03-09-2255-export.xlsx'

CUTOFF_DEFAULT = date(2026, 3, 10)   # inclusive
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
    p.add_argument('--year',    type=int, default=YEAR_DEFAULT,
                   help='Year assumed when parsing "D-Mon" date strings (default: 2026)')
    p.add_argument('--dry-run', action='store_true',
                   help='Show what would change without writing to DB')
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

    if 'id' not in df.columns:
        df['id'] = df['indexNo'].astype(int).astype(str)

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

    # ── Filter: only rows on/after cutoff ─────────────────────────────────────
    mask    = df['_date_dt'].notna() & (df['_date_dt'].dt.date >= cutoff)
    df_new  = df[mask].copy()
    df_skip = df[~mask]

    print(f'\nCutoff: {cutoff} (inclusive)')
    print(f'  Rows in xlsx total        : {len(df)}')
    print(f'  Rows BEFORE cutoff (skip) : {len(df_skip)}')
    print(f'  Rows ON/AFTER cutoff      : {len(df_new)}')

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

    if args.dry_run:
        print('\n[DRY RUN] Would upsert:')
        print(df_new[['id', 'date', 'day', 'time', 'moduleCode']].to_string(index=False))
        print(f'\nTotal: {len(df_new)} rows — no changes written.')
        return

    # ── Write to DuckDB ───────────────────────────────────────────────────────
    con = duckdb.connect(str(DB_PATH))

    ids_str = ', '.join(f"'{i}'" for i in df_new['id'].tolist())
    existing = con.execute(
        f"SELECT COUNT(*) FROM attend WHERE id IN ({ids_str})"
    ).fetchone()[0]
    new_inserts = len(df_new) - existing

    print(f'\n  Existing rows to overwrite : {existing}')
    print(f'  New rows to insert         : {new_inserts}')

    con.register('df_new', df_new)

    if existing:
        con.execute(f"DELETE FROM attend WHERE id IN ({ids_str})")

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
