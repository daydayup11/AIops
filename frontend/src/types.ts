export type MessageType = "clarify" | "progress" | "result" | "plan" | "summary" | "error" | "done" | "user";
export type RenderType = "echarts" | "html" | "table" | "text";

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
}

export interface VizBlueprintItem {
  task_id: string;
  chart_type: string;
  title: string;
  x_field: string;
  y_field: string;
  insight_hint: string;
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
