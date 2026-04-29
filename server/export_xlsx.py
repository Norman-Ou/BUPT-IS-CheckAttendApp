"""
Export server/data/attend.duckdb → Excel (.xlsx)

Usage:
    python export_xlsx.py
    python export_xlsx.py --out /path/to/output.xlsx
    python export_xlsx.py --filled-only       # only rows where someone filled in data

Output file defaults to: server/export_YYYYMMDD_HHMMSS.xlsx
"""

import sys
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime
from config import SERVER_DB_PATH, SERVER_EXPORT_XLSX_PATH

DB_PATH = SERVER_DB_PATH


def export_xlsx(out_path: Path = None, filled_only: bool = False):
    if not DB_PATH.exists():
        print(f'ERROR: {DB_PATH} not found. Run import_xlsx.py first.')
        sys.exit(1)

    con = duckdb.connect(str(DB_PATH))

    base_filter = '"hidden" IS NOT TRUE'
    if filled_only:
        query = f'SELECT * FROM attend WHERE {base_filter} AND "by" != \'\''
    else:
        query = f'SELECT * FROM attend WHERE {base_filter}'

    df = con.execute(query).df()
    con.close()

    # ── Sort by date (parsed from "D-Mon") then time ───────────────
    df['_sort_date'] = pd.to_datetime(df['date'] + '-2026', format='%d-%b-%Y', errors='coerce')
    df = df.sort_values(['_sort_date', 'time']).drop(columns=['_sort_date'])

    # ── Drop unwanted columns ──────────────────────────────────────
    df = df.drop(columns=['id', 'photoUploaded', 'hidden'], errors='ignore')

    # ── Rename columns back to human-readable ─────────────────────
    df = df.rename(columns={
        'indexNo':                'Index No.',
        'week':                   'Week',
        'day':                    'Day',
        'date':                   'Date',
        'time':                   'Time',
        'room':                   'Room',
        'moduleCode':             'Module Code',
        'moduleName':             'Module Name',
        'lecturer':               'Lecturer',
        'year':                   'Year',
        'programme':              'Programme',
        'class_':                 'Class',
        'totalStudentNum':        'Total Student Num',
        'studentNumInClassroom':  'Student Num In Classroom',
        'percent':                'Percent (%)',
        'by':                     'Filled By',
        'remark':                 'Remark',
    })

    if out_path is None:
        out_path = SERVER_EXPORT_XLSX_PATH

    df.to_excel(out_path, index=False)
    print(f'Exported {len(df)} records → {out_path}')


if __name__ == '__main__':
    args = sys.argv[1:]
    out  = None
    filled_only = '--filled-only' in args

    if '--out' in args:
        idx = args.index('--out')
        out = Path(args[idx + 1])

    export_xlsx(out_path=out, filled_only=filled_only)
