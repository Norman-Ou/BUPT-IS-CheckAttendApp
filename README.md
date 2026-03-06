# 考勤小程序

微信小程序 + Python 后端，用于课堂考勤数据的录入与管理。

## 功能

- 按日期查看当日排课列表，自动定位到当前时段
- 填写课堂实到人数，自动计算出勤率
- 拍照或从相册上传课堂现场照片至阿里云 OSS
- 数据持久化至 DuckDB，支持多人协作填写

## 项目结构

```
.
├── app.js / app.json / app.wxss   # 小程序入口
├── pages/schedule/                # 考勤主页面
├── utils/
│   ├── util.js                    # 时间格式化工具
│   └── hmac_sha1.js               # OSS 签名工具
├── cloudfunctions/getOpenId/      # 云函数：获取用户 OpenID
├── server/
│   ├── main.py                    # FastAPI 后端服务
│   ├── import_xlsx.py             # xlsx 导入脚本
│   ├── export_xlsx.py             # 数据导出脚本
│   └── requirements.txt
├── tools/xlsx_to_csv.py           # xlsx 转 csv 工具
└── attendance.xlsx                # 排课数据源
```

## 快速开始

### 小程序

使用**微信开发者工具**打开项目根目录，AppID 为 `wx76e796f05cef368a`。

### 后端服务

```bash
cd server
pip install -r requirements.txt

# 首次导入排课数据
python import_xlsx.py

# 启动 API 服务（监听 0.0.0.0:8000）
python main.py
```

使用 [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) 将本地服务暴露为公网 URL，并将 URL 更新至 `pages/schedule/schedule.js` 顶部的 `API` 常量。

## 后端 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/dates` | 获取所有排课日期 |
| GET | `/records?date=4-Mar` | 获取指定日期的排课记录 |
| PATCH | `/records/{id}` | 更新实到人数、出勤率、照片状态 |
| GET | `/health` | 健康检查 |

## 更新排课数据

替换根目录下的 `attendance.xlsx`，然后重新导入：

```bash
# 完全重置（清空已填写数据）
python server/import_xlsx.py

# 仅更新静态字段，保留已填写数据
python server/import_xlsx.py --preserve
```
