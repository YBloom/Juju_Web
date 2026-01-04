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

> [!IMPORTANT]
> **核心原则**: 本地修改 → Git Push → 服务器 Pull。避免直接在服务器修改Git追踪的文件!

#### 🚀 最简洁的更新流程(推荐)

**在本地完成修改后:**

```bash
# 1. 本地提交并推送
git add .
git commit -m "更新描述"
git push origin v1

# 2. 服务器拉取(一行命令)
ssh yyj "cd /opt/MusicalBot && sudo git stash && sudo git pull origin v1 && sudo supervisorctl restart musicalbot_web"
```

#### 📜 使用自动化脚本

如果服务器有未提交的修改(如Umami配置),使用safe_pull.sh:

```bash
ssh yyj "sudo bash /opt/MusicalBot/scripts/safe_pull.sh"
```

**脚本功能**:
- 自动 stash 本地修改
- 拉取最新代码
- 恢复服务器特定配置(如Umami Website ID)
- 重启 WebApp 服务

#### 🔧 手动更新(仅在需要时)

```bash
cd /opt/MusicalBot

# 保存本地修改
sudo git stash

# 拉取代码
sudo git pull origin v1

# 恢复本地修改(如有)
sudo git stash pop

# 安装新依赖(如requirements.txt有变化)
sudo .venv/bin/pip install -r requirements.txt

# 重启服务
sudo supervisorctl restart musicalbot_web
```

#### ⚠️ 避免Git冲突

1. **不要直接编辑服务器上的Git文件**
2. **动态配置放`.env`**(不在Git中)
3. **出现冲突时**: `sudo git stash && sudo git pull && sudo git stash pop`

详见: [Git工作流文档](./git_workflow.md)

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

## 📊 访问统计系统 (Umami Analytics)

### 系统概述

Umami 是一个开源、轻量级、隐私友好的网站统计工具,用于分析网站访问数据。

**组件**:
- **Umami 应用**: Node.js 应用,运行在 Docker 容器中
- **PostgreSQL 数据库**: 存储统计数据
- **追踪脚本**: 前端页面加载的轻量脚本(<2KB)

**资源占用**:
- 内存: ~500MB
- 磁盘: ~5GB (随数据增长)

---

### 访问统计仪表板

#### 访问地址

**服务器上**:
```
https://yyj.yaobii.com/umami
```

#### 默认账号

- **用户名**: `admin`
- **密码**: `umami`

> [!IMPORTANT]
> **必须立即修改密码**: 首次登录后请立即修改为强密码!

---

### 首次配置步骤

#### 1. 登录后台

访问 `https://yyj.yaobii.com/umami`,使用默认账号登录。

#### 2. 修改密码

1. 点击右上角头像图标
2. 选择 **Settings** → **Profile**
3. 在 "Change password" 区域输入新密码
4. 建议使用 12 位以上强密码(包含大小写字母、数字、特殊字符)

#### 3. 创建网站

1. 在左侧菜单选择 **Settings** → **Websites**
2. 点击 **Add website** 按钮
3. 填写信息:
   - **Domain**: `yyj.yaobii.com`
   - **Name**: `MusicalBot`
4. 点击 **Save**

#### 4. 获取追踪代码

1. 在网站列表中点击刚创建的网站
2. 点击 **Tracking code** 标签
3. 复制显示的 **Website ID** (类似 `abc123def-456g-789h-ijkl-mnopqrst`)
4. 编辑 `/opt/MusicalBot/web/static/index.html`
5. 将 `YOUR_WEBSITE_ID` 替换为实际的 Website ID:
   ```html
   <script defer src="/umami/script.js" data-website-id="abc123def-456g-789h-ijkl-mnopqrst"></script>
   ```
6. 保存文件并重启 WebApp:
   ```bash
   sudo supervisorctl restart musicalbot_web
   ```

---

### 查看统计数据

#### 仪表板功能

登录后可以查看:

1. **总览 (Overview)**:
   - 总访问量 (Page Views)
   - 独立访客 (Unique Visitors)
   - 跳出率 (Bounce Rate)
   - 平均访问时长

2. **实时数据 (Realtime)**:
   - 当前在线人数
   - 实时访问流

3. **页面排行**:
   - 最受欢迎的页面
   - 各 API 端点访问量

4. **访客来源**:
   - 地理位置分布(国家、城市)
   - 流量来源(直接访问、搜索引擎等)

5. **设备统计**:
   - 桌面 vs 移动端
   - 浏览器分布
   - 操作系统分布

#### 时间范围筛选

仪表板右上角可以选择时间范围:
- 最近 24 小时
- 最近 7 天
- 最近 30 天
- 自定义范围

---

### 服务管理

#### 查看 Umami 容器状态

```bash
cd /opt/MusicalBot
sudo docker-compose -f docker-compose.umami.yml ps
```

#### 查看日志

```bash
# 查看所有日志
sudo docker-compose -f docker-compose.umami.yml logs

# 实时查看日志
sudo docker-compose -f docker-compose.umami.yml logs -f

# 仅查看 Umami 应用日志
sudo docker-compose -f docker-compose.umami.yml logs -f umami

# 仅查看数据库日志
sudo docker-compose -f docker-compose.umami.yml logs -f db
```

#### 重启 Umami

```bash
cd /opt/MusicalBot
sudo docker-compose -f docker-compose.umami.yml restart
```

#### 停止 Umami

```bash
cd /opt/MusicalBot
sudo docker-compose -f docker-compose.umami.yml down
```

#### 启动 Umami

```bash
cd /opt/MusicalBot
sudo docker-compose -f docker-compose.umami.yml up -d
```

---

### 数据备份

#### 备份 PostgreSQL 数据库

```bash
# 进入数据库容器
sudo docker exec -it musicalbot-umami-db-1 /bin/sh

# 备份数据库
pg_dump -U umami umami > /tmp/umami_backup.sql

# 退出容器
exit

# 复制备份到宿主机
sudo docker cp musicalbot-umami-db-1:/tmp/umami_backup.sql ~/umami_backup_$(date +%Y%m%d).sql
```

#### 恢复数据库

```bash
# 复制备份到容器
sudo docker cp ~/umami_backup.sql musicalbot-umami-db-1:/tmp/

# 进入容器
sudo docker exec -it musicalbot-umami-db-1 /bin/sh

# 恢复数据库
psql -U umami umami < /tmp/umami_backup.sql

# 退出
exit
```

---

### 故障排查

#### 问题 1: 无法访问 Umami 仪表板

**症状**: 访问 `https://yyj.yaobii.com/umami` 显示 502 错误

**排查步骤**:
```bash
# 1. 检查容器状态
sudo docker-compose -f docker-compose.umami.yml ps

# 2. 查看日志
sudo docker-compose -f docker-compose.umami.yml logs --tail=50

# 3. 检查端口占用
sudo netstat -tulnp | grep 3000
```

**解决方案**:
```bash
# 重启容器
sudo docker-compose -f docker-compose.umami.yml restart
```

---

#### 问题 2: 追踪脚本加载失败

**症状**: 浏览器控制台显示 `/umami/script.js` 404 错误

**原因**: Nginx 配置未正确代理

**解决方案**:
```bash
# 1. 检查 Nginx 配置
sudo nginx -t

# 2. 确认配置包含 Umami 代理规则
sudo cat /etc/nginx/sites-available/musicalbot | grep umami

# 3. 重启 Nginx
sudo systemctl restart nginx
```

---

#### 问题 3: 统计数据不显示

**症状**: 已访问网站但仪表板没有数据

**可能原因**:
1. Website ID 未正确替换
2. 浏览器广告拦截插件拦截了追踪脚本

**排查步骤**:
```bash
# 1. 检查 index.html 中的 Website ID
sudo grep "data-website-id" /opt/MusicalBot/web/static/index.html

# 2. 在浏览器中打开开发者工具(F12)
# 3. 切换到 Network 标签
# 4. 刷新页面
# 5. 查找 script.js 请求是否成功
```

**解决方案**:
- 确认 Website ID 正确
- 暂时禁用广告拦截插件测试
- 检查浏览器控制台是否有错误

---

### 安全建议

1. **强密码**: 使用 12 位以上复杂密码
2. **定期备份**: 建议每周备份一次数据库
3. **仅 HTTPS 访问**: 确保通过 HTTPS 访问仪表板
4. **(可选) IP 白名单**: 在 Nginx 中限制只有特定 IP 能访问 `/umami/` 管理后台

**Nginx IP 白名单示例**:
```nginx
location /umami/ {
    # 仅允许您的 IP 访问
    allow 1.2.3.4;     # 替换为您的家庭 IP
    allow 5.6.7.8;     # 替换为您的办公室 IP
    deny all;
    
    proxy_pass http://localhost:3000/;
    # ... 其他配置
}
```

---

**文档版本**: v1.0  
**最后更新**: 2026-01-04  
**维护者**: YBloom
