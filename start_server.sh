#!/usr/bin/env bash
# Backend startup script (uv-managed environment).
# All config lives in the project-root .env (see .env.example).

set -euo pipefail

# ── Locate project root ──────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Load env from project-root .env (single source of truth) ─────────
if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "ERROR: $ROOT_DIR/.env not found. Run: cp .env.example .env" >&2
    exit 1
fi
set -a
# shellcheck disable=SC1091
. "$ROOT_DIR/.env"
set +a

# ── Ensure uv is available ───────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: 'uv' not found. Install from https://docs.astral.sh/uv/" >&2
    exit 1
fi

# ── Sync uv-managed environment ──────────────────────────────────────
# Dependencies live in server/pyproject.toml.
cd "$ROOT_DIR/server"
uv sync --package bupt-attend-server

# ── Ensure DuckDB exists; create from xlsx if missing ────────────────
# Resolve absolute DB path (config.py treats relative paths as project-root-relative).
DB_ABS="${SERVER_DB_PATH:-server/data/attend.duckdb}"
[[ "$DB_ABS" = /* ]] || DB_ABS="$ROOT_DIR/$DB_ABS"

if [ ! -f "$DB_ABS" ]; then
    # Fall back to UPDATE_XLSX when IMPORT_XLSX is unset/empty.
    if [ -z "${SERVER_IMPORT_XLSX:-}" ]; then
        echo "SERVER_IMPORT_XLSX not set — falling back to SERVER_UPDATE_XLSX (${SERVER_UPDATE_XLSX:-unset}) for initial import."
        export SERVER_IMPORT_XLSX="${SERVER_UPDATE_XLSX:-}"
    fi
    if [ -z "${SERVER_IMPORT_XLSX:-}" ]; then
        echo "ERROR: neither SERVER_IMPORT_XLSX nor SERVER_UPDATE_XLSX is set; cannot create DB." >&2
        exit 1
    fi
    echo "DuckDB not found at $DB_ABS — running import_xlsx.py ..."
    uv run python import_xlsx.py
fi

# ── Launch server ────────────────────────────────────────────────────
exec uv run python main.py
