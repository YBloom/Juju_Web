# MusicalBot 备份系统操作指南

本文档详细介绍如何使用和配置 MusicalBot 的双层备份系统。

## 一、本地备份脚本

### 1.1 触发方式

#### 方式一：手动触发

```bash
# 在项目根目录执行
python3 scripts/backup.py
```

**适用场景**：

- 重大更新前手动备份
- 测试备份系统
- 需要立即备份时

#### 方式二：自动定时备份（推荐）

使用 Linux/macOS 的 `cron` 定时任务实现自动化备份。

**配置步骤**：

1. 编辑 crontab：

```bash
crontab -e
```

1. 添加以下配置（每天凌晨 2 点自动备份）：

```cron
0 2 * * * cd /path/to/MusicalBot && /usr/bin/python3 scripts/backup.py >> logs/cron_backup.log 2>&1
```

**配置说明**：

- `0 2 * * *`：每天凌晨 2:00 执行
- `cd /path/to/MusicalBot`：切换到项目目录（请替换为实际路径）
- `/usr/bin/python3`：使用系统 Python3（确保版本 >= 3.12）
- `>> logs/cron_backup.log 2>&1`：将输出追加到日志文件

**其他常用 cron 时间配置**：

```cron
# 每 6 小时执行一次
0 */6 * * * cd /path/to/MusicalBot && /usr/bin/python3 scripts/backup.py

# 每周日凌晨 3 点执行
0 3 * * 0 cd /path/to/MusicalBot && /usr/bin/python3 scripts/backup.py
```

1. 验证 cron 任务：

```bash
# 查看已配置的定时任务
crontab -l
```

### 1.2 备份内容

脚本会自动备份以下内容并压缩为 `zip` 文件：

- ✅ **数据库**：`data/musicalbot.db`（使用 SQLite 热备份 API，支持 WAL 模式）
- ✅ **密钥文件**：`keys/` 目录下的所有文件（AWS 密钥、SMTP 凭证等）
- ✅ **环境配置**：`.env` 文件

### 1.3 备份存储

- **位置**：`backups/backup_YYYYMMDD_HHMMSS.zip`
- **保留策略**：自动删除 7 天前的旧备份（可在 `scripts/backup.py` 中修改 `RETENTION_DAYS`）
- **日志**：`logs/backups.log`

### 1.4 恢复数据

```bash
# 1. 停止服务
# 2. 解压备份文件
unzip backups/backup_20260120_020000.zip -d /tmp/restore

# 3. 恢复数据库
cp /tmp/restore/musicalbot.db data/musicalbot.db

# 4. 恢复密钥和配置（可选）
cp /tmp/restore/.env .env
cp -r /tmp/restore/keys/* keys/

# 5. 重启服务
```

---

## 二、AWS Lightsail 快照（系统级容灾）

### 2.1 为什么需要快照？

本地备份只能应对**数据误操作**，无法防范：

- 💥 服务器磁盘故障
- 💥 实例整体损坏
- 💥 操作系统崩溃

AWS Lightsail 快照可以将**整个服务器**（包括系统、配置、数据）一键恢复。

### 2.2 启用自动快照

1. **登录 AWS Lightsail 控制台**  
   <https://lightsail.aws.amazon.com/>

2. **选择您的实例**  
   进入实例详情页

3. **启用自动快照**
   - 点击「Snapshots」标签
   - 点击「Enable automatic snapshots」
   - 选择快照时间（建议选择凌晨 3:00-5:00，避开业务高峰）
   - AWS 会自动保留最近 7 天的快照

4. **验证快照**
   - 在「Snapshots」列表中确认有自动快照生成
   - 快照命名格式：`auto-YYYY-MM-DD`

### 2.3 手动创建快照

重大更新前建议手动创建快照：

1. 进入实例详情页
2. 点击「Create snapshot」
3. 输入描述性名称（如 `before-major-update-2026-01-20`）
4. 点击「Create」

### 2.4 从快照恢复

**完整恢复流程**：

1. 在 Lightsail 控制台找到目标快照
2. 点击「...」→「Create new instance from snapshot」
3. 选择实例配置（与原实例相同）
4. 等待新实例启动（约 3-5 分钟）
5. 更新 DNS 记录指向新实例的 IP
6. 验证服务正常后删除旧实例

---

## 三、异地备份（可选）

如果未来数据量增长，可以将本地备份推送到 AWS S3 实现真正的"异地异介质"备份。

### 3.1 方案：使用 Rclone 同步到 S3

1. **安装 Rclone**：

```bash
curl https://rclone.org/install.sh | sudo bash
```

1. **配置 S3**：

```bash
rclone config
# 选择 Amazon S3，填入 Access Key 和 Secret
```

1. **添加到 cron 任务**（在本地备份后执行）：

```cron
0 3 * * * rclone copy /path/to/MusicalBot/backups s3:your-bucket-name/musicalbot-backups --max-age 7d
```

**成本估算**（AWS S3 标准存储）：

- 假设每个备份 20MB，每天 1 次
- 7 天滚动：20MB × 7 ≈ 140MB
- 费用：约 $0.003/月（几乎免费）

---

## 四、最佳实践

### 4.1 黄金 3-2-1 备份原则

✅ **3 个副本**：生产数据 + 本地备份 + Lightsail 快照  
✅ **2 种介质**：本机磁盘 + AWS 云端  
✅ **1 个异地**：Lightsail 位于 AWS 数据中心

### 4.2 定期验证

每月至少验证一次备份可用性：

```bash
# 解压最新备份
unzip backups/backup_*.zip -d /tmp/test_restore

# 测试数据库完整性
sqlite3 /tmp/test_restore/musicalbot.db "PRAGMA integrity_check;"
# 预期输出：ok
```

### 4.3 监控备份状态

定期检查日志：

```bash
# 查看最近 10 次备份记录
tail -n 50 logs/backups.log

# 检查是否有失败记录
grep "失败" logs/backups.log
```

---

## 五、常见问题

**Q：备份会影响服务运行吗？**  
A：不会。脚本使用 SQLite 的 `backup()` API，支持 WAL 模式下的在线备份，对服务无影响。

**Q：备份文件会占用多少空间？**  
A：根据当前数据量约 5-20MB/个，7 天滚动约占用 100-150MB。

**Q：如何修改保留天数？**  
A：编辑 `scripts/backup.py`，修改 `RETENTION_DAYS = 7` 为所需天数。

**Q：可以备份到其他位置吗？**  
A：可以。修改 `scripts/backup.py` 中的 `BACKUP_DIR` 变量即可。
