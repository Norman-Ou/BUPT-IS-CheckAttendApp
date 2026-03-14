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

DB_PATH = Path(__file__).parent / 'data' / 'attend.duckdb.bak.20260313-100126'


def export_xlsx(out_path: Path = None, filled_only: bool = False):
    if not DB_PATH.exists():
        print(f'ERROR: {DB_PATH} not found. Run import_xlsx.py first.')
        sys.exit(1)

    con = duckdb.connect(str(DB_PATH))

    query = "SELECT * FROM attend ORDER BY indexNo"
    if filled_only:
        query = "SELECT * FROM attend WHERE by != '' ORDER BY indexNo"

    df = con.execute(query).df()
    con.close()

    # ── Rename columns back to human-readable ─────────────────────
    df = df.rename(columns={
        'id':                     'ID',
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
        'photoUploaded':          'Photo Uploaded',
        'remark':                 'Remark',
    })

    if out_path is None:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = Path(__file__).parent / f'export_{ts}.xlsx'

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
