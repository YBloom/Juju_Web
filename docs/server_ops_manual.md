# Server Operations Manual

**Server**: `yyj` (Alias) | IP: `54.169.3.40`
**Location**: `/opt/MusicalBot`

## SSH Connection
```bash
ssh yyj
```

## Service Management (Supervisor)

The web service is managed by `supervisor`.

| Action | Command |
| :--- | :--- |
| **Restart** | `ssh yyj "sudo supervisorctl restart musicalbot_web"` |
| **Stop** | `ssh yyj "sudo supervisorctl stop musicalbot_web"` |
| **Start** | `ssh yyj "sudo supervisorctl start musicalbot_web"` |
| **Status** | `ssh yyj "sudo supervisorctl status"` |

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
