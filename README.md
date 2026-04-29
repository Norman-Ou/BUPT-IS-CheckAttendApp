# BUPT IS CheckAttendApp

[English](./README_EN.md)

BUPT IS CheckAttendApp 是一个课堂考勤管理工具，由微信小程序前端和 FastAPI 后端组成。它可以帮助助教或课程管理员查看每日课表、记录到课人数、上传课堂照片、添加备注、隐藏或修正记录，并将考勤数据导出为表格用于后续统计。

公开仓库只包含源代码和配置模板。真实课表、导出结果、本地数据库、云服务密钥和部署相关配置不会提交到仓库，应通过 `.env` 和本地忽略文件提供。

## 功能

- 按日期查看课程记录，并自动定位到当前时间段附近。
- 填写实到人数并自动计算出勤率。
- 上传课堂照片到 Aliyun OSS。
- 为记录添加备注，隐藏不需要展示的记录。
- 修正教室、日期、时间等结构化字段。
- 查询同课程/同教室的历史照片记录作为参考。
- 从 Excel 导入课表到 DuckDB，并将考勤结果导出为 Excel。

## 项目结构

```text
.
├── app.js / app.json / app.wxss
├── pages/schedule/              # 小程序主页面
├── utils/                       # 工具函数和 OSS 签名
├── config.example.js            # 小程序配置模板
├── scripts/setup_config.py      # 根据 .env 生成本地配置
├── server/
│   ├── main.py                  # FastAPI 服务
│   ├── config.py                # 后端配置读取
│   ├── import_xlsx.py           # Excel 导入 DuckDB
│   ├── export_xlsx.py           # DuckDB 导出 Excel
│   └── requirements.txt
└── .env.example                 # 环境变量模板
```

## 使用方法

### 1. 准备配置

复制模板并填写本地配置：

```bash
cp .env.example .env
python scripts/setup_config.py
```

脚本会生成以下本地文件：

- `config.local.js`：小程序运行时配置。
- `server/.env`：后端脚本配置。
- `project.private.config.json`：微信开发者工具私有配置。

这些文件都已被 `.gitignore` 忽略。

### 2. 准备后端

```bash
cd server
pip install -r requirements.txt
python import_xlsx.py
python main.py
```

默认服务地址由 `.env` 中的 `SERVER_HOST` 和 `SERVER_PORT` 决定。

### 3. 打开小程序

用微信开发者工具打开仓库根目录。真实 AppID 填在 `.env` 的 `WECHAT_APPID` 中，然后运行 `python scripts/setup_config.py` 生成本地私有配置。

### 4. 导入和导出数据

导入课表：

```bash
cd server
python import_xlsx.py
```

保留已填写的考勤数据，只更新静态课表字段：

```bash
python import_xlsx.py --preserve
```

导出考勤结果：

```bash
python export_xlsx.py
python export_xlsx.py --filled-only
python export_xlsx.py --out /path/to/output.xlsx
```

## 配置项

`.env.example` 包含所有可配置项：

- `WECHAT_APPID`：微信小程序 AppID。
- `MINIPROGRAM_API_BASE_URL`：小程序请求的后端地址。
- `OSS_BUCKET`、`OSS_ENDPOINT`、`OSS_PREFIX`：Aliyun OSS 存储配置。
- `OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`：Aliyun OSS 访问密钥。
- `SERVER_HOST`、`SERVER_PORT`：后端监听地址。
- `SERVER_DB_PATH`：DuckDB 数据库路径。
- `SERVER_IMPORT_XLSX`：默认导入 Excel 路径。
- `SERVER_EXPORT_XLSX`：默认导出 Excel 路径。
- `SERVER_UPDATE_XLSX`：更新脚本默认读取的 Excel 路径。

## 数据与安全

以下内容不应提交到仓库：

- `.env`、`server/.env`、`config.local.js`
- `project.private.config.json`
- Excel/CSV 导入导出文件
- DuckDB 数据库和 `server/data/`
- notebook 和预处理产物
- 真实课表生成的 `schedule.json`、`data/schedule.js`

如果本地曾经跟踪过这些文件，可以用以下命令从 git 索引中移除，但保留本地文件：

```bash
git rm -r --cached project.private.config.json schedule.json data/schedule.js server/data server/attend_preprocess 2>/dev/null || true
git rm --cached '*.xlsx' '*.xls' '*.csv' '*.ipynb' 2>/dev/null || true
```
