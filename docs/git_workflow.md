# Git & Deployment Workflow

## Core Principles
1. **Source of Truth**: The `v1` branch on GitHub is the single source of truth.
2. **Local First**: All changes must be committed locally and pushed.
3. **No Direct Edits**: **NEVER** edit files directly on the server (except for untracked `.env` or logs).

## Development Cycle

### 1. Local Development
```bash
# Make changes
# Test locally (./dev.sh)
git add .
git commit -m "feat: description"
git push origin v1
```

### 2. Deployment (Server Update)
Only perform this step if testing is passed and user requests deployment.

**Option A: Standard Update (Recommended)**
(Uses `update.sh` which handles pull + restart)
```bash
ssh yyj "sudo /opt/MusicalBot/scripts/update.sh"
```

**Option B: Manual Pull (For Debugging)**
```bash
ssh yyj
cd /opt/MusicalBot
sudo git stash      # Save any on-server hacks (though there shouldn't be any)
sudo git pull origin v1
sudo supervisorctl restart musicalbot_web
```

## Emergency Hotfix
If `git pull` fails on server due to conflicts:
1. Run `ssh yyj "sudo bash /opt/MusicalBot/scripts/safe_pull.sh"`
2. This forces a reset to origin/v1.
