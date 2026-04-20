# Attendance Mini Program

A WeChat Mini Program + Python backend for classroom attendance tracking and management.

## Features

- View daily class schedule by date, auto-scrolled to the current time slot
- Fill in headcount and auto-calculate attendance percentage
- Upload classroom photos to Aliyun OSS (camera or photo library)
- Edit record attributes (room, date, time) to correct scheduling errors
- Double-tap a row to add remarks or hide/show records
- Ref feature: look up historical records from the same lecturer/room with photos
- Data persisted in DuckDB; supports concurrent filling by multiple users

## Project Structure

```
.
├── app.js / app.json / app.wxss   # Mini program entry
├── pages/schedule/                # Main attendance page
├── utils/
│   ├── util.js                    # Date formatting helper
│   └── hmac_sha1.js               # OSS request signing (HMAC-SHA1)
├── data/schedule.js               # Static schedule data
├── server/
│   ├── main.py                    # FastAPI backend (port 17800)
│   ├── import_xlsx.py             # Import schedule from Excel → DuckDB
│   ├── export_xlsx.py             # Export DuckDB → Excel
│   └── requirements.txt
├── tools/xlsx_to_csv.py           # Excel to CSV conversion tool
└── attendance.xlsx                # Source schedule spreadsheet
```

## Getting Started

### Mini Program

Open the project root in **WeChat Developer Tools**. AppID: `wx76e796f05cef368a`.

### Backend

```bash
cd server
pip install -r requirements.txt

# Import schedule data for the first time
python import_xlsx.py

# Start the API server (listens on 127.0.0.1:17800)
python main.py
```

Expose the local server via [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) and set the resulting URL as the API base in the mini program's settings (or via the in-app URL config).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dates` | All distinct dates with day names |
| GET | `/records?date=4-Mar` | All records for a given date |
| PATCH | `/records/{id}` | Update headcount, percentage, photo status, remark, visibility |
| PATCH | `/records/{id}/attrs` | Correct structural attributes (room, date, time) |
| GET | `/health` | Record count health check |

## Updating Schedule Data

Replace `attendance.xlsx` in the project root, then re-import:

```bash
# Full reset — drops and recreates the table (clears all filled data)
python server/import_xlsx.py

# Preserve filled data — updates only static schedule fields
python server/import_xlsx.py --preserve
```

## Exporting Data

```bash
python server/export_xlsx.py                        # all records
python server/export_xlsx.py --out /path/out.xlsx   # custom output path
python server/export_xlsx.py --filled-only          # only filled rows
```
