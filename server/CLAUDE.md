# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Import Excel data into DuckDB (drops and recreates the table)
python import_xlsx.py

# Import while preserving existing mutable fill data
python import_xlsx.py --preserve

# Start the API server (runs on http://127.0.0.1:17800)
python main.py

# Export DuckDB back to Excel
python export_xlsx.py
python export_xlsx.py --out /path/to/output.xlsx
python export_xlsx.py --filled-only   # only rows where data was filled in
```

## Architecture

This is a small FastAPI attendance tracking server backed by a single DuckDB file (`data/attend.duckdb`).

**Data flow:**
1. `attendance.xlsx` → `import_xlsx.py` → `data/attend.duckdb` (one-time or periodic import)
2. `main.py` serves REST API against the DuckDB file
3. `export_xlsx.py` → dumps DuckDB back to Excel for reporting

**DuckDB schema (`attend` table):**
- Immutable/read-only fields: `id`, `indexNo`, `week`, `day`, `date`, `time`, `room`, `moduleCode`, `moduleName`, `lecturer`, `year`, `programme`, `class_`, `totalStudentNum`, `remark`
- Mutable fields (updatable via API): `studentNumInClassroom`, `percent`, `by`, `photoUploaded`
- `id` is a stable string derived from `indexNo` (integer cast to string)
- Dates are stored as strings in `"D-Mon"` format (e.g. `"4-Mar"`)

**API endpoints:**
- `GET /dates` — all distinct dates with day names
- `GET /records?date=4-Mar` — all records for a date, ordered by time then indexNo
- `PATCH /records/{id}` — update mutable fields (`studentNumInClassroom`, `percent`, `by`, `photoUploaded`)
- `GET /health` — record count check

**Key design notes:**
- Single DuckDB connection `con` shared across all requests (works because uvicorn runs single-process)
- The server exits at startup if the DB file doesn't exist — run `import_xlsx.py` first
- `import_xlsx.py --preserve` updates only static fields and leaves mutable fill data intact; without `--preserve` it drops and recreates the whole table
