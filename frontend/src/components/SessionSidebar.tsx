import type { Session } from "../types";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { Plus } from "lucide-react";

interface Props {
  sessions: Session[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
}

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const isToday =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();
  const hhmm = date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return isToday
    ? `今天 ${hhmm}`
    : date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" }) +
        " " +
        hhmm;
}

export function SessionSidebar({ sessions, activeId, onSelect, onNew }: Props) {
  return (
    <div className="w-60 border-r bg-[var(--color-card)] flex flex-col">
      <div className="p-3 border-b">
        <Button
          variant="outline"
          className="w-full justify-start gap-2 text-sm font-medium"
          onClick={onNew}
        >
          <Plus className="h-4 w-4" />
          新对话
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="py-1">
          {sessions.map((s) => (
            <button
              key={s.id}
              className={`w-full text-left px-3 py-2.5 text-sm cursor-pointer transition-colors border-l-2 ${
                s.id === activeId
                  ? "border-l-[var(--color-primary)] bg-[var(--color-primary)]/8 text-[var(--color-primary)]"
                  : "border-l-transparent hover:bg-[var(--color-muted)] text-[var(--color-foreground)]"
              }`}
              onClick={() => onSelect(s.id)}
            >
              <div className="truncate font-medium leading-snug">{s.title}</div>
              <div className="text-xs text-[var(--color-muted-foreground)] mt-0.5">
                {formatTime(s.updated_at)}
              </div>
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
