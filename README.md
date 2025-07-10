# SimpCity API

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com/)

基于FastAPI的SimpCity论坛爬虫API服务，提供帖子爬取、同步和监控功能。

## 特性

- 🚀 **完整爬取**: 支持完整爬取帖子的所有页面和数据
- 🔄 **增量同步**: 智能对比现有数据，仅同步变化部分
- ⏰ **定时监控**: 支持间隔和cron两种调度方式的自动监控
- 📊 **状态管理**: 实时查看监控器状态和执行结果
- 🔧 **灵活配置**: 多种cookies加载方式和配置选项
- 📝 **完整日志**: 统一的日志输出和请求跟踪

## 快速开始

### 1. 安装依赖

```bash
# 克隆项目
git clone <your-repo-url>
cd dionysus

# 安装依赖
uv sync
```

### 2. 配置

```bash
# 复制配置文件模板
cp config.yaml.example config.yaml

# 编辑配置文件，添加cookies和数据库配置
vim config.yaml
```

### 3. 启动服务

```bash
# 开发模式（推荐）
uv run start_api.py --reload

# 生产模式
uv run start_api.py --host 0.0.0.0 --port 8000

# 或直接使用uvicorn
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问服务

- **API文档**: http://localhost:8000/docs
- **ReDoc文档**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/

## API 端点

### 爬取帖子 - `POST /crawler`

完整爬取指定帖子的所有页面和帖子数据。

```bash
curl -X POST "http://localhost:8000/crawler" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_url": "https://simpcity.su/threads/example.12345/",
    "thread_title": "示例帖子",
    "enable_reactions": false,
    "save_to_db": true
  }'
```

### 同步帖子 - `POST /sync`

对比现有数据和最新数据，进行增量同步。

```bash
curl -X POST "http://localhost:8000/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_url": "https://simpcity.su/threads/example.12345/",
    "thread_title": "示例帖子",
    "enable_reactions": false,
    "save_to_db": true
  }'
```

### 启动监控 - `POST /watch`

创建定时任务监控指定帖子的更新。

**间隔调度**:
```bash
curl -X POST "http://localhost:8000/watch" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_url": "https://simpcity.su/threads/example.12345/",
    "thread_title": "示例帖子",
    "schedule_type": "interval",
    "interval_minutes": 30,
    "enable_reactions": false,
    "save_to_db": true
  }'
```

**Cron调度**:
```bash
curl -X POST "http://localhost:8000/watch" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_url": "https://simpcity.su/threads/example.12345/",
    "thread_title": "示例帖子",
    "schedule_type": "cron",
    "cron_expression": "0 8 * * *",
    "enable_reactions": false,
    "save_to_db": true
  }'
```

### 监控器管理

- `GET /watchers` - 获取所有监控器
- `GET /watchers/{watcher_id}` - 获取监控器详情
- `DELETE /watchers/{watcher_id}` - 停止监控器
- `POST /watchers/{watcher_id}/force-sync` - 手动触发同步

## 配置说明

### Cookies配置

支持两种方式配置cookies：

**方式一：config.yaml**
```yaml
cookies:
  - domain: ".simpcity.su"
    name: "session_id"
    value: "你的session_id值"
    path: "/"
    secure: true
    httpOnly: true
```

**方式二：browser_cookies.json**
将浏览器导出的cookies JSON文件保存为 `browser_cookies.json`。

### 数据库配置

```yaml
database:
  host: "localhost"
  port: 5432
  database: "dionysus"
  user: "postgresql"
  password: "password"
  min_connections: 1
  max_connections: 20
```

## Python客户端示例

```python
import requests

base_url = "http://localhost:8000"

# 启动监控
response = requests.post(f"{base_url}/watch", json={
    "thread_url": "https://simpcity.su/threads/example.12345/",
    "thread_title": "示例帖子",
    "schedule_type": "interval",
    "interval_minutes": 30,
    "enable_reactions": False,
    "save_to_db": True
})

if response.status_code == 200:
    result = response.json()
    watcher_id = result["data"]["watcher_id"]
    print(f"监控器已启动: {watcher_id}")
    
    # 查看监控器状态
    status_response = requests.get(f"{base_url}/watchers/{watcher_id}")
    print("监控器状态:", status_response.json())
    
    # 手动触发同步
    sync_response = requests.post(f"{base_url}/watchers/{watcher_id}/force-sync")
    print("手动同步结果:", sync_response.json())
else:
    print("启动监控失败:", response.text)
```

## 日志记录

API服务会输出详细的日志信息到控制台，包含：
- 请求跟踪ID
- 操作状态和结果
- 错误信息和异常

日志格式：
```
2025-01-10 14:30:00,123 - app.main - INFO - [request_id] 操作描述
```

## 响应格式

所有API端点都使用统一的响应格式：

```json
{
  "success": true,
  "message": "操作描述",
  "data": { /* 具体数据 */ },
  "request_id": "uuid-here",
  "timestamp": "2025-01-10T14:30:00Z"
}
```

## 错误处理

- `200` - 成功
- `400` - 请求参数错误
- `404` - 资源未找到
- `500` - 服务器内部错误

## 开发

### 项目结构

```
dionysus/
├── app/
│   └── main.py           # FastAPI应用
├── crawler/
│   └── simpcity/
│       └── simpcity.py   # 爬虫核心逻辑
├── cookies/
│   └── cookies.py        # Cookie管理
├── db/
│   └── postgre.py        # 数据库管理
├── config/
│   └── config.py         # 配置加载
├── config.yaml.example   # 配置文件模板
├── start_api.py          # API启动脚本
└── README.md             # 项目说明
```

### 开发模式

```bash
# 启动开发服务器（自动重载）
uv run start_api.py --reload --log-level debug

# 或使用fastapi dev命令
uv run fastapi dev app/main.py
```

## 许可证

本项目基于 [Apache License 2.0](LICENSE) 开源协议发布。

## 贡献

欢迎提交Issue和Pull Request！
