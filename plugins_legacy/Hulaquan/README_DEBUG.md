# 呼啦圈上新通知调试工具包

## 📦 包含文件

### 1. `debug_announcer.py` - 核心调试工具
完整的调试器类，包含：
- 模拟数据生成
- 消息生成测试
- 用户设置检查
- 任务状态检查

### 2. `DEBUG_GUIDE.md` - 详细调试指南
完整的调试流程和问题排查文档

### 3. `quick_test.py` - 快速测试脚本
可独立运行的测试脚本，用于快速检查系统状态

---

## 🚀 快速开始

### 方式一：在 Bot 运行时使用命令（推荐）

```bash
# 1. 检查定时任务状态
/debug通知 check

# 2. 查看你的关注设置
/debug通知 user

# 3. 使用模拟数据测试
/debug通知 mock

# 4. 手动触发一次刷新（管理员）
/refresh
```

### 方式二：使用 Python 脚本

```bash
cd f:\MusicalBot\plugins\Hulaquan
python quick_test.py
```

### 方式三：在 Bot 代码中调用

```python
from plugins.Hulaquan.debug_announcer import run_debug_tests

# 运行完整调试流程
await run_debug_tests(plugin_instance)
```

---

## 🔍 典型问题诊断流程

### 问题：用户反馈收不到上新通知

#### Step 1: 检查任务运行
```
/debug通知 check
```
**预期结果：** 
- ✅ 运行状态: 运行中
- ⏰ 检测间隔: 120~300秒

**如果未运行：**
```
/呼啦圈检测  # 管理员命令开启
```

#### Step 2: 检查用户设置
```
/debug通知 user
```
**预期结果：**
- 全局模式: 1/2/3（不是0）
- 如果只关注特定剧目，确认上新的是这些剧目

**如果模式为0：**
```
/呼啦圈通知 1  # 切换到模式1
```

#### Step 3: 模拟测试
```
/debug通知 mock
```
**预期结果：**
- ✅ 成功生成消息

**如果没有生成消息：**
- 说明问题在用户设置，返回 Step 2
- 检查全局模式和关注列表

**如果生成了消息：**
- 说明消息生成逻辑正常
- 问题在数据比对或发送环节

#### Step 4: 查看日志
```powershell
# 查看最新日志
Get-Content f:\MusicalBot\logs\bot.log -Tail 100

# 搜索关键词
Select-String -Path f:\MusicalBot\logs\bot.log -Pattern "呼啦圈|announcer" | Select-Object -Last 20
```

---

## 📊 关注模式说明

### 模式对照表

| 模式 | 说明 | 接收通知类型 |
|------|------|------------|
| 0 | ❌ 不接受通知 | 无 |
| 1 | 🆕 基础模式 | 上新、补票、待开票 |
| 2 | 🔄 进阶模式 | 模式1 + 回流票 |
| 3 | 📊 完整模式 | 模式2 + 增减票 |

### 票务变动类型

| 类型 | emoji | 说明 | 需要模式 |
|------|-------|------|---------|
| new | 🆕 | 上新 | 1+ |
| add | ➕ | 补票 | 1+ |
| pending | ⏰ | 待开票 | 1+ |
| return | 🔄 | 回流 | 2+ |
| back | 📈 | 增票 | 3+ |
| sold | 📉 | 减票 | 3+ |

---

## 🧪 测试场景

### 场景1：测试全局通知
```python
# 设置全局模式为1
/呼啦圈通知 1

# 等待下次刷新，或手动触发
/refresh

# 使用模拟数据测试
/debug通知 mock
```

### 场景2：测试特定剧目关注
```python
# 关注特定剧目（模式1）
/关注学生票 剧目名 -1

# 查看关注列表
/查看关注

# 测试
/debug通知 mock
```

### 场景3：测试特定场次关注
```python
# 关注特定场次（模式1）
/关注学生票 场次ID1 场次ID2 -t -1

# 查看关注列表
/查看关注

# 测试
/debug通知 mock
```

---

## 🐛 常见问题 FAQ

### Q1: 为什么 mock 测试能生成消息，但实际不会通知？

**A:** 问题在数据比对环节（`Hlq.compare_to_database_async()`）

**排查步骤：**
1. 手动 `/refresh` 触发刷新
2. 查看日志是否有错误
3. 检查网络连接
4. 确认呼啦圈API是否正常

### Q2: 定时任务一直在运行，但从来没收到通知？

**A:** 可能原因：
1. 数据比对一直返回空结果（没有变动）
2. 检测间隔太长，用户已通过其他渠道知道
3. 全局模式设置问题

**解决方案：**
- 使用 mock 测试确认消息生成正常
- 减小检测间隔
- 添加日志观察每次检测的结果

### Q3: 只有部分用户收不到？

**A:** 逐个检查用户设置
```
/debug通知 user  # 让该用户执行
```

可能原因：
- 该用户的模式为0
- 该用户只关注了特定剧目
- 该用户不在好友列表中（已被删除）

### Q4: 模拟测试无法生成消息？

**A:** 用户设置有问题

**检查项：**
- [ ] 全局模式是否为0？
- [ ] 是否只关注了特定剧目，但测试数据用的是其他剧目？
- [ ] 票务类型是否在用户关注范围内？

**解决：**
```
/呼啦圈通知 1  # 设置全局模式
```

---

## 📝 添加调试日志

如果需要更详细的日志，在 `main.py` 中添加：

```python
@user_command_wrapper("hulaquan_announcer")
async def on_hulaquan_announcer(self, test=False, manual=False, announce_admin_only=False):
    log.info(f"🔄 [Announcer] 开始执行，manual={manual}")
    
    try:
        result = await Hlq.compare_to_database_async()
        
        # 添加统计日志
        total_changes = sum(len(items) for items in result["categorized"].values())
        log.info(f"📊 [Announcer] 数据比对完成，总变动: {total_changes}")
        
        for cat, items in result["categorized"].items():
            if items:
                log.info(f"  - {cat}: {len(items)}")
        
        # ... 原有代码 ...
        
        # 在发送前记录
        log.info(f"👥 [Announcer] 准备为 {len(_users)} 个用户生成消息")
        
        for user_id, user in _users.items():
            messages = self.__generate_announce_text(...)
            log.info(f"👤 [Announcer] 用户 {user_id}: {len(messages)} 组消息")
            
            for idx, msg_group in enumerate(messages):
                m = "\n\n".join(msg_group)
                log.info(f"📤 [Announcer] 发送消息 #{idx+1}，长度: {len(m)}")
                r = await self.api.post_private_msg(user_id, m)
                log.info(f"📬 [Announcer] 发送结果: retcode={r.get('retcode')}")
                
                if r['retcode'] != 0:
                    log.error(f"❌ [Announcer] 发送失败: {r}")
```

---

## 🎯 最佳实践

### 开发阶段
1. 使用较短的检测间隔（60-120秒）
2. 启用详细日志
3. 使用 mock 数据频繁测试
4. 监控日志文件

### 生产环境
1. 适中的检测间隔（300-600秒）
2. 保留关键日志
3. 定期检查任务状态
4. 收集用户反馈

---

## 📞 需要帮助？

如果以上方法无法解决问题，请提供：

1. **基础信息**
   - Bot 版本
   - 插件版本
   - 运行环境

2. **测试结果**
   ```
   /debug通知 check
   /debug通知 user
   /debug通知 mock
   ```

3. **日志文件**
   - `logs/bot.log` 最近100行
   - 搜索 "announcer" 相关日志

4. **问题描述**
   - 什么时候应该收到通知但没收到
   - 是所有用户还是特定用户
   - 是所有类型还是特定类型的通知

---

## 🔧 工具文件说明

### `debug_announcer.py`
- `AnnouncerDebugger` 类：核心调试器
- `create_mock_ticket()`: 创建模拟票务
- `create_mock_result()`: 创建完整模拟结果
- `test_generate_announce_text()`: 测试消息生成
- `check_task_status()`: 检查任务状态
- `print_user_settings()`: 打印用户设置
- `simulate_announcer_once()`: 模拟完整流程

### `quick_test.py`
快速测试脚本，可以：
- 检查用户数据
- 检查呼啦圈数据
- 测试数据比对
- 提供诊断建议

### 使用建议
- **日常调试**：使用 `/debug通知` 命令
- **深度调试**：使用 Python 导入 `debug_announcer.py`
- **快速检查**：运行 `quick_test.py`
- **学习参考**：阅读 `DEBUG_GUIDE.md`
