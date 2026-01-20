# SSH 开发与部署准则

## 核心原则
>
> **[CRITICAL] 严禁直接在服务器上修改代码！**
> **[CRITICAL] NEVER edit code directly on the server!**

服务器上的代码必须始终与 Git 仓库保持一致。任何直接在服务器上的修改都会导致 `git pull` 冲突，并在下次部署时被覆盖或引发错误。

## 标准开发流程

1. **本地开发**：
   - 在本地环境中修改代码、修复 Bug 或添加新功能。
   - 在本地运行测试，确保代码正常工作。

2. **提交与推送**：
   - 使用 git 提交更改：`git commit -m "feat: description"`
   - 推送到远程仓库：`git push origin v1` (或其他对应分支)

3. **服务器部署**：
   - SSH 登录服务器：`ssh yyj`
   - 进入项目目录：`cd /opt/MusicalBot`
   - 拉取最新代码：`git pull`
   - (如有必要) 更新依赖：`source .venv/bin/activate && pip install -r requirements.txt`
   - 重启服务：`sudo systemctl restart musicalbot` 或手动重启 uvicorn。

## 紧急修复流程

即使是紧急修复（Hotfix），也**必须**遵循上述流程。
不允许为了图快而跳过 Git 流程直接在服务器编辑 `py` 或 `html` 文件。

## 服务器状态维护

- 保持 `git status` 干净。
- 如果不慎在服务器上产生了修改，请使用 `git stash` 暂存或 `git reset --hard HEAD` 放弃修改，然后再执行 `git pull`。
