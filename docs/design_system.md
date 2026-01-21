# Design System (设计系统) - Agent 开发规范

> **重要提示**：本文档为强制性规范。所有 UI 代码必须 100% 遵循本规范。

## 核心原则 (Core Principles)

1.  **语义化优先 (Semantics First)**：永远使用语义 Token (`--primary-color`)，而非原子 Token (`--green-500`)。
2.  **一致性至上 (Consistency Above All)**：禁止任何硬编码值。所有样式必须来自 `variables.css`。
3.  **移动端友好 (Mobile-Friendly)**：使用响应式单位 (`rem`, `%`)，谨慎使用 `px`。

---

## Token 字典 (Token Dictionary)

所有可用变量定义在 [`variables.css`](file:///Users/yaobii/Developer/MY PROJECTS/MusicalBot/web/static/css/variables.css)。

### 颜色 (Colors)

| 语义变量 | 说明 | 原子值 |
|---------|------|--------|
| `--primary-color` | 主题色 (Sage Green) | `#637E60` |
| `--accent-color` | 强调色 (Terracotta) | `#D9885E` |
| `--text-primary` | 主文本色 | `#3C403B` |
| `--text-secondary` | 次级文本 | `#6B7068` |
| `--bg-color` | 背景色 | `#FDFDFB` |
| `--card-bg` | 卡片背景 | `#FFFFFF` |
| `--border-color` | 边框色 | `#E8E6DE` |

### 间距 (Spacing)

| 语义变量 | 用途 | 值 |
|---------|------|-----|
| `--container-padding` | 容器内边距 | `20px` |
| `--card-padding` | 卡片内边距 | `24px` |
| `--section-gap` | 区块间距 | `24px` |
| `--section-margin` | 大区块外边距 | `40px` |

**原子变量**: `--space-4`, `--space-8`, ..., `--space-48` (禁止直接使用)

### 圆角 (Radius)

| 语义变量 | 用途 | 值 |
|---------|------|-----|
| `--btn-radius` | 按钮圆角 | `12px` |
| `--card-radius` | 卡片圆角 | `20px` |
| `--input-radius` | 输入框圆角 | `12px` |
| `--modal-radius` | 弹窗圆角 | `24px` |
| `--radius-pill` | 胶囊圆角 | `50px` |

### 阴影 (Shadows)

| 语义变量 | 用途 |
|---------|------|
| `--shadow-soft` | 轻柔阴影 (卡片默认) |
| `--shadow-card` | 卡片阴影 (悬浮感) |
| `--shadow-btn` | 按钮阴影 |

### 排版 (Typography)

| 变量 | 用途 | 值 |
|------|------|-----|
| `--text-xs` ~ `--text-3xl` | 字号比例 | `0.75rem` ~ `1.6rem` |
| `--font-heading` | 标题字体 | `Outfit` |
| `--font-body` | 正文字体 | `Inter` |
| `--font-mono` | 等宽字体 | `JetBrains Mono` |

---

## ❌ 禁止清单 (The "Never" List)

### 1. 严禁内联样式
**错误示例**:
```html
<div style="padding: 16px; color: #637E60;">
```

**正确示例**:
```html
<div class="p-md text-primary">
```

### 2. 严禁硬编码颜色
**错误示例**:
```css
.my-card {
    background: #FFFFFF;
    border: 1px solid #E8E6DE;
}
```

**正确示例**:
```css
.my-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
}
```

### 3. 严禁 Magic Number
**错误示例**:
```css
.header {
    padding: 17px;
    margin-bottom: 23px;
}
```

**正确示例**:
```css
.header {
    padding: var(--container-padding);
    margin-bottom: var(--section-gap);
}
```

### 4. 严禁自行发明变量名
**如果 Token 不存在，停下并提问**。禁止编造如 `--my-special-color` 的新变量。

---

## ✅ Do & Don't 代码对比

### 场景 1: 创建卡片组件

**❌ Bad Code (反面教材)**:
```html
<div style="background: white; padding: 20px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
    <h3 style="color: #637E60; font-size: 18px;">标题</h3>
    <p style="color: #666;">内容</p>
</div>
```

**✅ Good Code (标准写法)**:
```html
<div class="card">
    <h3 class="card-title">标题</h3>
    <p class="card-text">内容</p>
</div>
```

```css
.card {
    background: var(--card-bg);
    padding: var(--card-padding);
    border-radius: var(--card-radius);
    box-shadow: var(--shadow-soft);
}

.card-title {
    color: var(--primary-color);
    font-size: var(--text-lg);
}

.card-text {
    color: var(--text-secondary);
}
```

### 场景 2: 移除内联样式的安全替换

**❌ 直接删除并凭感觉重写**:
```html
<!-- Before -->
<div style="display: flex; align-items: center; padding: 12px;">

<!-- Bad After: 样式丢失 -->
<div class="some-class">
```

**✅ 使用 Utility Classes 平替**:
```html
<!-- Before -->
<div style="display: flex; align-items: center; padding: 12px;">

<!-- Good After -->
<div class="flex-center p-sm">
```

---

## Utility Classes (工具类速查)

在 [`style.css`](file:///Users/yaobii/Developer/MY PROJECTS/MusicalBot/web/static/css/style.css) 中已定义的工具类：

```css
/* Spacing */
.p-sm { padding: var(--space-8); }
.p-md { padding: var(--space-16); }
.p-lg { padding: var(--space-24); }

/* Layout */
.flex-center { display: flex; align-items: center; justify-content: center; }
.w-full { width: 100%; }

/* Typography */
.text-primary { color: var(--text-primary); }
.text-secondary { color: var(--text-secondary); }

/* Radius */
.rounded-md { border-radius: var(--radius-md); }
.rounded-pill { border-radius: var(--radius-pill); }
```

---

## Agent 合规性检查清单 (Self-Check)

在完成代码后，必须提问自己：
1.  ✅ **是否存在内联 `style="..."` 属性？** → 应为 0
2.  ✅ **是否使用了 Hex 颜色 (如 `#FFFFFF`)？** → 应全为 `var(--...)`
3.  ✅ **是否直接使用了 `px` 数值 (除边框外)？** → 应使用语义变量
4.  ✅ **是否包含未定义的新变量？** → 禁止，请先查阅 Token 字典

---

## 响应式设计 (Responsive Design)

### 断点变量
使用 `--breakpoint-md` (768px) 作为移动端/桌面端分界。

### 示例
```css
@media (max-width: 768px) {
    .header {
        padding: var(--space-16);
    }
}
```

---

## 维护指南 (Maintenance)

### 定期审查 (每季度)
1.  检查 `variables.css` 是否有未使用的旧变量。
2.  验证所有语义 Token 是否仍符合设计意图。

### 新增 Token 流程
1.  先在 Primitive 层定义原子值。
2.  在 Semantic 层创建映射。
3.  更新本文档的 Token 字典。

---

## 参考资源

-   **Token 定义**: [`variables.css`](file:///Users/yaobii/Developer/MY PROJECTS/MusicalBot/web/static/css/variables.css)
-   **Workflow**: [重构 UI 组件标准流程](file:///Users/yaobii/.agent/workflows/refactor_ui_component.md)
-   **Skill**: [设计合规性检查工具](file:///Users/yaobii/.agent/skills/check_design_compliance/SKILL.md)
