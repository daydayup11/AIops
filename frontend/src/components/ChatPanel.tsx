import type { ChatMessage } from "../types";
import { ChartRenderer } from "./ChartRenderer";
import { ProgressBar } from "./ProgressBar";

interface Props {
  messages: ChatMessage[];
}

export function ChatPanel({ messages }: Props) {
  return (
    <div className="flex flex-col gap-3 p-4 overflow-y-auto flex-1">
      {messages.map((msg) => {
        if (msg.type === "user") {
          return (
            <div
              key={msg.id}
              className="self-end bg-blue-500 text-white rounded-lg px-4 py-2 max-w-lg"
            >
              {msg.content}
            </div>
          );
        }
        if (msg.type === "progress") {
          return <ProgressBar key={msg.id} content={msg.content} />;
        }
        if (msg.type === "clarify") {
          return (
            <div
              key={msg.id}
              className="self-start bg-gray-100 rounded-lg px-4 py-2 max-w-lg text-gray-800"
            >
              {msg.content}
            </div>
          );
        }
        if (msg.type === "result") {
          return (
            <div
              key={msg.id}
              className="w-full bg-white border rounded-lg p-4 shadow-sm"
            >
              <ChartRenderer render={msg.render!} content={msg.content} />
            </div>
          );
        }
        if (msg.type === "error") {
          return (
            <div
              key={msg.id}
              className="text-red-500 text-sm px-4 py-2 bg-red-50 rounded"
            >
              {msg.content}
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}
