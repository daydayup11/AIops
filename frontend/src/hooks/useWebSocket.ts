import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, WSMessage } from "../types";
import { v4 as uuidv4 } from "uuid";

const WS_URL = "ws://localhost:8000/api/v1/chat";
const PROGRESS_BUBBLE_ID = "__progress__";
const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 5;

export function useWebSocket(
  sessionId: string,
  onSessionTitle?: (id: string, title: string) => void,
) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onSessionTitleRef = useRef(onSessionTitle);

  useEffect(() => {
    onSessionTitleRef.current = onSessionTitle;
  });

  useEffect(() => {
    let cancelled = false;
    setMessages([]);
    setIsLoading(false);

    function connect() {
      if (cancelled) return;
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        if (cancelled) { ws.close(); return; }
        wsRef.current = ws;
        reconnectAttemptsRef.current = 0;
        setConnected(true);
      };

      ws.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        wsRef.current = null;
        // Auto-reconnect while a query is in-flight (isLoading may be stale here,
        // so we check attempt count independently)
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current += 1;
          reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      ws.onmessage = (event) => {
        if (cancelled) return;
        const msg: WSMessage = JSON.parse(event.data);

        if (msg.type === "session_title") {
          onSessionTitleRef.current?.(msg.session_id ?? "", msg.title ?? "");
          return;
        }

        if (msg.type === "done") {
          setMessages((prev) => prev.filter((m) => m.id !== PROGRESS_BUBBLE_ID));
          setIsLoading(false);
          reconnectAttemptsRef.current = MAX_RECONNECT_ATTEMPTS; // stop reconnecting after done
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
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onclose = null;
        wsRef.current.onmessage = null;
        wsRef.current.close();
      }
    };
  }, [sessionId]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      reconnectAttemptsRef.current = 0; // allow reconnects for this new query
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
