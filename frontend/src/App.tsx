import { useState, useEffect, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { Settings, Moon } from "lucide-react";
import { SessionSidebar } from "./components/SessionSidebar";
import { ChatPanel } from "./components/ChatPanel";
import { InputBar } from "./components/InputBar";
import { useWebSocket } from "./hooks/useWebSocket";
import { useSessionMessages } from "./hooks/useSessionMessages";
import { useTheme } from "./hooks/useTheme";
import { Button } from "./components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./components/ui/tooltip";
import type { Session } from "./types";

const API_BASE = "http://localhost:8000/api/v1";

export default function App() {
  const [sessionId, setSessionId] = useState(() => uuidv4());
  const [sessions, setSessions] = useState<Session[]>([]);
  const { theme, toggleTheme } = useTheme();

  const handleSessionTitle = useCallback((id: string, title: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, title } : s))
    );
  }, []);

  const { messages: liveMessages, isLoading, sendMessage } = useWebSocket(
    sessionId,
    handleSessionTitle,
  );

  const { historyMessages, historyError } = useSessionMessages(sessionId);

  const allMessages = [...historyMessages, ...liveMessages];

  useEffect(() => {
    fetch(`${API_BASE}/sessions`)
      .then((r) => r.json())
      .then(setSessions)
      .catch(() => {});
  }, []);

  const handleNew = () => {
    const id = uuidv4();
    setSessionId(id);
  };

  const handleSelect = (id: string) => {
    setSessionId(id);
  };

  const handleDeleteSession = (id: string) => {
    const remaining = sessions.filter((s) => s.id !== id);
    setSessions(remaining);
    if (id === sessionId) {
      setSessionId(remaining.length > 0 ? remaining[0].id : uuidv4());
    }
  };

  const handleRenameSession = (id: string, title: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, title } : s))
    );
  };

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
            onSelect={handleSelect}
            onNew={handleNew}
            onDelete={handleDeleteSession}
            onRename={handleRenameSession}
          />
          <div className="flex flex-col flex-1 overflow-hidden">
            {historyError && (
              <div className="px-4 py-2 text-sm text-[var(--color-destructive)] bg-[var(--color-destructive)]/10 border-b border-[var(--color-destructive)]/20">
                {historyError}
              </div>
            )}
            <ChatPanel
              messages={allMessages}
              onSend={sendMessage}
              sessionId={sessionId}
            />
            <InputBar onSend={sendMessage} disabled={isLoading} />
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
