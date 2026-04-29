import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


_load_env_file(ROOT_DIR / '.env')
_load_env_file(BASE_DIR / '.env')

SERVER_HOST = os.environ.get('SERVER_HOST', '127.0.0.1')
SERVER_PORT = int(os.environ.get('SERVER_PORT', '17800'))
SERVER_DB_PATH = project_path(os.environ.get('SERVER_DB_PATH', 'server/data/attend.duckdb'))
SERVER_IMPORT_XLSX_PATH = project_path(os.environ.get('SERVER_IMPORT_XLSX', 'server/attendance.xlsx'))
SERVER_EXPORT_XLSX_PATH = project_path(os.environ.get('SERVER_EXPORT_XLSX', 'server/export.xlsx'))
SERVER_UPDATE_XLSX_PATH = project_path(os.environ.get('SERVER_UPDATE_XLSX', 'server/export.xlsx'))
API_BASE_URL = os.environ.get('MINIPROGRAM_API_BASE_URL', f'http://{SERVER_HOST}:{SERVER_PORT}')
OSS_BUCKET = os.environ.get('OSS_BUCKET', '')
OSS_ENDPOINT = os.environ.get('OSS_ENDPOINT', '')
OSS_PREFIX = os.environ.get('OSS_PREFIX', '')
