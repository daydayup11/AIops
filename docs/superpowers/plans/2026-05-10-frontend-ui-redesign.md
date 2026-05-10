# Frontend UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the 校园网流量分析助手 frontend from basic Tailwind to a polished "modern minimal + dashboard card" style using shadcn/ui components.

**Architecture:** Install Radix UI primitives and utility packages manually (no shadcn CLI), add shadcn component source files under `src/components/ui/`, inject CSS variable tokens into `index.css` using Tailwind v4 `@theme` syntax, then restyle each existing component.

**Tech Stack:** React 19, TypeScript, Tailwind v4, Vite, Radix UI, lucide-react, class-variance-authority, clsx, tailwind-merge

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/package.json` | Modify | Add new npm dependencies |
| `frontend/vite.config.ts` | Modify | Add `@` path alias |
| `frontend/tsconfig.app.json` | Modify | Add `paths` for `@/*` |
| `frontend/src/index.css` | Modify | CSS variable tokens + page background |
| `frontend/src/lib/utils.ts` | Create | `cn()` helper |
| `frontend/src/components/ui/button.tsx` | Create | shadcn Button |
| `frontend/src/components/ui/input.tsx` | Create | shadcn Input |
| `frontend/src/components/ui/scroll-area.tsx` | Create | shadcn ScrollArea |
| `frontend/src/components/ui/tooltip.tsx` | Create | shadcn Tooltip |
| `frontend/src/App.tsx` | Modify | Header with icon buttons |
| `frontend/src/components/SessionSidebar.tsx` | Modify | ScrollArea + timestamps + active style |
| `frontend/src/components/ChatPanel.tsx` | Modify | Refined message bubbles + card |
| `frontend/src/components/InputBar.tsx` | Modify | shadcn Input + Button |

---

### Task 1: Install dependencies and configure path alias

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.app.json`

- [ ] **Step 1: Install npm packages**

```bash
cd frontend
npm install @radix-ui/react-scroll-area @radix-ui/react-tooltip @radix-ui/react-slot lucide-react class-variance-authority clsx tailwind-merge
```

Expected: packages added to `node_modules`, `package.json` updated.

- [ ] **Step 2: Add path alias to vite.config.ts**

Replace the full file content:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

- [ ] **Step 3: Add paths to tsconfig.app.json**

Add `baseUrl` and `paths` inside `compilerOptions`:

```json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "es2023",
    "lib": ["ES2023", "DOM"],
    "module": "esnext",
    "types": ["vite/client"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Verify dev server still starts**

```bash
cd frontend
npm run dev
```

Expected: Vite starts without errors on `http://localhost:5173`.

- [ ] **Step 5: Commit**

```bash
cd frontend
git add package.json package-lock.json vite.config.ts tsconfig.app.json
git commit -m "chore: add shadcn dependencies and path alias"
```

---

### Task 2: Add CSS design tokens

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Replace index.css with tokens + Tailwind import**

```css
@import "tailwindcss";

@theme {
  --color-background: hsl(210 20% 98%);
  --color-foreground: hsl(222.2 84% 4.9%);
  --color-card: hsl(0 0% 100%);
  --color-card-foreground: hsl(222.2 84% 4.9%);
  --color-primary: hsl(221.2 83.2% 53.3%);
  --color-primary-foreground: hsl(210 40% 98%);
  --color-muted: hsl(210 40% 96.1%);
  --color-muted-foreground: hsl(215.4 16.3% 46.9%);
  --color-border: hsl(214.3 31.8% 91.4%);
  --color-destructive: hsl(0 84.2% 60.2%);
  --color-destructive-foreground: hsl(210 40% 98%);
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
}

* {
  border-color: var(--color-border);
}

body {
  background-color: var(--color-background);
  color: var(--color-foreground);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 2: Verify page background changes**

Open `http://localhost:5173` — page background should now be a very light gray (not pure white).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "style: add shadcn CSS design tokens"
```

---

### Task 3: Create utility and shadcn UI primitives

**Files:**
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/components/ui/scroll-area.tsx`
- Create: `frontend/src/components/ui/tooltip.tsx`

- [ ] **Step 1: Create src/lib/utils.ts**

```ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 2: Create src/components/ui/button.tsx**

```tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-primary)] text-[var(--color-primary-foreground)] hover:bg-[var(--color-primary)]/90",
        ghost:
          "hover:bg-[var(--color-muted)] hover:text-[var(--color-foreground)]",
        outline:
          "border border-[var(--color-border)] bg-transparent hover:bg-[var(--color-muted)]",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
```

- [ ] **Step 3: Create src/components/ui/input.tsx**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-9 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-[var(--color-muted-foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
```

- [ ] **Step 4: Create src/components/ui/scroll-area.tsx**

```tsx
import * as React from "react";
import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area";
import { cn } from "@/lib/utils";

const ScrollArea = React.forwardRef<
  React.ElementRef<typeof ScrollAreaPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root>
>(({ className, children, ...props }, ref) => (
  <ScrollAreaPrimitive.Root
    ref={ref}
    className={cn("relative overflow-hidden", className)}
    {...props}
  >
    <ScrollAreaPrimitive.Viewport className="h-full w-full rounded-[inherit]">
      {children}
    </ScrollAreaPrimitive.Viewport>
    <ScrollBar />
    <ScrollAreaPrimitive.Corner />
  </ScrollAreaPrimitive.Root>
));
ScrollArea.displayName = ScrollAreaPrimitive.Root.displayName;

const ScrollBar = React.forwardRef<
  React.ElementRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>,
  React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>
>(({ className, orientation = "vertical", ...props }, ref) => (
  <ScrollAreaPrimitive.ScrollAreaScrollbar
    ref={ref}
    orientation={orientation}
    className={cn(
      "flex touch-none select-none transition-colors",
      orientation === "vertical" &&
        "h-full w-2.5 border-l border-l-transparent p-[1px]",
      orientation === "horizontal" &&
        "h-2.5 flex-col border-t border-t-transparent p-[1px]",
      className
    )}
    {...props}
  >
    <ScrollAreaPrimitive.ScrollAreaThumb className="relative flex-1 rounded-full bg-[var(--color-border)]" />
  </ScrollAreaPrimitive.ScrollAreaScrollbar>
));
ScrollBar.displayName = ScrollAreaPrimitive.ScrollAreaScrollbar.displayName;

export { ScrollArea, ScrollBar };
```

- [ ] **Step 5: Create src/components/ui/tooltip.tsx**

```tsx
import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 overflow-hidden rounded-md bg-[var(--color-foreground)] px-3 py-1.5 text-xs text-[var(--color-primary-foreground)] animate-in fade-in-0 zoom-in-95",
        className
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd frontend
npm run build 2>&1 | head -30
```

Expected: Build completes without type errors (or only pre-existing warnings).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/utils.ts frontend/src/components/ui/
git commit -m "feat: add shadcn UI primitives (Button, Input, ScrollArea, Tooltip)"
```

---

### Task 4: Restyle App.tsx header

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Replace App.tsx**

```tsx
import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { Settings, Moon } from "lucide-react";
import { SessionSidebar } from "./components/SessionSidebar";
import { ChatPanel } from "./components/ChatPanel";
import { InputBar } from "./components/InputBar";
import { useWebSocket } from "./hooks/useWebSocket";
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
                <Button variant="ghost" size="icon" aria-label="主题">
                  <Moon className="h-4 w-4 text-[var(--color-muted-foreground)]" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>切换主题（暂未实现）</TooltipContent>
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
            <ChatPanel messages={messages} />
            <InputBar onSend={sendMessage} disabled={isLoading} />
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
```

- [ ] **Step 2: Verify in browser**

Open `http://localhost:5173` — header should show a ⚡ icon, the title, and two icon buttons (Moon + Settings) on the right. Hovering each button shows a tooltip.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: restyle App header with icon buttons and tooltip"
```

---

### Task 5: Restyle SessionSidebar

**Files:**
- Modify: `frontend/src/components/SessionSidebar.tsx`

The `Session` type has `created_at: string` and `updated_at: string` (ISO strings from the API).

- [ ] **Step 1: Replace SessionSidebar.tsx**

```tsx
import type { Session } from "../types";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { Plus } from "lucide-react";

interface Props {
  sessions: Session[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
}

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const isToday =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();
  const hhmm = date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return isToday
    ? `今天 ${hhmm}`
    : date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" }) +
        " " +
        hhmm;
}

export function SessionSidebar({ sessions, activeId, onSelect, onNew }: Props) {
  return (
    <div className="w-60 border-r bg-[var(--color-card)] flex flex-col">
      <div className="p-3 border-b">
        <Button
          variant="outline"
          className="w-full justify-start gap-2 text-sm font-medium"
          onClick={onNew}
        >
          <Plus className="h-4 w-4" />
          新对话
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="py-1">
          {sessions.map((s) => (
            <button
              key={s.id}
              className={`w-full text-left px-3 py-2.5 text-sm cursor-pointer transition-colors border-l-2 ${
                s.id === activeId
                  ? "border-l-[var(--color-primary)] bg-[var(--color-primary)]/8 text-[var(--color-primary)]"
                  : "border-l-transparent hover:bg-[var(--color-muted)] text-[var(--color-foreground)]"
              }`}
              onClick={() => onSelect(s.id)}
            >
              <div className="truncate font-medium leading-snug">{s.title}</div>
              <div className="text-xs text-[var(--color-muted-foreground)] mt-0.5">
                {formatTime(s.updated_at)}
              </div>
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Sidebar should show a cleaner "新对话" button with a Plus icon, and each session item should show a timestamp below the title. The active session should have a left blue border.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SessionSidebar.tsx
git commit -m "feat: restyle SessionSidebar with ScrollArea and timestamps"
```

---

### Task 6: Restyle ChatPanel

**Files:**
- Modify: `frontend/src/components/ChatPanel.tsx`

- [ ] **Step 1: Replace ChatPanel.tsx**

```tsx
import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import { ChartRenderer } from "./ChartRenderer";
import { ProgressBar } from "./ProgressBar";

interface Props {
  messages: ChatMessage[];
}

export function ChatPanel({ messages }: Props) {
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
              <ChartRenderer render={msg.render!} content={msg.content} />
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

- [ ] **Step 2: Verify in browser**

Send a test message. User bubble should appear right-aligned with rounded corners, AI response should appear left-aligned with a bordered card. Result cards should have a visible shadow.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChatPanel.tsx
git commit -m "feat: restyle ChatPanel with refined bubbles and card results"
```

---

### Task 7: Restyle InputBar and ProgressBar

**Files:**
- Modify: `frontend/src/components/InputBar.tsx`
- Modify: `frontend/src/components/ProgressBar.tsx`

- [ ] **Step 1: Replace InputBar.tsx**

```tsx
import { useState, type KeyboardEvent } from "react";
import { SendHorizonal } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function InputBar({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");

  const handleSend = () => {
    if (!value.trim()) return;
    onSend(value.trim());
    setValue("");
  };

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex gap-2 px-5 py-4 border-t bg-[var(--color-card)] items-center">
      <div className="relative flex-1">
        <Input
          className="pr-16 h-10 text-sm"
          placeholder="输入分析问题，例如：分析昨天各出口线路的流量分布"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKey}
          disabled={disabled}
        />
        {!value && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[var(--color-muted-foreground)] pointer-events-none select-none">
            ⏎ 发送
          </span>
        )}
      </div>
      <Button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        size="icon"
        className="h-10 w-10 shrink-0"
      >
        <SendHorizonal className="h-4 w-4" />
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Replace ProgressBar.tsx**

```tsx
interface Props {
  content: string;
}

export function ProgressBar({ content }: Props) {
  return (
    <div className="flex items-center gap-2.5 text-sm text-[var(--color-muted-foreground)] py-1 px-1">
      <div className="animate-spin w-3.5 h-3.5 border-2 border-[var(--color-primary)] border-t-transparent rounded-full shrink-0" />
      <span>{content}</span>
    </div>
  );
}
```

- [ ] **Step 3: Verify in browser**

Input bar should show a send icon button. When the input is empty, a "⏎ 发送" hint should appear on the right side of the input. ProgressBar spinner should use the primary blue color.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/InputBar.tsx frontend/src/components/ProgressBar.tsx
git commit -m "feat: restyle InputBar and ProgressBar with shadcn components"
```

---

### Task 8: Final visual check and cleanup

**Files:**
- No new files

- [ ] **Step 1: Run TypeScript type check**

```bash
cd frontend
npm run build 2>&1
```

Expected: Build succeeds with no type errors.

- [ ] **Step 2: Check for unused imports**

```bash
cd frontend
npm run lint 2>&1
```

Expected: No lint errors. Fix any reported unused variables.

- [ ] **Step 3: Final browser walkthrough**

Open `http://localhost:5173` and verify:
1. Page background is light gray (not pure white)
2. Header shows ⚡ icon, title, Moon + Settings buttons with tooltips on hover
3. Sidebar has "新对话" button with Plus icon; session items show timestamps
4. Chat area has proper bubble alignment (user right, AI left)
5. Input bar shows "⏎ 发送" hint when empty; send button is an icon
6. No layout breaks or overlapping elements

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: final UI polish and cleanup"
```
