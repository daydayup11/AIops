export type MessageType = "clarify" | "progress" | "result" | "plan" | "summary" | "error" | "done" | "user" | "session_title";
export type RenderType = "image" | "text" | "image-placeholder";

export interface WSMessage {
  type: MessageType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content?: any;
  render?: RenderType;
  elapsed?: number;
  question?: string;
  options?: string[];
  allow_free_input?: boolean;
}

export interface ChatMessage {
  id: string;
  type: MessageType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any;
  render?: RenderType;
  timestamp: number;
  question?: string;
  options?: string[];
  msg_id?: number;  // for history image lazy-loading
}

export interface SummaryReportData {
  title: string;
  key_points: string[];
  conclusion: string;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}
