import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { SessionSidebar } from "./components/SessionSidebar";
import { ChatPanel } from "./components/ChatPanel";
import { InputBar } from "./components/InputBar";
import { useWebSocket } from "./hooks/useWebSocket";
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
    <div className="flex flex-col h-screen bg-white">
      <header className="flex items-center justify-between px-6 py-3 border-b bg-white shadow-sm">
        <h1 className="text-lg font-semibold text-gray-800">校园网流量分析助手</h1>
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
  );
}
