# BUPT IS CheckAttendApp

[中文](./README.md)

BUPT IS CheckAttendApp is a classroom attendance management tool built with a WeChat Mini Program frontend and a FastAPI backend. It helps teaching assistants or course administrators browse daily schedules, record attendance counts, upload classroom photos, add remarks, hide or correct records, and export attendance data for reporting.

The public repository contains only source code and configuration templates. Real schedules, exported reports, local databases, cloud credentials, and deployment-specific settings are intentionally excluded and should be provided through `.env` and local ignored files.

## Features

- Browse class records by date and auto-scroll near the current time slot.
- Fill attendance counts and calculate attendance percentages.
- Upload classroom photos to Aliyun OSS.
- Add remarks and hide records that should not be displayed.
- Correct structural fields such as room, date, and time.
- Look up historical photo records from the same course or room as references.
- Import schedules from Excel into DuckDB and export attendance results back to Excel.

## Project Structure

```text
.
├── app.js / app.json / app.wxss
├── pages/schedule/              # Mini Program main page
├── utils/                       # Helpers and OSS signing
├── config.example.js            # Mini Program config template
├── scripts/setup_config.py      # Generates local config from .env
├── server/
│   ├── main.py                  # FastAPI server
│   ├── config.py                # Backend config loader
│   ├── import_xlsx.py           # Import Excel into DuckDB
│   ├── export_xlsx.py           # Export DuckDB to Excel
│   └── requirements.txt
└── .env.example                 # Environment variable template
```

## Usage

### 1. Prepare Config

Copy the template and fill in local values:

```bash
cp .env.example .env
python scripts/setup_config.py
```

The script generates:

- `config.local.js`: runtime config for the Mini Program.
- `server/.env`: backend script config.
- `project.private.config.json`: private config for WeChat Developer Tools.

These files are ignored by git.

### 2. Start the Backend

```bash
cd server
pip install -r requirements.txt
python import_xlsx.py
python main.py
```

The default host and port are configured by `SERVER_HOST` and `SERVER_PORT` in `.env`.

### 3. Open the Mini Program

Open the repository root in WeChat Developer Tools. Put the real AppID in `WECHAT_APPID` inside `.env`, then run `python scripts/setup_config.py` to generate the local private config.

### 4. Import and Export Data

Import a schedule:

```bash
cd server
python import_xlsx.py
```

Preserve existing attendance data while updating static schedule fields:

```bash
python import_xlsx.py --preserve
```

Export attendance results:

```bash
python export_xlsx.py
python export_xlsx.py --filled-only
python export_xlsx.py --out /path/to/output.xlsx
```

## Configuration

`.env.example` documents all supported settings:

- `WECHAT_APPID`: WeChat Mini Program AppID.
- `MINIPROGRAM_API_BASE_URL`: backend API URL used by the Mini Program.
- `OSS_BUCKET`, `OSS_ENDPOINT`, `OSS_PREFIX`: Aliyun OSS storage settings.
- `OSS_ACCESS_KEY_ID`, `OSS_ACCESS_KEY_SECRET`: Aliyun OSS credentials.
- `SERVER_HOST`, `SERVER_PORT`: backend listen address.
- `SERVER_DB_PATH`: DuckDB database path.
- `SERVER_IMPORT_XLSX`: default Excel path for import.
- `SERVER_EXPORT_XLSX`: default Excel path for export.
- `SERVER_UPDATE_XLSX`: default Excel path for update scripts.

## Data and Security

Do not commit:

- `.env`, `server/.env`, `config.local.js`
- `project.private.config.json`
- Excel/CSV import and export files
- DuckDB databases and `server/data/`
- notebooks and preprocessing artifacts
- generated schedule files such as `schedule.json` and `data/schedule.js`

If any of these files were previously tracked locally, remove them from the git index while keeping local copies:

```bash
git rm -r --cached project.private.config.json schedule.json data/schedule.js server/data server/attend_preprocess 2>/dev/null || true
git rm --cached '*.xlsx' '*.xls' '*.csv' '*.ipynb' 2>/dev/null || true
```
