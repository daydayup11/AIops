import { useCallback, useEffect, useRef, useState } from "react";
import { ChatMessage, WSMessage } from "../types";
import { v4 as uuidv4 } from "uuid";

const WS_URL = "ws://localhost:8000/api/v1/chat";

export function useWebSocket(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);
      if (msg.type === "done") {
        setIsLoading(false);
        return;
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

    return () => ws.close();
  }, [sessionId]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      setIsLoading(true);
      setMessages((prev) => [
        ...prev,
        {
          id: uuidv4(),
          type: "user",
          content: text,
          timestamp: Date.now(),
        },
      ]);
      wsRef.current.send(
        JSON.stringify({ session_id: sessionId, message: text })
      );
    },
    [sessionId]
  );

  return { messages, connected, isLoading, sendMessage };
}
