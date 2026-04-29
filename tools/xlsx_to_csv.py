"""
Convert attendance.xlsx → 2526_Sem2_Attend.csv for WeChat Cloud DB import.
Usage: python tools/xlsx_to_csv.py
"""

import pandas as pd
import os

FIELD_MAP = {
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
    'Class':                       'class',
    'Total student num':           'totalStudentNum',
    'Student number in classroom': 'studentNumInClassroom',
    'Percent':                     'percent',
    'By':                          'by',
    'Remark':                      'remark',
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT  = os.environ.get('XLSX_TO_CSV_INPUT', os.path.join(ROOT, 'attendance.xlsx'))
OUTPUT = os.environ.get('XLSX_TO_CSV_OUTPUT', os.path.join(ROOT, '2526_Sem2_Attend.csv'))

df = pd.read_excel(INPUT)
df_out = df.rename(columns=FIELD_MAP)[list(FIELD_MAP.values())]
df_out['remark'] = df_out['remark'].fillna('')
df_out['by']     = df_out['by'].fillna('')
df_out.to_csv(OUTPUT, index=False, encoding='utf-8')

print(f'Done: {len(df_out)} records')
print(f'Output: {OUTPUT}')
print(f"Tutorial rows: {(df_out['remark'] == 'Tutorial').sum()}")
