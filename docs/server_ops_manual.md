# Server Operations Manual

**Server 1 (Prod)**: `yyj` (Alias) | IP: `54.169.3.40`
**Location**: `/opt/MusicalBot`

**Server 2 (Legacy/Bot)**: `aliyun` (Alias) | IP: `47.117.167.13`
**Specs**: 2 Core / 2GB RAM / 40GB SSD
**Location**: `/bots/MusicalBot`
> [!WARNING] pending_refactor
> This server is currently managed via `tmux` and runs as **ROOT**.
> Future Goal: Migrate capabilities to unify with standard deployment.

## SSH Connection
```bash
ssh yyj    # Production (AWS)
ssh aliyun # Bot Server (Aliyun) - ROOT ACCESS
```

## Service Management

### Server 1: `yyj` (Supervisor)
The web service is managed by `supervisor`.

| Action | Command |
| :--- | :--- |
| **Restart** | `ssh yyj "sudo supervisorctl restart musicalbot_web"` |
| **Stop** | `ssh yyj "sudo supervisorctl stop musicalbot_web"` |
| **Start** | `ssh yyj "sudo supervisorctl start musicalbot_web"` |
| **Status** | `ssh yyj "sudo supervisorctl status"` |

### Server 2: `aliyun` (Tmux)
> [!CAUTION]
> Runs as ROOT. Be careful with file operations.

**Process Management (Tmux)**:
1.  **Attach Session**: `ssh aliyun "tmux attach -t qqbot"`
2.  **Detach**: Press `Ctrl+B` then `D`.
3.  **Start New**: `ssh aliyun "tmux new -s qqbot"` (Then run `python3 main.py`)
4.  **Kill**: `ssh aliyun "tmux kill-session -t qqbot"`

## Logs

| Log Type | Command |
| :--- | :--- |
| **Live Tail** | `ssh yyj "sudo supervisorctl tail -f musicalbot_web stdout"` |
| **Error Log** | `ssh yyj "sudo supervisorctl tail -f musicalbot_web stderr"` |
| **System Info** | `ssh yyj "df -h && free -m"` |

## Docker (Umami Analytics)

Located in `/opt/MusicalBot/docker-compose.umami.yml`.

```bash
# Check status
ssh yyj "sudo docker compose -f /opt/MusicalBot/docker-compose.umami.yml ps"

# Restart
ssh yyj "sudo docker compose -f /opt/MusicalBot/docker-compose.umami.yml restart"
```

## Maintenance Scripts

These scripts are located in `/opt/MusicalBot/scripts/` on the server.

### 1. Update & Restart (`update.sh`)
Pulls latest `v1` code and restarts the service.
```bash
ssh yyj "sudo /opt/MusicalBot/scripts/update.sh"
```

### 2. Safe Pull (`safe_pull.sh`)
Stashes local changes (if any) and forces a pull. Use if `update.sh` fails due to conflicts.
```bash
ssh yyj "sudo bash /opt/MusicalBot/scripts/safe_pull.sh"
```

## Troubleshooting
- **Permission Denied**: Ensure you are using `sudo` for supervisor/docker/git commands on server.
- **Port Busy**: Check if another instance is running (`ps aux | grep web_app.py`).

## Running Python Scripts on Server

> [!IMPORTANT]
> 服务器使用虚拟环境 `.venv`，直接使用 `python3` 可能缺少依赖（如 `sqlmodel`）。

**正确方式：使用虚拟环境的 Python**
```bash
cd /opt/MusicalBot
PYTHONPATH=/opt/MusicalBot .venv/bin/python scripts/your_script.py
```

**示例：运行数据清理脚本**
```bash
ssh yyj
cd /opt/MusicalBot
PYTHONPATH=/opt/MusicalBot .venv/bin/python scripts/cleanup_cast_data.py --apply
```

**常见错误**
| 错误 | 原因 | 解决方案 |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'sqlmodel'` | 使用了系统 Python | 使用 `.venv/bin/python` |
| `Permission denied` | 脚本无执行权限 | 用 `python scripts/xxx.py` 而不是 `./scripts/xxx.py` |
