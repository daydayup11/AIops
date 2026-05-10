import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import type { ChatMessage } from "../types";

const API_BASE = "http://localhost:8000/api/v1";

interface HistoryRow {
  id: number;
  session_id: string;
  role: string;
  type: string;
  content: string;
  created_at: string;
}

function rowToChatMessage(row: HistoryRow): ChatMessage {
  const base: ChatMessage = {
    id: uuidv4(),
    msg_id: row.id,
    type: row.type === "image" ? "result" : (row.type as ChatMessage["type"]),
    content: row.content,
    timestamp: new Date(row.created_at).getTime(),
  };

  if (row.type === "image") {
    return { ...base, render: "image-placeholder" };
  }
  if (row.role === "user") {
    return { ...base, type: "user" };
  }
  return base;
}

export function useSessionMessages(sessionId: string) {
  const [historyMessages, setHistoryMessages] = useState<ChatMessage[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    setIsLoadingHistory(true);
    setHistoryError(null);
    setHistoryMessages([]);

    fetch(`${API_BASE}/sessions/${sessionId}/messages`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<HistoryRow[]>;
      })
      .then((rows) => setHistoryMessages(rows.map(rowToChatMessage)))
      .catch(() => setHistoryError("历史记录加载失败，请刷新重试"))
      .finally(() => setIsLoadingHistory(false));
  }, [sessionId]);

  return { historyMessages, isLoadingHistory, historyError };
}
