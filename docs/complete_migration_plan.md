# 呼啦圈机器人 (MusicalBot) 完整迁移方案 (End-to-End Migration Plan) V2

> **目标**: 将原有的基于 Aliyun + Ncatbot 的旧版机器人完全迁移至 AWS (Lightsail) + NapCat + Web 的新架构。
> **核心思想**: Bot 回归"通知与触达" (Ticket Updates Core User Value)，Web 承担"复杂交互与管理" (Account & Subscription Management)。

## 1. 架构演进 (Architecture Evolution)

| 维度 | 旧版 (Legacy) | 新版 (Target) |
| :--- | :--- | :--- |
| **基础设施** | Aliyun ECS (2C/2G) + Ncatbot (Windows/Wine) | AWS Lightsail (Linux) |
| **Bot 框架** | Ncatbot (Legacy Plugins) | NapCat (基于 NTQQ) + Python Service |
| **Web 端** | 无 (或仅静态页) | 完整 Python Flask Web App + **独立账号系统** |
| **数据存储** | 本地 JSON (UsersManager.py) | AWS MySQL / PostgreSQL (统一存储) |
| **交互模式** | 纯指令 (参数复杂, Alias 猜测) | 指令引导 -> Web 可视化操作 (无 Alias) |
| **登录体系** | QQ 绑定 (弱关联) | **Magic Link (QQ -> Web 强绑定)** + Web 独立账号 |

---

## 2. 关键决策与优先级 (Key Decisions & Priorities)

### 2.1 产品优先级排序
1.  **Bot-Web 互通 (Phase 1)**: Magic Link 登录，确保 QQ 用户能一键进入 Web。
2.  **Web 账号系统 (Phase 1.5)**: 建立独立的用户/账号表，允许绑定 QQ，为订阅功能打底。
3.  **订阅管理迁移 (Phase 2)**: 在 Web 端实现可视化的订阅管理（剧目/演员），替代 Bot 复杂的指令。
4.  **Bot 核心功能复刻 (Phase 3)**: 确保 "票务动态通知" 这个 Killer Feature 在新 Bot 上稳定运行。
5.  **废弃别名系统**: 新版基于结构化数据，不再需要 `alias` 猜测，完全移除。

### 2.2 用户体验目标
*   **Web**: 保持现有的简洁风格 (Minimalist)。订阅入口可以是新页面 `(User Profile -> Subscriptions)` 或在原有列表页增加 `🔔` 按钮。
*   **Bot**: 只做它最擅长的事——**通知**。查询指令仅保留最基础的，复杂的全部给链接去 Web。

---

## 3. 功能迁移矩阵 (Feature Migration Matrix)

| 功能模块 | 旧版指令 | 新版方案 | 状态 |
| :--- | :--- | :--- | :--- |
| **身份认证** | 无 (按 QQ 号识别) | **Magic Link** (`/web` 生成免密链接) -> 自动注册/登录 Web 账号 | ✅ 代码已就绪 |
| **账号系统** | `UsersManager.json` | **Web SQL DB** (User 表 + OAuth Binding) | 🗓 需设计表结构 |
| **订阅管理** | `/关注` (参数极其复杂) | **Web 可视化面板** (勾选剧目/演员)。Bot 仅推送通知。 | 🗓 需开发 Web UI |
| **基础查询** | `/hlq`, `/date` | **Bot 轻量查询** (仅返回 Top 3 + Web 链接) | ✅ 代码已就绪 |
| **同场演员** | `/同场演员` | **Web 专属页面** (Bot 仅返回跳转链接) | ✅ 代码已就绪 |
| **Repo/剧评** | `/新建repo` | **Web Repo 中心** (上传图片、打分、长评) | ⏳ 规划中 (低优) |
| **别名管理** | `/alias` | **❌ 彻底移除** (Web 搜索支持自动匹配，无需人工 Alias) | 🗑 已废弃 |
| **通知推送** | 私聊推送 | **AWS Bot 推送** (对接 Hulaquan Service) | 🛠 调试中 |

---

## 4. 数据迁移策略 (Data Migration Strategy)

基于 `plugins_legacy/AdminPlugin/UsersManager.py` 的数据结构分析。

### 4.1 用户数据 (User Data)
*   **源结构**: `users[qq_id] = { "subscribe": { ... }, "attention_to_hulaquan": int }`
*   **目标表**: `users` (id, qq_id, nickname), `user_settings` (notification_level)
*   **动作**: 编写脚本读取 json，写入 SQL。

### 4.2 订阅数据 (Subscription Mapping)
旧版订阅结构极其复杂，包含 `subscribe_tickets` (场次), `subscribe_events` (剧目), `subscribe_actors` (演员)。

| 旧版字段 | 含义 | 新版映射 (ItemSubscription) | 备注 |
| :--- | :--- | :--- | :--- |
| `subscribe_events` | 关注剧目 | `type='show', item_id=event_id` | 直接迁移 |
| `subscribe_tickets` | 关注具体场次 | `type='session', item_id=ticket_id` | 直接迁移 |
| `subscribe_actors` | 关注演员 | `type='actor', item_id=actor_name` | **注意** Old: `include_events` (白名单) -> New: 需支持过滤字段 |
| `related_to_actors`| 因演员关注的场次 | (不需要迁移) | 這是衍生数据，新版通过逻辑动态判断，或仅迁移为普通场次关注 |

**注意**: 演员订阅中的 `include_events/exclude_events` 需要在新版数据库模型中支持（例如 `filter_rules` JSON 字段）。

---

## 5. 运维与部署 (DevOps)

**需求**: 区分 WebApp 和 Bot 的部署更新脚本。

### 5.1 目录结构规划
```
/opt/MusicalBot/
  ├── web_app.py        # Web 服务入口
  ├── main_bot_v2.py    # Bot 服务入口
  ├── services/         # 共享服务层
  ├── scripts/
  │   ├── deploy_web.sh # 更新并重启 Web
  │   ├── deploy_bot.sh # 更新并重启 Bot
  │   └── common.sh     # 共享更新逻辑 (git pull 等)
```

### 5.2 脚本设计

**`scripts/deploy_web.sh`**:
```bash
#!/bin/bash
# 1. Git Pull
# 2. Update Pip Dependencies (web only)
# 3. Restart Supervisor Web Process
sudo supervisorctl restart musicalbot_web
```

**`scripts/deploy_bot.sh`**:
```bash
#!/bin/bash
# 1. Git Pull
# 2. Update Pip Dependencies (bot only)
# 3. Restart Supervisor Bot Process
# 4. Check Bot Status (via Health Check)
sudo supervisorctl restart musicalbot_bot
```

---

## 6. 下一步行动计划 (Action Plan)

1.  **基础设施 (Ops)**:
    *   创建 `scripts/deploy_web.sh` 和 `scripts/deploy_bot.sh`。
    *   配置 Supervisor 分别管理 `musicalbot_web` 和 `musicalbot_bot` 进程。

2.  **账号系统 (Web)**:
    *   设计 `User` 和 `Subscription` 的 SQLAlchemy 模型。
    *   完善 `auth.py`，实现 Magic Link -> 自动注册 -> Session 保持。

3.  **Bot 修复**:
    *   确保 AWS `ncatbot` 稳定运行 (解决交互式登录问题)。

4.  **订阅迁移 (Data)**:
    *   编写 `migrate_legacy_data.py` 脚本，从 Json 导入 SQL。
