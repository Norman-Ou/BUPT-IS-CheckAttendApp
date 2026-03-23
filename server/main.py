"""
Attendance API server

Usage:
    python main.py

Runs on http://0.0.0.0:8000
Use cloudflared to expose externally.
"""

import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import duckdb
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

CST = timezone(timedelta(hours=8))

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(Path(__file__).parent / 'data' / 'server.log'), encoding='utf-8'),
    ],
)
logger = logging.getLogger('attend')


def now() -> str:
    return datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S CST')

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


@app.middleware('http')
async def log_requests(request: Request, call_next):
    client = request.client.host if request.client else 'unknown'
    logger.info(f'[{now()}] {request.method} {request.url.path}{("?" + str(request.query_params)) if request.query_params else ""} from {client}')
    response = await call_next(request)
    return response


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
    df = con.execute(
        "SELECT * FROM attend WHERE date=? ORDER BY time, indexNo",
        [date],
    ).df()
    df = df.astype(object).where(df.notna(), other=None)
    return df.to_dict(orient='records')


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
    logger.info(f'[{now()}] [PATCH] id={record_id} updates={updates}')
    con.execute(sql, values)
    # verify
    row = con.execute('SELECT id, "studentNumInClassroom", "by" FROM attend WHERE id=?', [record_id]).fetchone()
    logger.info(f'[{now()}] [PATCH] after update: {row}')
    return {'ok': True}


# ── Healthcheck ────────────────────────────────────────────────────
@app.get('/health')
def health():
    count = con.execute('SELECT COUNT(*) FROM attend').fetchone()[0]
    return {'ok': True, 'records': count}


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=17800)
