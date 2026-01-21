# 核心脚本索引

本文档列出项目中需要长期维护和使用的核心脚本。

## 📦 部署脚本 (核心)

| 脚本 | 位置 | 执行环境 | 用途 |
|------|------|----------|------|
| `update_bot.sh` | 项目根目录 | **服务器** | Bot 拉取并重启 (pull → restart bot) |
| `scripts/update_web.sh` | scripts/ | **服务器** | Web 拉取并更新 (pull → pip → restart web) |
| `scripts/update_all.sh` | scripts/ | **服务器** | 全部更新 (pull → pip → restart all) |

### 使用示例

```bash
# 本地推送并远程更新 Bot
git push origin v1 && ssh yyj "cd /opt/MusicalBot && sudo ./update_bot.sh"

# 服务器端更新 Web (SSH 后执行)
sudo ./scripts/update_web.sh

# 服务器端更新全部 (SSH 后执行)
sudo ./scripts/update_all.sh
```

---

## 🛠️ 开发脚本

| 脚本 | 位置 | 用途 |
|------|------|------|
| `dev.sh` | 项目根目录 | 本地开发启动 Web 服务 |

---

## 🔧 维护脚本 (按需使用)

| 脚本 | 用途 | 使用频率 |
|------|------|----------|
| `scripts/sanity_check.py` | 数据库完整性检查 | 定期 |
| `scripts/fix_user_schema.py` | 修复 User 表结构 | 一次性 |
| `scripts/migrate_legacy.py` | 旧数据迁移 | 一次性 |

---

## ⚠️ 废弃/重复脚本

以下脚本功能重复或已过时，建议删除：

| 脚本 | 原因 | 替代方案 |
|------|------|----------|
| `scripts/deploy_bot.sh` | 与 `update_bot.sh` 重复 | 使用 `update_bot.sh` |
| `scripts/deploy_web.sh` | 与 `scripts/update.sh` 部分重复 | 使用 `scripts/update.sh` |
| `scripts/safe_pull.sh` | `update.sh` 已包含 stash 逻辑 | 使用 `scripts/update.sh` |

---

## 📝 Agent 使用指南

当需要部署代码时，优先使用以下命令：

```bash
# Bot 部署 (从本地)
git push origin v1 && ssh yyj "cd /opt/MusicalBot && sudo ./update_bot.sh"

# Web 部署 (从本地)
git push origin v1 && ssh yyj "cd /opt/MusicalBot && sudo ./scripts/update_web.sh"

# 全部更新 (从本地)
git push origin v1 && ssh yyj "cd /opt/MusicalBot && sudo ./scripts/update_all.sh"
```

**注意**: 所有服务器端命令都需要 `sudo`，脚本已内置。
