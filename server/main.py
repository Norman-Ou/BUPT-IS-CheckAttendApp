"""
Attendance API server

Usage:
    python main.py

Runs on http://0.0.0.0:8000
Use cloudflared to expose externally.
"""

import sys
from pathlib import Path
from typing import Optional

import duckdb
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_PATH = str(Path(__file__).parent / 'data' / 'attend.duckdb')

# ── Check DB exists ────────────────────────────────────────────────
if not Path(DB_PATH).exists():
    print(f'ERROR: {DB_PATH} not found. Run import_xlsx.py first.')
    sys.exit(1)

# ── Single connection (single-process server) ─────────────────────
con = duckdb.connect(DB_PATH)

app = FastAPI(title='Attendance API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)


# ── GET /dates ─────────────────────────────────────────────────────
@app.get('/dates')
def get_dates():
    """Return all distinct dates (for the date picker)."""
    rows = con.execute(
        "SELECT DISTINCT date, day FROM attend ORDER BY date"
    ).fetchall()
    return [{'date': r[0], 'day': r[1]} for r in rows]


# ── GET /records?date=4-Mar ────────────────────────────────────────
@app.get('/records')
def get_records(date: str):
    """Return all records for a given date, ordered by time then indexNo."""
    rows = con.execute(
        "SELECT * FROM attend WHERE date=? ORDER BY time, indexNo",
        [date],
    ).df().to_dict(orient='records')
    return rows


# ── PATCH /records/{id} ────────────────────────────────────────────
class UpdateBody(BaseModel):
    studentNumInClassroom: Optional[int]  = None
    percent:               Optional[float] = None
    by:                    Optional[str]   = None
    photoUploaded:         Optional[bool]  = None


@app.patch('/records/{record_id}')
def update_record(record_id: str, body: UpdateBody):
    """Update mutable fields on a single record."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {'ok': True}

    sets   = ', '.join(f'"{k}"=?' for k in updates)
    values = list(updates.values()) + [record_id]
    sql = f'UPDATE attend SET {sets} WHERE id=?'
    print(f'[PATCH] sql={sql} values={values}', flush=True)
    con.execute(sql, values)
    # verify
    row = con.execute('SELECT id, "studentNumInClassroom", "by" FROM attend WHERE id=?', [record_id]).fetchone()
    print(f'[PATCH] after update: {row}', flush=True)
    return {'ok': True}


# ── Healthcheck ────────────────────────────────────────────────────
@app.get('/health')
def health():
    count = con.execute('SELECT COUNT(*) FROM attend').fetchone()[0]
    return {'ok': True, 'records': count}


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=17800)
