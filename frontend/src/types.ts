export type MessageType = "clarify" | "progress" | "result" | "error" | "done" | "user";
export type RenderType = "echarts" | "html" | "table" | "text";

export interface WSMessage {
  type: MessageType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any;
  render?: RenderType;
  elapsed?: number;
}

export interface ChatMessage {
  id: string;
  type: MessageType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any;
  render?: RenderType;
  timestamp: number;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}
