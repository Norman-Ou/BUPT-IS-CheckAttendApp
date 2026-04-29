# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

This is a **WeChat Mini Program** (微信小程序) for attendance tracking. There is no npm build system or CLI — development and preview require **WeChat Developer Tools** (微信开发者工具), Tencent's proprietary IDE.

- Open the project directory in WeChat Developer Tools to build, preview, and upload
- AppID and service credentials are local only. Copy `.env.example` to `.env`, then run `python scripts/setup_config.py`.
- Framework: Glass Easel (`glass-easel` in `app.json`)

## Architecture

**File types:**
- `.js` — page/component logic
- `.wxml` — markup (like HTML, WeChat-proprietary)
- `.wxss` — styles (like CSS, supports `rpx` units)
- `.json` — page/component configuration

**App entry:** `app.js` reads `wechatId` from local storage into `globalData.wechatId` on launch.

**Pages** (defined in `app.json`):
- `pages/schedule/` — the only page; attendance tracking UI

**Utilities:**
- `utils/hmac_sha1.js` — pure-JS HMAC-SHA1 implementation used for Aliyun OSS request signing
- `utils/util.js` — `formatTime(date)` helper

**Data:**
- Schedule spreadsheets, generated schedule JSON/JS, exports, notebooks, DuckDB files, and local config are ignored and must not be committed.

**Cloud functions:**
- `cloudfunctions/getOpenId/` — WeChat cloud function to fetch OpenID (currently unused)

## Schedule Page (`pages/schedule/`)

The main attendance tracking page. Key behaviors:

- **Login:** user enters name (`Ruizhe` or `Shuyue`), stored in local storage and `globalData.wechatId`
- **API URL:** generated from `.env` into `config.local.js`; users can still override it via local storage.
- **Date selection:** fetches all dates from `GET /dates`, auto-selects today; user can pick via picker
- **Records list:** fetches `GET /records?date=D-Mon`; auto-scrolls to the currently-active time slot
- **Filling count:** tap a row to select, then tap "Fill" → modal → PATCH `/records/{id}` with `studentNumInClassroom`, `percent`, `by`
- **Photo upload:** user picks image → uploaded directly to Aliyun OSS → PATCH `/records/{id}` with `photoUploaded: true`
- **Photo naming convention:** `M.D_HH.MM_ROOM.jpg` (e.g. `4.7_09.50_LT1.jpg`) stored under `OSS_PREFIX`
- **Ref feature:** tap `totalStudentNum` to find historical records from same lecturer/room with photos; can copy photo and pre-fill count
- **Hidden rows:** double-tap a row to open remark/visibility modal; hidden rows can be toggled visible globally
- **Photo sync:** on load, HEAD-checks OSS for each record without a photo and auto-corrects the DB flag

## Server (`server/`)

See `server/CLAUDE.md` for full details. Summary:

- FastAPI + DuckDB attendance API running locally, exposed via Cloudflare tunnel
- `GET /dates`, `GET /records?date=`, `PATCH /records/{id}`
- Import from Excel: `python import_xlsx.py [--preserve]`
- Start server: `python main.py` (port 17800)
- Export to Excel: `python export_xlsx.py`
