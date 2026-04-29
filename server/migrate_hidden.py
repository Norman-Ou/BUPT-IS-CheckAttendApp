"""
Migration: add 'hidden' column to attend table.
Run once: python migrate_hidden.py
Safe to re-run (skips if column already exists).
"""
import duckdb
from config import SERVER_DB_PATH

DB_PATH = str(SERVER_DB_PATH)

con = duckdb.connect(DB_PATH)
try:
    con.execute('ALTER TABLE attend ADD COLUMN "hidden" BOOLEAN DEFAULT FALSE')
    print('Column "hidden" added successfully.')
except Exception as e:
    print(f'Skipped (likely already exists): {e}')
finally:
    con.close()
