# Tech Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为校园网流量分析助手添加科技风（Tech Dark）主题，支持通过顶栏月亮 icon 与简明风（Clean Light）切换，主题状态持久化到 localStorage。

**Architecture:** 在 `index.css` 的 `@theme` 块之后添加 `[data-theme="tech"]` CSS 规则覆盖颜色变量，React 侧用 `useTheme` hook 管理状态并写入 `localStorage`，ECharts 注册独立 theme JSON 后通过 `theme` prop 切换配色。

**Tech Stack:** React 19, Tailwind v4 CSS variables, ECharts 6, echarts-for-react 3, lucide-react

---

## File Map

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `frontend/src/hooks/useTheme.ts` | 主题状态管理 + localStorage 持久化 |
| 新建 | `frontend/src/lib/echartsTheme.ts` | 科技风 ECharts theme JSON 注册 |
| 修改 | `frontend/src/index.css` | 添加科技风 CSS 变量块 |
| 修改 | `frontend/src/App.tsx` | 绑定 useTheme，月亮 icon 激活态，传 theme prop |
| 修改 | `frontend/src/components/ChartRenderer.tsx` | 接收 theme prop，应用 ECharts 主题 |

---

### Task 1: CSS 变量 — 科技风颜色定义

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: 在 `index.css` 末尾追加科技风变量块和 body 样式**

将以下内容追加到 `frontend/src/index.css` 末尾（现有内容完整保留）：

```css
[data-theme="tech"] {
  --color-background: #0a0e1a;
  --color-foreground: #a0c4d8;
  --color-card: #0d1117;
  --color-card-foreground: #e2f4ff;
  --color-primary: #0077cc;
  --color-primary-foreground: #e2f4ff;
  --color-muted: #0d1f3a;
  --color-muted-foreground: #2a5f85;
  --color-border: #1e3a5f;
  --color-destructive: hsl(0 70% 50%);
  --color-destructive-foreground: #e2f4ff;
  --color-accent: #00d4ff;
  --color-accent-muted: rgba(0, 212, 255, 0.08);
}

[data-theme="tech"] body {
  background-image: radial-gradient(ellipse at 70% 10%, rgba(0, 212, 255, 0.04), transparent 50%);
}

[data-theme="tech"] ::-webkit-scrollbar {
  width: 4px;
}
[data-theme="tech"] ::-webkit-scrollbar-track {
  background: transparent;
}
[data-theme="tech"] ::-webkit-scrollbar-thumb {
  background: #1e3a5f;
  border-radius: 2px;
}
```

- [ ] **Step 2: 在浏览器 DevTools 手动验证变量覆盖**

打开前端（`cd frontend && npm run dev`），在浏览器 Console 运行：
```js
document.documentElement.setAttribute('data-theme', 'tech')
```
预期：页面背景变深色 `#0a0e1a`，侧边栏、顶栏变 `#0d1117`，文字变蓝灰色。

- [ ] **Step 3: 还原 data-theme（验证完毕后）**

```js
document.documentElement.removeAttribute('data-theme')
```
预期：恢复白色简明风。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: add tech dark CSS variable block"
```

---

### Task 2: useTheme hook

**Files:**
- Create: `frontend/src/hooks/useTheme.ts`

- [ ] **Step 1: 创建 `useTheme.ts`**

```ts
import { useState, useEffect } from "react";

type Theme = "light" | "tech";

const STORAGE_KEY = "app-theme";

function applyTheme(theme: Theme) {
  if (theme === "tech") {
    document.documentElement.setAttribute("data-theme", "tech");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "tech" ? "tech" : "light";
  });

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "light" ? "tech" : "light"));

  return { theme, toggleTheme };
}
```

- [ ] **Step 2: 在浏览器 Console 手动冒烟测试**

启动前端后，在 Console 运行（稍后 Task 3 接入 UI 前的临时验证）：
```js
localStorage.setItem('app-theme', 'tech')
location.reload()
```
预期：刷新后页面自动应用深色科技风（Task 1 的颜色）。

```js
localStorage.removeItem('app-theme')
location.reload()
```
预期：恢复简明风。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useTheme.ts
git commit -m "feat: add useTheme hook with localStorage persistence"
```

---

### Task 3: ECharts 科技风主题

**Files:**
- Create: `frontend/src/lib/echartsTheme.ts`

- [ ] **Step 1: 创建 `echartsTheme.ts`**

```ts
import * as echarts from "echarts/core";

const techTheme = {
  color: ["#0088cc", "#0099dd", "#00aaee", "#4a7fa5", "#2a5f85", "#006699", "#005588"],
  backgroundColor: "transparent",
  textStyle: { color: "#4a7fa5" },
  title: { textStyle: { color: "#7eb8d4" } },
  legend: { textStyle: { color: "#4a7fa5" } },
  tooltip: {
    backgroundColor: "#0d1422",
    borderColor: "#1e3a5f",
    textStyle: { color: "#a0c4d8" },
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: "#1e3a5f" } },
    axisTick: { lineStyle: { color: "#1e3a5f" } },
    axisLabel: { color: "#2a5f85" },
    splitLine: { lineStyle: { color: "rgba(30,58,95,0.4)" } },
  },
  valueAxis: {
    axisLine: { lineStyle: { color: "#1e3a5f" } },
    axisTick: { lineStyle: { color: "#1e3a5f" } },
    axisLabel: { color: "#2a5f85" },
    splitLine: { lineStyle: { color: "rgba(30,58,95,0.4)" } },
  },
  line: { itemStyle: { borderWidth: 2 } },
  bar: { itemStyle: { borderRadius: [3, 3, 0, 0] } },
};

echarts.registerTheme("tech", techTheme);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/echartsTheme.ts
git commit -m "feat: register ECharts tech theme"
```

---

### Task 4: App.tsx — 接入 useTheme，绑定月亮 icon

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 修改 `App.tsx`，引入 useTheme 并绑定月亮 icon**

完整替换后的 `App.tsx`：

```tsx
import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { Settings, Moon } from "lucide-react";
import { SessionSidebar } from "./components/SessionSidebar";
import { ChatPanel } from "./components/ChatPanel";
import { InputBar } from "./components/InputBar";
import { useWebSocket } from "./hooks/useWebSocket";
import { useTheme } from "./hooks/useTheme";
import { Button } from "./components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./components/ui/tooltip";
import type { Session } from "./types";

export default function App() {
  const [sessionId, setSessionId] = useState(() => uuidv4());
  const [sessions, setSessions] = useState<Session[]>([]);
  const { messages, isLoading, sendMessage } = useWebSocket(sessionId);
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/sessions")
      .then((r) => r.json())
      .then(setSessions)
      .catch(() => {});
  }, [sessionId]);

  const handleNew = () => setSessionId(uuidv4());

  return (
    <TooltipProvider>
      <div className="flex flex-col h-screen bg-[var(--color-background)]">
        <header className="flex items-center justify-between px-5 py-3 border-b bg-[var(--color-card)] shadow-sm backdrop-blur supports-[backdrop-filter]:bg-[var(--color-card)]/95">
          <div className="flex items-center gap-2">
            <span className="text-[var(--color-primary)] text-lg">⚡</span>
            <h1 className="text-sm font-semibold text-[var(--color-foreground)] tracking-tight">
              校园网流量分析助手
            </h1>
          </div>
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="切换主题"
                  onClick={toggleTheme}
                >
                  <Moon
                    className="h-4 w-4"
                    style={{
                      color:
                        theme === "tech"
                          ? "var(--color-accent)"
                          : "var(--color-muted-foreground)",
                    }}
                  />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {theme === "tech" ? "切换到简明风" : "切换到科技风"}
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="设置">
                  <Settings className="h-4 w-4 text-[var(--color-muted-foreground)]" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>设置（暂未实现）</TooltipContent>
            </Tooltip>
          </div>
        </header>
        <div className="flex flex-1 overflow-hidden">
          <SessionSidebar
            sessions={sessions}
            activeId={sessionId}
            onSelect={setSessionId}
            onNew={handleNew}
          />
          <div className="flex flex-col flex-1 overflow-hidden">
            <ChatPanel messages={messages} theme={theme} />
            <InputBar onSend={sendMessage} disabled={isLoading} />
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
```

- [ ] **Step 2: 手动测试切换**

在浏览器点击月亮 icon，预期：
- 界面立即从白色切换到深蓝黑科技风
- Tooltip 文案在"切换到科技风"和"切换到简明风"之间变化
- Moon icon 在科技风下变为青蓝色（`#00d4ff`）
- 刷新页面后主题保持不变

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire moon icon to theme toggle"
```

---

### Task 5: ChartRenderer — 接入 ECharts 主题

**Files:**
- Modify: `frontend/src/components/ChartRenderer.tsx`
- Modify: `frontend/src/components/ChatPanel.tsx`

- [ ] **Step 1: 修改 `ChartRenderer.tsx`，引入 theme prop 和 ECharts 主题注册**

```tsx
import ReactECharts from "echarts-for-react";
import "../lib/echartsTheme";

interface Props {
  render: "echarts" | "html" | "table" | "text";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any;
  insight?: string;
  theme?: "light" | "tech";
}

export function ChartRenderer({ render, content, insight, theme }: Props) {
  if (render === "echarts") {
    return (
      <div className="w-full">
        {insight && (
          <p className="text-sm text-[var(--color-muted-foreground)] mb-2">
            {insight}
          </p>
        )}
        <ReactECharts
          option={content}
          theme={theme === "tech" ? "tech" : undefined}
          style={{ height: 350 }}
        />
      </div>
    );
  }
  if (render === "html") {
    return (
      <iframe
        srcDoc={content}
        className="w-full border rounded"
        style={{ height: 500 }}
        sandbox="allow-scripts"
      />
    );
  }
  return (
    <p className="text-sm text-[var(--color-foreground)] whitespace-pre-wrap">
      {content}
    </p>
  );
}
```

- [ ] **Step 2: 修改 `ChatPanel.tsx`，接收并向下传递 theme prop**

完整替换后的 `ChatPanel.tsx`：

```tsx
import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import { ChartRenderer } from "./ChartRenderer";
import { ProgressBar } from "./ProgressBar";

interface Props {
  messages: ChatMessage[];
  theme?: "light" | "tech";
}

export function ChatPanel({ messages, theme }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col gap-4 p-5 overflow-y-auto flex-1 bg-[var(--color-background)]">
      {messages.map((msg) => {
        if (msg.type === "user") {
          return (
            <div key={msg.id} className="flex justify-end">
              <div className="bg-[var(--color-primary)] text-[var(--color-primary-foreground)] rounded-2xl rounded-br-sm px-4 py-2.5 max-w-lg text-sm leading-relaxed shadow-sm">
                {msg.content}
              </div>
            </div>
          );
        }
        if (msg.type === "progress") {
          return <ProgressBar key={msg.id} content={msg.content} />;
        }
        if (msg.type === "clarify") {
          return (
            <div key={msg.id} className="flex justify-start">
              <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-2xl rounded-bl-sm px-4 py-2.5 max-w-lg text-sm text-[var(--color-foreground)] leading-relaxed shadow-sm">
                {msg.content}
              </div>
            </div>
          );
        }
        if (msg.type === "result") {
          return (
            <div
              key={msg.id}
              className="w-full bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5 shadow-md"
            >
              <ChartRenderer
                render={msg.render!}
                content={msg.content}
                theme={theme}
              />
            </div>
          );
        }
        if (msg.type === "error") {
          return (
            <div
              key={msg.id}
              className="text-[var(--color-destructive)] text-sm px-4 py-2.5 bg-[var(--color-destructive)]/10 border border-[var(--color-destructive)]/20 rounded-lg"
            >
              {msg.content}
            </div>
          );
        }
        return null;
      })}
      <div ref={bottomRef} />
    </div>
  );
}
```

- [ ] **Step 3: 验证图表主题切换**

在有图表输出的会话中切换主题，预期：
- 科技风：ECharts 图表坐标轴变 `#1e3a5f`，标签变 `#2a5f85`，柱/线颜色变蓝系调色盘，tooltip 深色背景
- 简明风：ECharts 恢复默认配色
- 切换后已渲染的图表立即更新（ReactECharts 在 theme prop 变化时自动重绘）

- [ ] **Step 4: TypeScript 编译检查**

```bash
cd frontend && npx tsc --noEmit
```
预期：无错误输出。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChartRenderer.tsx frontend/src/components/ChatPanel.tsx
git commit -m "feat: apply ECharts tech theme on chart render"
```

---

### Task 6: 端到端验收

**Files:** 无新增，仅验证

- [ ] **Step 1: 启动前端**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: 验收清单**

| 场景 | 预期结果 |
|------|---------|
| 首次加载 | 简明白色风格，月亮 icon 灰色 |
| 点击月亮 icon | 立即切换到科技风，背景 `#0a0e1a`，月亮 icon 变青蓝色 |
| Tooltip hover | 显示"切换到简明风" |
| 刷新页面 | 保持科技风（localStorage） |
| 再次点击月亮 | 切换回简明风 |
| 刷新页面 | 保持简明风 |
| 有图表时切换 | ECharts 图表颜色同步更新 |
| 错误消息 | 红色样式在两种主题下均可辨认 |

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: tech dark theme with toggle complete"
```
