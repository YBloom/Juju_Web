# AWS Deployment Log (Test Bot)
Date: 2026-01-07

## Plan
1.  **Sync Code**: Commit local changes -> Push to GitHub -> Pull on AWS.
2.  **Install NapCat**: Run Docker container for NapCat (Test Account `3132859862`).
3.  **Start Bot**: Run `main_bot_v2.py` on AWS.

## Command Log

| Step | Command | Description | Status |
| :--- | :--- | :--- | :--- |
| Check Conn | `ssh yyj "uname -a"` | Verify SSH connectivity | ✅ Success |
| Git Sync (Local) | `git push origin v1` | Push local code changes | ✅ Success |
| Git Sync (Remote) | `ssh yyj "cd /opt/MusicalBot && sudo git pull"` | Pull changes to server | Pending |
| Deps Install | `ssh yyj "cd /opt/MusicalBot && sudo pip3 install -r requirements.txt"` | Install upgraded ncatbot | Pending |
