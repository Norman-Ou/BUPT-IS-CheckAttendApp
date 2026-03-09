"""
Convert attendance.xlsx → server/data/attend.duckdb

Usage:
    python import_xlsx.py

Re-running will DROP and recreate the table (mutable fields reset to defaults).
If you want to preserve existing fill data, use --preserve flag.
"""

import sys
import duckdb
import pandas as pd
from pathlib import Path

XLSX_PATH = Path(__file__).parent / 'attendance.xlsx'
DB_PATH   = Path(__file__).parent / 'data' / 'attend.duckdb'


def import_xlsx(preserve: bool = False):
    if not XLSX_PATH.exists():
        print(f'ERROR: {XLSX_PATH} not found')
        sys.exit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f'Reading {XLSX_PATH} ...')
    df = pd.read_excel(XLSX_PATH)

    # ── Column rename ──────────────────────────────────────────────
    df = df.rename(columns={
        'Index No.':                  'indexNo',
        'Week':                       'week',
        'Day':                        'day',
        'Date':                       'date',
        'Time':                       'time',
        'Room':                       'room',
        'Module Code':                'moduleCode',
        'Module Name':                'moduleName',
        'Lecturer':                   'lecturer',
        'Year':                       'year',
        'Programme':                  'programme',
        'Class':                      'class_',
        'Total student num':          'totalStudentNum',
        'Student number in classroom':'studentNumInClassroom',
        'Percent':                    'percent',
        'By':                         'by',
        'Remark':                     'remark',
    })

    # ── Date: "4-Mar" format ───────────────────────────────────────
    df['date'] = pd.to_datetime(df['date'], errors='coerce').apply(
        lambda d: f"{d.day}-{d.strftime('%b')}" if pd.notna(d) else ''
    )

    # ── Day: keep as-is (e.g. "Monday") ───────────────────────────
    df['day'] = df['day'].fillna('').astype(str)

    # ── Stable string ID from indexNo ─────────────────────────────
    df['id'] = df['indexNo'].astype(int).astype(str)

    # ── Mutable fields: defaults (don't overwrite if preserving) ──
    df['studentNumInClassroom'] = df.get('studentNumInClassroom', pd.Series(dtype=float)).fillna(0).astype(int)
    df['percent']               = df.get('percent', pd.Series(dtype=float)).fillna(0.0).astype(float)
    df['by']                    = df.get('by', pd.Series(dtype=str)).fillna('').astype(str)
    df['photoUploaded']         = False

    # ── Remark: NaN → empty string ────────────────────────────────
    df['remark'] = df['remark'].fillna('').astype(str)

    # ── Final column order ─────────────────────────────────────────
    cols = [
        'id', 'indexNo', 'week', 'day', 'date', 'time', 'room',
        'moduleCode', 'moduleName', 'lecturer', 'year', 'programme',
        'class_', 'totalStudentNum', 'studentNumInClassroom',
        'percent', 'by', 'photoUploaded', 'remark',
    ]
    df = df[cols]

    # ── Write to DuckDB ────────────────────────────────────────────
    con = duckdb.connect(str(DB_PATH))

    if preserve and con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='attend'").fetchone()[0]:
        # Keep existing mutable data, only update static fields
        print('Preserving existing fill data ...')
        con.execute("CREATE TEMP TABLE new_data AS SELECT * FROM df")
        con.execute("""
            UPDATE attend a
            SET
                week       = n.week,
                day        = n.day,
                date       = n.date,
                time       = n.time,
                room       = n.room,
                moduleCode = n.moduleCode,
                moduleName = n.moduleName,
                lecturer   = n.lecturer,
                year       = n.year,
                programme  = n.programme,
                class_     = n.class_,
                totalStudentNum = n.totalStudentNum,
                remark     = n.remark
            FROM new_data n
            WHERE a.id = n.id
        """)
        print('Static fields updated; mutable fields preserved.')
    else:
        con.execute("DROP TABLE IF EXISTS attend")
        con.execute("CREATE TABLE attend AS SELECT * FROM df")
        count = con.execute("SELECT COUNT(*) FROM attend").fetchone()[0]
        print(f'Imported {count} records → {DB_PATH}')

    # Sanity check
    sample = con.execute("SELECT id, date, day, time, moduleCode, remark FROM attend LIMIT 3").fetchdf()
    print('\nSample rows:')
    print(sample.to_string(index=False))

    con.close()


if __name__ == '__main__':
    preserve = '--preserve' in sys.argv
    import_xlsx(preserve=preserve)
