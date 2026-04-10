"""
Migration: add 'hidden' column to attend table.
Run once: python migrate_hidden.py
Safe to re-run (skips if column already exists).
"""
from pathlib import Path
import duckdb

DB_PATH = str(Path(__file__).parent / 'data' / 'attend.duckdb')

con = duckdb.connect(DB_PATH)
try:
    con.execute('ALTER TABLE attend ADD COLUMN "hidden" BOOLEAN DEFAULT FALSE')
    print('Column "hidden" added successfully.')
except Exception as e:
    print(f'Skipped (likely already exists): {e}')
finally:
    con.close()
