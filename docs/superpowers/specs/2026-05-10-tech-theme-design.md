# 科技风主题与风格切换 — 设计规范

## 概述

为校园网流量分析助手增加「科技风（Tech Dark）」主题，与现有「简明风（Clean Light）」支持通过顶栏月亮 icon 一键切换。主题状态持久化到 `localStorage`。

---

## 方案选型

**CSS 变量切换**：在 `index.css` 的 `@theme` 块中定义两套颜色变量，通过给 `<html>` 元素添加 `data-theme="tech"` 属性激活科技风。React 侧用 `useTheme` hook 管理状态。ECharts 使用独立的 theme JSON 文件，在 theme 变化时传给 `ReactECharts` 的 `theme` prop。

---

## CSS 变量定义

### 简明风（默认，无 data-theme）
现有变量保持不变：
```css
--color-background: hsl(210 20% 98%)
--color-foreground: hsl(222.2 84% 4.9%)
--color-card: hsl(0 0% 100%)
--color-primary: hsl(221.2 83.2% 53.3%)
--color-primary-foreground: hsl(210 40% 98%)
--color-muted: hsl(210 40% 96.1%)
--color-muted-foreground: hsl(215.4 16.3% 46.9%)
--color-border: hsl(214.3 31.8% 91.4%)
```

### 科技风（`[data-theme="tech"]`）
```css
--color-background: #0a0e1a
--color-foreground: #a0c4d8
--color-card: #0d1117
--color-card-foreground: #e2f4ff
--color-primary: #0077cc
--color-primary-foreground: #e2f4ff
--color-muted: #0d1f3a
--color-muted-foreground: #2a5f85
--color-border: #1e3a5f
--color-destructive: hsl(0 70% 50%)
--color-destructive-foreground: #e2f4ff
/* 科技风专用 */
--color-accent: #00d4ff
--color-accent-muted: rgba(0, 212, 255, 0.08)
--color-glow: rgba(0, 212, 255, 0.15)
```

---

## 组件变更

### `index.css`
- 在 `@theme` 块之后，添加 `[data-theme="tech"]` CSS 规则块，覆盖所有颜色变量。
- 添加科技风专用变量（`--color-accent`、`--color-accent-muted`、`--color-glow`）。
- 添加科技风的 `body` 背景渐变：`radial-gradient(ellipse at 70% 10%, rgba(0,212,255,0.04), transparent 50%)`。
- 添加科技风的滚动条样式（细条深色）。

### `useTheme.ts`（新建 hook）
- 状态：`theme: "light" | "tech"`，初始值从 `localStorage.getItem("theme")` 读取，默认 `"light"`。
- 切换：`toggleTheme()` 在两个值间切换，写入 `localStorage`，同步设置 `document.documentElement.dataset.theme`（`"light"` 时删除该属性）。
- 导出：`{ theme, toggleTheme }`。

### `App.tsx`
- 引入 `useTheme`，将 `toggleTheme` 绑定到顶栏月亮 icon 的 `onClick`。
- 月亮 icon 在 `theme === "tech"` 时显示激活态样式（`color: var(--color-accent)`）。
- 将 `theme` 通过 prop 向下传给 `ChartRenderer`。

### `ChartRenderer.tsx`
- 新增 `theme?: "light" | "tech"` prop。
- 新建 `src/lib/echartsTheme.ts`，导出科技风 ECharts theme JSON（调色盘用 `#0088cc, #0099dd, #00aaee, #4a7fa5, #2a5f85`，背景透明，文字 `#4a7fa5`，坐标轴线 `#1e3a5f`，分割线 `#1e3a5f44`）。
- 在模块初始化时用 `echarts.registerTheme("tech", techTheme)` 注册。
- `ReactECharts` 的 `theme` prop：`theme === "tech" ? "tech" : undefined`。

### 其他组件（`ChatPanel`、`SessionSidebar`、`InputBar`、`ProgressBar`）
- 这些组件已全部使用 `var(--color-*)` CSS 变量，**无需修改**，变量切换后自动生效。

---

## ECharts 科技风主题配置要点

| 项目 | 值 |
|------|-----|
| 背景色 | `transparent` |
| 调色盘 | `["#0088cc","#0099dd","#00aaee","#4a7fa5","#2a5f85","#006699","#005588"]` |
| 文字颜色 | `#4a7fa5` |
| 坐标轴线颜色 | `#1e3a5f` |
| 分割线颜色 | `rgba(30,58,95,0.4)` |
| 提示框背景 | `#0d1422` |
| 提示框边框 | `#1e3a5f` |

无发光/阴影特效，保持清晰可读。

---

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `frontend/src/index.css` | 添加 `[data-theme="tech"]` 变量块 |
| `frontend/src/hooks/useTheme.ts` | 新建 |
| `frontend/src/lib/echartsTheme.ts` | 新建 |
| `frontend/src/App.tsx` | 引入 useTheme，绑定月亮 icon，传 theme prop |
| `frontend/src/components/ChartRenderer.tsx` | 接收 theme prop，注册并应用 ECharts 主题 |

---

## 行为规范

- 首次访问默认简明风。
- 切换后刷新页面保持上次选择（`localStorage` 持久化）。
- `document.documentElement.dataset.theme` 在 `"light"` 时不设置（保持默认），`"tech"` 时设为 `"tech"`。
- 月亮 icon tooltip 文案：简明风时显示"切换到科技风"，科技风时显示"切换到简明风"。
