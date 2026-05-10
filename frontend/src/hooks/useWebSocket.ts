import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, WSMessage } from "../types";
import { v4 as uuidv4 } from "uuid";

const WS_URL = "ws://localhost:8000/api/v1/chat";
const PROGRESS_BUBBLE_ID = "__progress__";

export function useWebSocket(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      if (cancelled) { ws.close(); return; }
      wsRef.current = ws;
      setConnected(true);
    };
    ws.onclose = () => {
      if (!cancelled) setConnected(false);
    };
    ws.onmessage = (event) => {
      if (cancelled) return;
      const msg: WSMessage = JSON.parse(event.data);

      if (msg.type === "done") {
        setMessages((prev) => prev.filter((m) => m.id !== PROGRESS_BUBBLE_ID));
        setIsLoading(false);
        return;
      }

      if (msg.type === "progress") {
        setMessages((prev) => {
          const exists = prev.some((m) => m.id === PROGRESS_BUBBLE_ID);
          const bubble: ChatMessage = {
            id: PROGRESS_BUBBLE_ID,
            type: "progress",
            content: msg.content,
            timestamp: Date.now(),
          };
          return exists
            ? prev.map((m) => (m.id === PROGRESS_BUBBLE_ID ? bubble : m))
            : [...prev, bubble];
        });
        return;
      }

      if (msg.type === "clarify") {
        setMessages((prev) => prev.filter((m) => m.id !== PROGRESS_BUBBLE_ID));
        setIsLoading(false);
        setMessages((prev) => [
          ...prev,
          {
            id: uuidv4(),
            type: "clarify",
            content: msg.question ?? msg.content,
            question: msg.question,
            options: msg.options ?? [],
            timestamp: Date.now(),
          },
        ]);
        return;
      }

      if (msg.type === "error") {
        setMessages((prev) => prev.filter((m) => m.id !== PROGRESS_BUBBLE_ID));
        setIsLoading(false);
      }

      setMessages((prev) => [
        ...prev,
        {
          id: uuidv4(),
          type: msg.type,
          content: msg.content,
          render: msg.render,
          timestamp: Date.now(),
        },
      ]);
    };

    return () => {
      cancelled = true;
      ws.onopen = null;
      ws.onclose = null;
      ws.onmessage = null;
      ws.close();
    };
  }, [sessionId]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      setIsLoading(true);
      setMessages((prev) =>
        prev.map((m) =>
          m.type === "clarify" ? { ...m, options: [] } : m
        )
      );
      setMessages((prev) => [
        ...prev,
        { id: uuidv4(), type: "user", content: text, timestamp: Date.now() },
      ]);
      wsRef.current.send(
        JSON.stringify({ session_id: sessionId, message: text })
      );
    },
    [sessionId]
  );

  return { messages, connected, isLoading, sendMessage };
}
