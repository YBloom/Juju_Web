# MusicalBot Lightsail 服务器运维手册

> **服务器**: AWS Lightsail  
> **域名**: `yyj.yaobii.com`  
> **最后更新**: 2026-01-04

---

## 📋 服务器基础信息

### 实例配置
- **云服务**: AWS Lightsail
- **套餐**: $20/月 (4GB RAM, 2 vCPU, 80GB SSD)
- **操作系统**: Ubuntu 24.04 LTS
- **Python 版本**: 3.12
- **网络**: Dual-stack (IPv4 + IPv6)
- **流量额度**: 3TB/月

### 网络信息
- **公网 IPv4**: `54.169.3.40`
- **域名**: `yyj.yaobii.com`
- **SSL 证书**: Let's Encrypt (自动续期)
- **开放端口**: 22 (SSH), 80 (HTTP), 443 (HTTPS)

### 关键路径
```
/opt/MusicalBot/          # 项目代码根目录
├── .env                  # 环境配置
├── data/                 # 数据目录
│   ├── musicalbot.db     # 呼啦圈数据库
│   └── saoju_service_cache.json  # Saoju 缓存
├── web/                  # 前端代码
├── services/             # 后端服务
├── scripts/              # 运维脚本
├── logs/                 # 应用日志
└── .venv/               # Python 虚拟环境

/var/log/musicalbot/      # Supervisor 日志目录
├── web_out.log           # WebApp 标准输出
└── web_err.log           # WebApp 错误日志

/etc/nginx/sites-available/musicalbot  # Nginx 配置
/etc/supervisor/conf.d/musicalbot.conf # Supervisor 配置
```

---

## 🏗️ 系统架构

### 技术栈
```
┌─────────────────────────────────────────┐
│          用户浏览器                      │
└──────────────┬──────────────────────────┘
               │ HTTPS (443)
               ↓
┌─────────────────────────────────────────┐
│   Nginx (反向代理 + SSL 终止)           │
└──────────────┬──────────────────────────┘
               │ HTTP (127.0.0.1:8002)
               ↓
┌─────────────────────────────────────────┐
│   FastAPI WebApp (uvicorn)              │
│   - 后台调度器 (5分钟同步)               │
│   - API 端点                             │
│   - 静态文件服务                          │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴───────┐
        ↓              ↓
┌──────────────┐  ┌─────────────────┐
│ SQLite DB    │  │ Saoju API       │
│ (呼啦圈数据)  │  │ (演员/剧目数据) │
└──────────────┘  └─────────────────┘
```

### 服务组件
- **Nginx**: Web 服务器，处理 HTTPS 和反向代理
- **Supervisor**: 进程管理，守护 FastAPI 应用
- **FastAPI**: Python Web 框架，提供 REST API
- **SQLite**: 本地数据库，存储呼啦圈数据
- **后台调度器**: 每 5 分钟自动同步呼啦圈数据

### 数据流
```
呼啦圈 API  ─【5分钟】→  后台调度器  →  SQLite
                            ↓
                        WebApp API  →  前端页面
                            ↑
Saoju API   ─【按需缓存】─→  Cache
```

---

## 🔧 常用运维命令

### SSH 连接
```bash
# 使用密钥登录
ssh -i ~/.ssh/LightsailDefaultKey-ap-southeast-1.pem ubuntu@54.169.3.40

# 或使用别名 (需配置 ~/.ssh/config)
ssh yyj
```

**配置 SSH 别名** (`~/.ssh/config`):
```
Host yyj
    HostName 54.169.3.40
    User ubuntu
    IdentityFile ~/.ssh/LightsailDefaultKey-ap-southeast-1.pem
```

---

### 服务管理

#### Supervisor 基础命令
```bash
# 查看所有服务状态
sudo supervisorctl status

# 重启 WebApp
sudo supervisorctl restart musicalbot_web

# 停止 WebApp
sudo supervisorctl stop musicalbot_web

# 启动 WebApp
sudo supervisorctl start musicalbot_web

# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update
```

#### Nginx 管理
```bash
# 检查配置语法
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx

# 查看 Nginx 状态
sudo systemctl status nginx

# 重新加载配置 (无需停机)
sudo systemctl reload nginx
```

---

### 日志查看

#### 实时日志
```bash
# WebApp 运行日志 (实时)
sudo supervisorctl tail -f musicalbot_web stdout

# WebApp 错误日志 (实时)
sudo supervisorctl tail -f musicalbot_web stderr

# Nginx 访问日志
sudo tail -f /var/log/nginx/access.log

# Nginx 错误日志
sudo tail -f /var/log/nginx/error.log

# 系统日志
sudo journalctl -f -u nginx
sudo journalctl -f -u supervisor
```

#### 历史日志
```bash
# 查看最近 100 行
sudo supervisorctl tail -100 musicalbot_web stdout

# 查看完整日志文件
sudo less /var/log/musicalbot/web_out.log
sudo less /var/log/musicalbot/web_err.log

# 搜索错误关键词
sudo grep -i "error" /var/log/musicalbot/web_err.log | tail -20
```

---

### 代码更新

#### 方式一：使用自动化脚本 (推荐)
```bash
cd /opt/MusicalBot
sudo ./scripts/update.sh
```

**脚本功能**:
- 自动 `git pull` 拉取最新代码
- 检测 `requirements.txt` 变化并更新依赖
- 重启 WebApp 服务
- 显示服务状态

#### 方式二：手动更新
```bash
# 1. 拉取代码
cd /opt/MusicalBot
sudo git pull

# 2. 更新依赖 (如有变化)
sudo .venv/bin/pip install -r requirements.txt

# 3. 重启服务
sudo supervisorctl restart musicalbot_web

# 4. 查看状态
sudo supervisorctl status
```

#### 回滚到之前版本
```bash
# 查看提交历史
cd /opt/MusicalBot
sudo git log --oneline -10

# 回滚到指定 commit
sudo git reset --hard <commit-hash>

# 重启服务
sudo supervisorctl restart musicalbot_web
```

---

### 数据库管理

#### 查看数据库状态
```bash
# 查看数据库大小
ls -lh /opt/MusicalBot/data/musicalbot.db

# 进入 SQLite 命令行
cd /opt/MusicalBot
sqlite3 data/musicalbot.db

# 常用 SQL 查询
.tables                          # 列出所有表
SELECT COUNT(*) FROM hulaquan_events;  # 事件总数
SELECT COUNT(*) FROM hulaquan_tickets; # 票据总数
.quit                            # 退出
```

#### 手动触发数据同步
```bash
# 立即同步呼啦圈数据
cd /opt/MusicalBot
sudo .venv/bin/python -c "import asyncio; from services.hulaquan.service import HulaquanService; asyncio.run(HulaquanService().sync_all_data())"
```

#### 从本地上传数据库
```bash
# 在本地开发机执行
rsync -avz -e "ssh -i ~/.ssh/LightsailDefaultKey-ap-southeast-1.pem" \
  data/musicalbot.db data/saoju_service_cache.json \
  ubuntu@54.169.3.40:/opt/MusicalBot/data/

# 上传后重启服务
ssh yyj "sudo supervisorctl restart musicalbot_web"
```

---

### 环境变量管理

#### 查看当前配置
```bash
sudo cat /opt/MusicalBot/.env
```

#### 修改配置
```bash
# 编辑 .env
sudo nano /opt/MusicalBot/.env

# 修改后保存 (Ctrl+O, Enter, Ctrl+X)

# 重启服务使配置生效
sudo supervisorctl restart musicalbot_web
```

**关键配置项**:
```bash
HLQ_ENABLE_CRAWLER=True   # 是否启用爬虫
LEGACY_COMPAT=1           # 旧版兼容模式
MAINTENANCE_MODE=0        # 维护模式 (1=开启)
```

---

### 系统监控

#### 系统资源
```bash
# CPU 和内存使用
htop  # 需安装: sudo apt install htop

# 磁盘使用情况
df -h

# 项目目录空间占用
du -sh /opt/MusicalBot/*

# 内存详情
free -h

# Swap 使用情况
swapon --show
```

#### 网络监控
```bash
# 实时网络流量
sudo iftop  # 需安装: sudo apt install iftop

# 端口占用
sudo netstat -tulnp | grep :80
sudo netstat -tulnp | grep :443
sudo netstat -tulnp | grep :8002

# 当前连接数
sudo ss -s
```

#### 服务健康检查
```bash
# 检查 WebApp 是否响应
curl -I http://localhost:8002/api/events/list

# 检查 Nginx 是否正常
curl -I https://yyj.yaobii.com

# 检查 SSL 证书有效期
sudo certbot certificates
```

---

## 🐛 故障排查

### 问题 1: 网站无法访问

**症状**: 浏览器打开 `https://yyj.yaobii.com` 无法连接

**排查步骤**:
```bash
# 1. 检查 Nginx 状态
sudo systemctl status nginx

# 2. 检查 WebApp 状态
sudo supervisorctl status musicalbot_web

# 3. 查看 Nginx 错误日志
sudo tail -50 /var/log/nginx/error.log

# 4. 测试本地端口
curl http://localhost:8002/api/events/list
```

**常见解决方案**:
```bash
# 重启 Nginx
sudo systemctl restart nginx

# 重启 WebApp
sudo supervisorctl restart musicalbot_web

# 检查防火墙
sudo ufw status
```

---

### 问题 2: 服务启动失败

**症状**: `supervisorctl status` 显示 `FATAL` 或 `EXITED`

**排查步骤**:
```bash
# 查看详细错误
sudo supervisorctl tail -100 musicalbot_web stderr

# 检查 Python 环境
cd /opt/MusicalBot
sudo .venv/bin/python --version

# 测试手动启动
cd /opt/MusicalBot
sudo -u ubuntu .venv/bin/uvicorn web_app:app --host 127.0.0.1 --port 8002
```

**常见原因**:
1. **依赖缺失**: 运行 `sudo .venv/bin/pip install -r requirements.txt`
2. **环境变量错误**: 检查 `.env` 文件格式
3. **端口占用**: `sudo netstat -tulnp | grep 8002`

---

### 问题 3: 数据未更新

**症状**: 网站显示的数据是旧的

**排查步骤**:
```bash
# 1. 检查爬虫是否启用
sudo cat /opt/MusicalBot/.env | grep CRAWLER

# 2. 查看日志确认同步时间
sudo supervisorctl tail -50 musicalbot_web stdout | grep "Scheduler"

# 3. 检查数据库最后修改时间
ls -lh /opt/MusicalBot/data/musicalbot.db
```

**解决方案**:
```bash
# 手动触发同步
cd /opt/MusicalBot
sudo .venv/bin/python -c "import asyncio; from services.hulaquan.service import HulaquanService; asyncio.run(HulaquanService().sync_all_data())"

# 或重启服务
sudo supervisorctl restart musicalbot_web
```

---

### 问题 4: SSL 证书过期

**症状**: 浏览器显示证书不受信任

**排查步骤**:
```bash
# 查看证书状态
sudo certbot certificates

# 手动续期
sudo certbot renew

# 测试自动续期
sudo certbot renew --dry-run
```

**解决方案**:
```bash
# 强制重新获取证书
sudo certbot --nginx -d yyj.yaobii.com --force-renewal

# 重启 Nginx
sudo systemctl restart nginx
```

---

### 问题 5: 内存不足

**症状**: 服务频繁崩溃，日志显示 `MemoryError`

**排查步骤**:
```bash
# 查看内存使用
free -h
top -o %MEM

# 检查 Swap
swapon --show
```

**解决方案**:
```bash
# 手动清理缓存
sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches

# 重启服务释放内存
sudo supervisorctl restart musicalbot_web
```

---

## 💾 备份与恢复

### 数据库备份

#### 手动备份
```bash
# 在服务器上备份
sudo cp /opt/MusicalBot/data/musicalbot.db \
       /opt/MusicalBot/data/musicalbot.db.backup.$(date +%Y%m%d)

# 下载到本地
scp -i ~/.ssh/LightsailDefaultKey-ap-southeast-1.pem \
  ubuntu@54.169.3.40:/opt/MusicalBot/data/musicalbot.db \
  ~/backup/musicalbot-$(date +%Y%m%d).db
```

#### 自动备份脚本
创建 `/opt/MusicalBot/scripts/backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/opt/MusicalBot/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 备份数据库
cp /opt/MusicalBot/data/musicalbot.db $BACKUP_DIR/musicalbot_$DATE.db

# 保留最近 7 天的备份
find $BACKUP_DIR -name "musicalbot_*.db" -mtime +7 -delete

echo "Backup completed: musicalbot_$DATE.db"
```

**设置定时备份** (每天凌晨 3 点):
```bash
sudo crontab -e
# 添加以下行
0 3 * * * /opt/MusicalBot/scripts/backup.sh >> /var/log/musicalbot/backup.log 2>&1
```

---

### 配置备份

```bash
# 备份关键配置文件
sudo tar -czf ~/config-backup-$(date +%Y%m%d).tar.gz \
  /opt/MusicalBot/.env \
  /etc/nginx/sites-available/musicalbot \
  /etc/supervisor/conf.d/musicalbot.conf
```

---

### 完整恢复流程

如果需要从零恢复整个服务：

```bash
# 1. 重新部署基础环境
sudo ./scripts/deploy_lightsail.sh

# 2. 恢复数据库
scp -i ~/.ssh/LightsailDefaultKey-ap-southeast-1.pem \
  ~/backup/musicalbot-latest.db \
  ubuntu@54.169.3.40:/opt/MusicalBot/data/musicalbot.db

# 3. 重启服务
sudo supervisorctl restart musicalbot_web

# 4. 验证
curl https://yyj.yaobii.com/api/events/list
```

---

## 📞 快速参考

### 紧急联系信息
- **DNS 提供商**: (根据实际情况填写)
- **AWS 账号**: (根据实际情况填写)
- **域名注册商**: yaobii.com

### 关键服务检查清单
- [ ] WebApp 服务运行正常
- [ ] Nginx 响应正常
- [ ] SSL 证书有效
- [ ] 数据库可读写
- [ ] 爬虫正常同步 (每 5 分钟)
- [ ] 磁盘空间充足 (> 10GB)
- [ ] 内存使用正常 (< 3.5GB)

### 最常用命令速查
```bash
# SSH 登录
ssh yyj

# 查看服务状态
sudo supervisorctl status

# 查看实时日志
sudo supervisorctl tail -f musicalbot_web stdout

# 重启服务
sudo supervisorctl restart musicalbot_web

# 更新代码
cd /opt/MusicalBot && sudo ./scripts/update.sh

# 手动同步数据
cd /opt/MusicalBot && sudo .venv/bin/python -c "import asyncio; from services.hulaquan.service import HulaquanService; asyncio.run(HulaquanService().sync_all_data())"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-01-04  
**维护者**: YBloom
