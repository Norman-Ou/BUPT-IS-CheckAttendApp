# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (uv-managed; deps in pyproject.toml)
uv sync --package bupt-attend-server

# Generate local config from .env
cd ..
uv run python scripts/setup_config.py
cd server

# Import Excel data into DuckDB (drops and recreates the table)
uv run python import_xlsx.py

# Import while preserving existing mutable fill data
uv run python import_xlsx.py --preserve

# Start the API server (runs on http://127.0.0.1:17800)
uv run python main.py

# Export DuckDB back to Excel
uv run python export_xlsx.py
uv run python export_xlsx.py --out /path/to/output.xlsx
uv run python export_xlsx.py --filled-only   # only rows where data was filled in
```

## Architecture

This is a small FastAPI attendance tracking server backed by a DuckDB file configured by `SERVER_DB_PATH` in `.env`.

**Data flow:**
1. `SERVER_IMPORT_XLSX` → `import_xlsx.py` → `SERVER_DB_PATH` (one-time or periodic import)
2. `main.py` serves REST API against the DuckDB file
3. `export_xlsx.py` → dumps DuckDB back to Excel for reporting

**DuckDB schema (`attend` table):**
- Immutable fields: `id`, `indexNo`, `week`, `day`, `date`, `time`, `room`, `moduleCode`, `moduleName`, `lecturer`, `year`, `programme`, `class_`
- Fill data fields (updatable via API): `studentNumInClassroom`, `percent`, `by`, `photoUploaded`
- Record info fields (editable via "编辑记录" modal in mini-program): `remark`, `hidden`, `totalStudentNum`
- `hidden` column was added via `migrate_hidden.py` (not in original xlsx)
- `id` is a stable SHA-256 hash derived from session key fields (week, day, date, time, room, moduleCode, moduleName, lecturer)
- Dates are stored as strings in `"D-Mon"` format (e.g. `"4-Mar"`)

**API endpoints:**
- `GET /dates` — all distinct dates with day names
- `GET /records?date=4-Mar` — all records for a date, ordered by time then indexNo
- `PATCH /records/{id}` — update fill/status fields: `studentNumInClassroom`, `percent`, `by`, `photoUploaded`, `remark`, `hidden`, `totalStudentNum`
- `PATCH /records/{id}/attrs` — correct structural schedule attributes: `room`, `date`, `time` (纠正 xlsx 错误，无需重新导入)
- `GET /health` — record count check

**Key design notes:**
- Single DuckDB connection `con` shared across all requests (works because uvicorn runs single-process)
- The server exits at startup if the DB file doesn't exist — run `import_xlsx.py` first
- `import_xlsx.py --preserve` updates only fully-static fields (week, day, date, time, room, moduleCode, etc.) and leaves all mutable data intact: `studentNumInClassroom`, `percent`, `by`, `photoUploaded`, `remark`, `hidden`, `totalStudentNum`
- Without `--preserve` it drops and recreates the whole table (mutable fields reset)
