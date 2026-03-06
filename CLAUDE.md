# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

This is a **WeChat Mini Program** (微信小程序). There is no npm build system or CLI — development and preview require **WeChat Developer Tools** (微信开发者工具), Tencent's proprietary IDE.

- Open the project directory in WeChat Developer Tools to build, preview, and upload
- AppID: `wx76e796f05cef368a` (in `project.config.json`)
- Framework: Glass Easel (`glass-easel` in `app.json`)

## Architecture

**File types:**
- `.js` — page/component logic
- `.wxml` — markup (like HTML, WeChat-proprietary)
- `.wxss` — styles (like CSS, supports `rpx` units)
- `.json` — page/component configuration

**App entry:** `app.js` initializes the app, handles WeChat login (`wx.login()`), and writes launch timestamps to local storage (`wx.setStorageSync`).

**Pages** (defined in `app.json`):
- `pages/index/` — user profile page; collects avatar + nickname via native WeChat components (WX ≥2.10.4) with a `getUserProfile()` fallback for older versions
- `pages/logs/` — reads launch timestamps from local storage and displays them formatted via `utils/util.js`

**Utilities:** `utils/util.js` exports `formatTime(date)` which formats a Date to `YYYY/MM/DD HH:MM:SS`.

**Data flow:** App launch → store timestamp → Index page collects user info → tap avatar navigates to Logs page → Logs page reads storage and renders history.
