import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import type { Theme } from "../hooks/useTheme";
import { ChartRenderer } from "./ChartRenderer";
import { ProgressBar } from "./ProgressBar";

interface Props {
  messages: ChatMessage[];
  theme?: Theme;
}

export function ChatPanel({ messages, theme }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col gap-4 p-5 overflow-y-auto flex-1 bg-[var(--color-background)]">
      {messages.map((msg) => {
        if (msg.type === "user") {
          return (
            <div key={msg.id} className="flex justify-end">
              <div className="bg-[var(--color-primary)] text-[var(--color-primary-foreground)] rounded-2xl rounded-br-sm px-4 py-2.5 max-w-lg text-sm leading-relaxed shadow-sm">
                {msg.content}
              </div>
            </div>
          );
        }
        if (msg.type === "progress") {
          return <ProgressBar key={msg.id} content={msg.content} />;
        }
        if (msg.type === "clarify") {
          return (
            <div key={msg.id} className="flex justify-start">
              <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-2xl rounded-bl-sm px-4 py-2.5 max-w-lg text-sm text-[var(--color-foreground)] leading-relaxed shadow-sm">
                {msg.content}
              </div>
            </div>
          );
        }
        if (msg.type === "result") {
          return (
            <div
              key={msg.id}
              className="w-full bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5 shadow-md"
            >
              <ChartRenderer
                render={msg.render!}
                content={msg.content}
                theme={theme}
              />
            </div>
          );
        }
        if (msg.type === "error") {
          return (
            <div
              key={msg.id}
              className="text-[var(--color-destructive)] text-sm px-4 py-2.5 bg-[var(--color-destructive)]/10 border border-[var(--color-destructive)]/20 rounded-lg"
            >
              {msg.content}
            </div>
          );
        }
        return null;
      })}
      <div ref={bottomRef} />
    </div>
  );
}
