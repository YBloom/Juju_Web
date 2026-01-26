# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

**MusicalBot (剧剧)** 是一个 QQ 机器人和 Web 服务，用于监控呼啦圈平台上的音乐剧学生票余票情况。系统采用**生产者-消费者架构**，Web 服务负责爬取票务数据，Bot 服务从队列中消费通知。

## 架构设计

### 核心设计模式：生产者-消费者

```
┌─────────────────────┐         ┌──────────────────┐
│  Web 服务           │         │  Bot 服务        │
│  (生产者)           │         │  (消费者)        │
│                     │         │                  │
│  - 爬取票务数据     │────────▶│  - 读取队列      │
│  - 写入 SendQueue   │  SQLite │  - 发送到 QQ     │
│  - 处理订阅匹配     │         │  - 只读数据库    │
└─────────────────────┘         └──────────────────┘
```

**核心铁律** (来自 ARCHITECTURE.md)：

1. **[PRODUCER_ONLY] 唯一生产权**：只有 `web_app.py` 或其子进程可以调用 `sync_all_data()` 爬取数据。Bot (`main_bot_v2.py`) **严格只读**，绝不能写入 `TicketInfo` 相关表。

2. **[SCHEMA_ENFORCED] 显式契约**：所有服务间通信（特别是写入 `SendQueue`）必须使用 `services.hulaquan.models` 中的 Pydantic 模型。严禁手动构建字典。

3. **[ASYNC_MANDATORY] 异步优先**：Bot 主循环中严禁使用同步阻塞调用如 `time.sleep` 或 `requests.get`。使用 `asyncio.sleep` 和 `httpx.AsyncClient`。

### 服务边界

- **Web 服务** (`web_app.py`)：FastAPI 应用，端口 8000，当 `HLQ_ENABLE_CRAWLER=True` 时运行爬虫调度器
- **Bot 服务** (`main_bot_v2.py`)：基于 ncatbot 的 QQ 机器人，每 30 秒消费一次 `SendQueue`
- **数据库**：SQLite WAL 模式，位于 `data/musicalbot.db`

## 开发命令

### 本地开发

```bash
# 启动 Web 服务（带自动重载）
./dev.sh

# 启动 Bot 服务（另开终端）
python3.12 main_bot_v2.py

# 手动激活虚拟环境
source .venv/bin/activate
```

### 数据库操作

```bash
# 在服务器上运行数据库迁移/脚本
cd /opt/MusicalBot
PYTHONPATH=/opt/MusicalBot .venv/bin/python scripts/your_script.py

# 完整数据重置（谨慎使用）
python scripts/prod_full_reset.py --dry-run  # 预览变更
python scripts/prod_full_reset.py            # 执行重置
```

### 部署

```bash
# 仅部署 Bot
git push origin main && ssh yyj "cd /opt/MusicalBot && sudo ./update_bot.sh"

# 仅部署 Web
git push origin main && ssh yyj "cd /opt/MusicalBot && sudo ./scripts/update_web.sh"

# 部署全部
git push origin main && ssh yyj "cd /opt/MusicalBot && sudo ./scripts/update_all.sh"
```

**注意**：所有服务器命令都需要 `sudo`。生产服务器使用 `supervisor` 进行进程管理。

## 关键目录结构

```
services/
├── bot/              # QQ 机器人处理器和命令
│   ├── handlers.py   # 主消息分发器
│   └── commands/     # 命令实现（注册表模式）
├── hulaquan/         # 呼啦圈票务爬虫和模型
│   ├── service.py    # 主爬虫逻辑 (sync_all_data)
│   ├── models.py     # Pydantic 模型 (TicketInfo, TicketUpdate)
│   ├── formatter.py  # Bot 消息格式化
│   └── tables.py     # SQLModel 数据库表
├── notification/     # 通知引擎
│   ├── engine.py     # 将更新匹配到订阅
│   └── config.py     # 通知等级和变更类型
├── db/
│   ├── models/       # SQLModel 表定义
│   ├── connection.py # 数据库引擎和 session_scope()
│   └── init.py       # Schema 初始化
└── saoju/            # Saoju.net 集成（音乐剧元数据）

web/
├── routers/          # FastAPI 路由处理器
├── static/           # 前端 HTML/JS/CSS
└── dependencies.py   # 共享的 FastAPI 依赖

scripts/              # 维护和部署脚本
```

## 共享能力（请勿重复造轮子）

| 领域 | 路径 | 核心类/函数 |
|------|------|------------|
| **数据模型** | `services.hulaquan.models` | `TicketUpdate`, `TicketInfo` (真理之源) |
| **数据库** | `services.db.models.base` | `TimeStamped` (UTC 时间戳), `session_scope()` |
| **格式化** | `services.hulaquan.formatter` | `HulaquanFormatter` (消息模板) |
| **通知** | `services.notification.engine` | `NotificationEngine` (订阅匹配) |
| **Bot 命令** | `services.bot.commands.registry` | `@register_command` 装饰器 |

## 数据库 Schema

所有时间戳通过 `services.db.models.base.utcnow()` 使用 **UTC**。关键表：

- `User`：6 位标准化用户 ID（如 "000001"）
- `UserAuthMethod`：将 QQ ID 映射到标准化用户 ID
- `Subscription`：用户订阅及其目标和选项
- `SubscriptionTarget`：订阅内容（剧目、演员、活动、关键词）
- `SendQueue`：Bot 消费的通知队列
- `HulaquanEvent`, `HulaquanTicket`：爬取的票务数据
- `SaojuShow`：来自 Saoju.net 的音乐剧元数据

## Bot 命令系统

命令使用**注册表模式**：

```python
from services.bot.commands.base import CommandHandler, CommandContext
from services.bot.commands.registry import register_command

@register_command
class MyCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/mycommand", "别名"]

    @property
    def help_text(self) -> str:
        return "命令帮助文本"

    async def handle(self, ctx: CommandContext) -> str:
        # 访问: ctx.user_id, ctx.args, ctx.service, ctx.session_maker
        return "响应消息"
```

命令由 `services.bot.handlers.BotHandler` 自动注册和分发。

## Web API 结构

`web/routers/` 中的 FastAPI 路由：

- `auth.py`：用户认证（魔法链接、QQ OAuth）
- `subscription.py`：订阅 CRUD
- `events.py`：票务搜索和活动详情
- `admin.py`：管理面板和系统管理
- `marketplace.py`：票务交易市场

所有需要认证的路由使用 `web.dependencies` 中的 `get_current_user` 依赖。

## 配置

环境变量（`.env`）：

```bash
# 爬虫控制
HLQ_ENABLE_CRAWLER=True  # 在 Web 服务中启用爬虫

# Bot 配置
BOT_UIN=3044829389       # QQ 机器人账号

# 数据库（可选覆盖）
HLQ_DB_PATH=data/musicalbot.db

# 旧版兼容
LEGACY_COMPAT=1
MAINTENANCE_MODE=0
```

## 测试

**注意**：本项目目前自动化测试较少。添加测试时：

- Python 测试使用 `pytest`
- 将测试放在 `tests/` 目录
- 测试中的数据库操作使用 `session_scope()`
- Mock 外部 API 调用（呼啦圈、Saoju）

## 常用模式

### 数据库操作

```python
from services.db.connection import session_scope
from services.db.models import User

# 始终使用 session_scope 上下文管理器
with session_scope() as session:
    user = session.get(User, user_id)
    if user:
        user.nickname = "新昵称"
        session.add(user)
    # 退出时自动提交
```

### 异步服务使用

```python
from services.hulaquan.service import HulaquanService

async with HulaquanService() as service:
    events = await service.search_events_smart("时光代理人")
    updates = await service.sync_all_data()  # 仅在 Web 服务中！
```

### 通知处理

```python
from services.notification import NotificationEngine

engine = NotificationEngine(bot_api=bot.api)
updates = await service.sync_all_data()  # 仅 Web 服务
enqueued = await engine.process_updates(updates)
```

## 重要约束

1. **绝不在 Bot 服务中编写爬虫逻辑** - 这违反了生产者-消费者边界
2. **始终使用 Pydantic 模型**进行服务间数据传输
3. **使用 UTC 时间戳**，通过 `utcnow()` 辅助函数
4. **优先使用 async/await** 而非同步阻塞调用
5. **所有数据库操作使用 `session_scope()`**
6. **使用 `@register_command` 装饰器注册 Bot 命令**

## 服务器信息

- **生产环境**：AWS Lightsail `54.169.3.40`（别名：`yyj`）
- **位置**：`/opt/MusicalBot`
- **进程管理器**：Supervisor
- **Web 端口**：8000（由 Nginx 代理）
- **Bot**：通过 NapCat WebSocket 运行于 `ws://127.0.0.1:3001`

查看日志：
```bash
ssh yyj "sudo supervisorctl tail -f musicalbot_web stdout"
ssh yyj "sudo supervisorctl tail -f musical_qq_bot stdout"
```

## 故障排查

### 服务器上的导入错误

始终使用虚拟环境的 Python：
```bash
PYTHONPATH=/opt/MusicalBot .venv/bin/python script.py
```

### 数据库锁定

SQLite 使用 WAL 模式，超时时间 60 秒。如果锁定：
- 检查长时间运行的事务
- 确保正确使用 `session_scope()`
- 验证异步代码中没有手动 `time.sleep()`

### 爬虫未运行

检查 `.env` 中的 `HLQ_ENABLE_CRAWLER`，并验证 Web 服务日志显示 "Crawler ENABLED"。

## 代码风格

- 函数签名使用**类型提示**
- 优先使用 **Pydantic 模型**而非原始字典
- I/O 操作使用 **async/await**
- 遵循 **PEP 8** 命名约定
- 为复杂函数添加**文档字符串**
- 保持函数**专注且简洁**
