# Agent 开发日常操作指南

本文档指导开发者如何在日常工作中，主动确保 AI Agent 遵守 [ARCHITECTURE.md](../ARCHITECTURE.md)。

## 1. 自动化防线 (One-Time Setup)

首先，安装 Git Hook，将架构检查固化到代码提交过程中。

```bash
# 在终端运行一次即可
chmod +x scripts/install_hooks.sh
./scripts/install_hooks.sh
```

**效果**：当你（或代理）尝试 `git commit` 时，如果代码包含了“Bot 写爬虫”或“Engine 手写 Dict”等违规行为，提交会被自动拦截。

---

## 2. “起手式”协议 (The Priming Protocol)

在每次开启新的 Agent 会话（或分配新任务）时，使用以下 **标准 Prompt** 进行“架构对齐”。

### 场景 A：开发新功能
>
> **User**: "我们要开发 [功能名称]。在开始 Plan 之前，请运行 `/workflow compliance_check`，并阅读 `ARCHITECTURE.md` 确认你的设计符合 Producer-Consumer 隔离原则。"

### 场景 B：代码审查
>
> **User**: "在提交代码前，请运行 `python scripts/arch_lint.py` 自检，并检查 `services/hulaquan/models.py` 确保复用了现有数据结构。"

---

## 3. 验收清单 (The Review Checklist)

在验收 Agent 的成果时，重点检查以下三点（这也是 Agent 最容易“漂移”的地方）：

1. **Engine 检查**：
    * *问*："Engine 里是用 `TicketUpdate(...)` 还是手写的 `{...}` ?"
    * *查*：搜索 `services/notification/engine.py` 中的 `messages.append`。

2. **Bot 检查**：
    * *问*："Bot (main_bot_v2) 有没有 import 任何 `crawler` 或 `web` 相关的包？"
    * *查*：运行 `grep "import" main_bot_v2.py`。

3. **Model 检查**：
    * *问*："你新加的字段，是在 `models.py` 定义的吗？"
    * *查*：确保没有在业务逻辑中散落神秘的字符串 Key。

---

## 4. 遇到 Agent "嘴硬" 怎么办？

如果 Agent 试图辩解说“为了方便，我就先直接写在 dict 里吧”，请直接回复：

> **User**: "DENIED. Violates [CRITICAL_RULE] in ARCHITECTURE.md: Schema Enforced. Refactor to use Pydantic."

（引用文档中的 `<CRITICAL_RULES>` 标签对 Agent 有极强的约束力。）
