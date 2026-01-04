# 服务器文件修改工作流

## 原则

**避免在服务器上直接修改被Git追踪的文件,以防止与Git同步冲突。**

---

## 工作流规则

### 1. 配置文件修改

对于需要在服务器上修改的文件(如 `index.html` 中的 Website ID),使用以下流程:

#### 方法A: 先在本地修改,再推送(推荐)

```bash
# 本地修改
cd /Users/yaobii/Developer/MY\ PROJECTS/MusicalBot
# 编辑文件...
git add .
git commit -m "更新配置"
git push origin v1

# 服务器拉取
ssh yyj "cd /opt/MusicalBot && sudo git stash && sudo git pull origin v1 && sudo git stash pop"
```

#### 方法B: 使用环境变量(最佳实践)

将动态配置放在 `.env` 文件中,不纳入Git:

```bash
# .env 文件(已在.gitignore中)
UMAMI_WEBSITE_ID=65e0c212-9644-47e1-a5f4-9dc3b27cffd8
```

然后在代码中读取:
```html
<script defer src="https://analytics.yaobii.com/script.js" 
        data-website-id="${UMAMI_WEBSITE_ID}"></script>
```

---

### 2. 服务器专属文件

某些文件只在服务器上存在,应该加入 `.gitignore`:

#### 当前未追踪的文件

```
web/static/report.html          # GoAccess报告(临时)
config/nginx_umami_subdomain.conf  # Nginx配置(服务器专属)
scripts/setup_umami_subdomain.sh   # 安装脚本(可选添加)
.env.umami                      # Umami环境变量(已忽略)
```

#### 建议操作

```bash
# 本地添加到 .gitignore
echo "web/static/report.html" >> .gitignore
echo "config/nginx_umami_subdomain.conf" >> .gitignore

# 提交
git add .gitignore
git commit -m "chore: 更新.gitignore,排除服务器专属文件"
git push origin v1
```

---

### 3. Agent修改服务器文件的标准流程

当我(Antigravity Agent)需要修改服务器文件时,遵循以下流程:

#### Step 1: 检查文件是否被Git追踪

```bash
ssh yyj "cd /opt/MusicalBot && git ls-files 文件路径"
```

#### Step 2: 如果被追踪,使用以下策略之一

**策略A: 仅用于临时测试**
```bash
# 修改后不提交,用户自行决定是否保留
ssh yyj "cd /opt/MusicalBot && sudo 编辑文件..."
# 提醒用户: "此修改未提交到Git,如需保留请手动commit"
```

**策略B: 提交到Git(推荐用于永久性修改)**
```bash
# 1. 在本地修改
在本地项目中修改文件

# 2. 提交到Git
git add 文件
git commit -m "描述"
git push origin v1

# 3. 服务器拉取
ssh yyj "cd /opt/MusicalBot && sudo git stash && sudo git pull origin v1 && sudo git stash pop"
```

**策略C: 使用配置文件(最佳)**
```bash
# 修改.env或其他非Git追踪的配置文件
ssh yyj "echo 'CONFIG_VALUE=xxx' | sudo tee -a /opt/MusicalBot/.env"
```

#### Step 3: 修改后重启服务

```bash
ssh yyj "sudo supervisorctl restart musicalbot_web"
```

---

### 4. 处理Git冲突(如果发生)

#### 检测冲突

```bash
ssh yyj "cd /opt/MusicalBot && git status"
```

#### 解决方案1: 保留服务器修改

```bash
ssh yyj "cd /opt/MusicalBot && sudo git stash && sudo git pull origin v1 && sudo git stash apply"
# 如果有冲突,手动解决
```

#### 解决方案2: 放弃服务器修改

```bash
ssh yyj "cd /opt/MusicalBot && sudo git reset --hard origin/v1"
```

#### 解决方案3: 合并修改

```bash
# 1. Stash服务器修改
ssh yyj "cd /opt/MusicalBot && sudo git stash"

# 2. Pull最新代码
ssh yyj "cd /opt/MusicalBot && sudo git pull origin v1"

# 3. Pop stash
ssh yyj "cd /opt/MusicalBot && sudo git stash pop"

# 4. 如果有冲突,查看冲突文件
ssh yyj "cd /opt/MusicalBot && git diff"

# 5. 手动解决冲突后
ssh yyj "cd /opt/MusicalBot && sudo git add . && sudo git commit -m '解决冲突'"
```

---

### 5. 自动化脚本

创建一个安全拉取脚本 `scripts/safe_pull.sh`:

```bash
#!/bin/bash
# 安全地从Git拉取最新代码

cd /opt/MusicalBot

echo "1. 保存当前修改..."
sudo git stash push -m "Auto-stash before pull $(date)"

echo "2. 拉取最新代码..."
sudo git pull origin v1

echo "3. 恢复之前的修改..."
if sudo git stash list | grep -q "Auto-stash"; then
    sudo git stash pop
    echo "✓ 修改已恢复"
else
    echo "✓ 无需恢复"
fi

echo "4. 重启服务..."
sudo supervisorctl restart musicalbot_web

echo "✓ 完成!"
```

使用:
```bash
ssh yyj "sudo bash /opt/MusicalBot/scripts/safe_pull.sh"
```

---

## 当前状态检查清单

- [ ] 服务器Git状态清理
- [ ] 更新 `.gitignore` 排除服务器专属文件
- [ ] 创建 `safe_pull.sh` 脚本
- [ ] 文档化配置项(哪些需要手动修改)

---

## 最佳实践总结

1. ✅ **配置分离**: 动态配置放 `.env`,不放Git
2. ✅ **本地优先**: 代码修改先在本地,再推送
3. ✅ **Stash保护**: Pull前先stash,pull后pop
4. ✅ **服务器只读**: 服务器上仅部署,不开发
5. ✅ **自动化脚本**: 用脚本标准化部署流程

---

**Future Agent Actions Checklist**:

当我需要修改服务器文件时:
- [ ] 检查文件是否在Git中 (`git ls-files 文件名`)
- [ ] 如果在Git中:
  - [ ] 优先在本地修改并push
  - [ ] 或使用`.env`等非Git文件
  - [ ] 或明确告知用户这是临时修改
- [ ] 修改后重启相关服务
- [ ] 提醒用户如何持久化修改
