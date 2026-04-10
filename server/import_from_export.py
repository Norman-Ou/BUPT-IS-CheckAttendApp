"""
Import an export_xlsx.py-generated .xlsx back into attend.duckdb

Usage:
    python import_from_export.py                        # uses default export filename
    python import_from_export.py --in /path/to/file.xlsx
    python import_from_export.py --preserve             # keep existing mutable fill data

The "exported" xlsx uses human-readable column names and omits id/photoUploaded.
This script reverses that: renames columns, recomputes stable hash IDs,
and writes (or updates) data/attend.duckdb.
"""

import hashlib
import sys
import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent / 'data' / 'attend.duckdb'

# Default input: same name export_xlsx.py uses
DEFAULT_IN = Path(__file__).parent / '2526 Sem2-Student Attendance.xlsx'


def make_id(week, day, date, time, room, moduleCode, moduleName, lecturer) -> str:
    key = f"{week}|{day}|{date}|{time}|{room}|{moduleCode}|{moduleName}|{lecturer}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def import_from_export(in_path: Path = None, preserve: bool = False):
    if in_path is None:
        in_path = DEFAULT_IN
    if not in_path.exists():
        print(f'ERROR: {in_path} not found.')
        sys.exit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f'Reading {in_path} ...')
    df = pd.read_excel(in_path)

    # ── Rename exported human-readable headers back to DB column names ──
    df = df.rename(columns={
        'Index No.':              'indexNo',
        'Week':                   'week',
        'Day':                    'day',
        'Date':                   'date',
        'Time':                   'time',
        'Room':                   'room',
        'Module Code':            'moduleCode',
        'Module Name':            'moduleName',
        'Lecturer':               'lecturer',
        'Year':                   'year',
        'Programme':              'programme',
        'Class':                  'class_',
        'Total Student Num':      'totalStudentNum',
        'Student Num In Classroom': 'studentNumInClassroom',
        'Percent (%)':            'percent',
        'Filled By':              'by',
        'Remark':                 'remark',
    })

    # ── Date: normalise to "D-Mon" string ──────────────────────────────
    def _to_dmon(val):
        if pd.isna(val) if not isinstance(val, str) else False:
            return ''
        if isinstance(val, str):
            return val
        d = pd.to_datetime(val, errors='coerce')
        return f"{d.day}-{d.strftime('%b')}" if pd.notna(d) else ''

    df['date'] = df['date'].apply(_to_dmon)
    df['day']  = df['day'].fillna('').astype(str)

    # ── Regenerate stable hash ID (not stored in export) ───────────────
    df['id'] = df.apply(
        lambda r: make_id(r['week'], r['day'], r['date'], r['time'],
                          r['room'], r['moduleCode'], r['moduleName'], r['lecturer']),
        axis=1,
    )

    # ── Mutable fields ──────────────────────────────────────────────────
    df['studentNumInClassroom'] = pd.to_numeric(df.get('studentNumInClassroom', 0), errors='coerce').fillna(0).astype(int)
    df['percent']               = pd.to_numeric(df.get('percent', 0.0), errors='coerce').fillna(0.0).astype(float)
    df['by']                    = df.get('by', pd.Series(dtype=str)).fillna('').astype(str)
    df['photoUploaded']         = False
    df['remark']                = df['remark'].fillna('').astype(str)

    # ── Final column order ──────────────────────────────────────────────
    cols = [
        'id', 'indexNo', 'week', 'day', 'date', 'time', 'room',
        'moduleCode', 'moduleName', 'lecturer', 'year', 'programme',
        'class_', 'totalStudentNum', 'studentNumInClassroom',
        'percent', 'by', 'photoUploaded', 'remark',
    ]
    df = df[cols]

    # ── Write to DuckDB ─────────────────────────────────────────────────
    con = duckdb.connect(str(DB_PATH))

    table_exists = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='attend'"
    ).fetchone()[0]

    if preserve and table_exists:
        print('Preserving existing fill data ...')
        con.execute("CREATE TEMP TABLE new_data AS SELECT * FROM df")
        con.execute("""
            UPDATE attend a
            SET
                week            = n.week,
                day             = n.day,
                date            = n.date,
                time            = n.time,
                room            = n.room,
                moduleCode      = n.moduleCode,
                moduleName      = n.moduleName,
                lecturer        = n.lecturer,
                year            = n.year,
                programme       = n.programme,
                class_          = n.class_,
                totalStudentNum = n.totalStudentNum,
                remark          = n.remark
            FROM new_data n
            WHERE a.id = n.id
        """)
        inserted = con.execute("""
            SELECT COUNT(*) FROM new_data n
            WHERE NOT EXISTS (SELECT 1 FROM attend a WHERE a.id = n.id)
        """).fetchone()[0]
        if inserted:
            con.execute("""
                INSERT INTO attend
                SELECT * FROM new_data n
                WHERE NOT EXISTS (SELECT 1 FROM attend a WHERE a.id = n.id)
            """)
            print(f'Inserted {inserted} new rows; static fields updated; mutable fields preserved.')
        else:
            print('Static fields updated; mutable fields preserved.')
    else:
        con.execute("DROP TABLE IF EXISTS attend")
        con.execute("CREATE TABLE attend AS SELECT * FROM df")
        count = con.execute("SELECT COUNT(*) FROM attend").fetchone()[0]
        print(f'Imported {count} records → {DB_PATH}')

    sample = con.execute('SELECT id, date, day, time, moduleCode, "by" FROM attend LIMIT 3').fetchdf()
    print('\nSample rows:')
    print(sample.to_string(index=False))

    con.close()


if __name__ == '__main__':
    args = sys.argv[1:]
    in_path  = None
    preserve = '--preserve' in args

    if '--in' in args:
        idx     = args.index('--in')
        in_path = Path(args[idx + 1])

    import_from_export(in_path=in_path, preserve=preserve)
