import { useState, useRef, useEffect } from "react";
import type { Session } from "../types";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { Plus, Pencil, Trash2, Check, X } from "lucide-react";

const API_BASE = "http://localhost:8000/api/v1";

interface Props {
  sessions: Session[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
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

interface SessionRowProps {
  session: Session;
  isActive: boolean;
  onSelect: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

function SessionRow({ session, isActive, onSelect, onDelete, onRename }: SessionRowProps) {
  const [hovered, setHovered] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(session.title);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
    };
  }, []);

  const handleRenameClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditing(true);
    setEditValue(session.title);
    setTimeout(() => inputRef.current?.select(), 0);
  };

  const submitRename = () => {
    const trimmed = editValue.trim();
    setEditing(false);
    if (!trimmed || trimmed === session.title) return;
    fetch(`${API_BASE}/sessions/${session.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: trimmed }),
    })
      .then((r) => {
        if (!r.ok) throw new Error("rename failed");
        onRename(session.id, trimmed);
      })
      .catch(() => {
        // revert shown title via parent state staying unchanged
      });
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDelete(true);
    confirmTimerRef.current = setTimeout(() => setConfirmDelete(false), 3000);
  };

  const handleConfirmDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
    fetch(`${API_BASE}/sessions/${session.id}`, { method: "DELETE" }).then((r) => {
      if (r.ok) onDelete(session.id);
    });
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
    setConfirmDelete(false);
  };

  return (
    <div
      className={`relative w-full text-left px-3 py-2.5 text-sm cursor-pointer transition-colors border-l-2 group ${
        isActive
          ? "border-l-[var(--color-primary)] bg-[var(--color-primary)]/8 text-[var(--color-primary)]"
          : "border-l-transparent hover:bg-[var(--color-muted)] text-[var(--color-foreground)]"
      }`}
      onClick={() => !editing && onSelect()}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => {
        setHovered(false);
        if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
        setConfirmDelete(false);
      }}
    >
      {editing ? (
        <input
          ref={inputRef}
          className="w-full bg-transparent border-b border-[var(--color-primary)] outline-none text-sm font-medium leading-snug"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submitRename();
            if (e.key === "Escape") setEditing(false);
          }}
          onBlur={submitRename}
          autoFocus
        />
      ) : (
        <div className="truncate font-medium leading-snug pr-12">{session.title}</div>
      )}
      <div className="text-xs text-[var(--color-muted-foreground)] mt-0.5">
        {formatTime(session.updated_at)}
      </div>

      {!editing && hovered && !confirmDelete && (
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-0.5">
          <button
            className="p-1 rounded hover:bg-[var(--color-accent)]/20"
            onClick={handleRenameClick}
            title="重命名"
          >
            <Pencil className="h-3.5 w-3.5 text-[var(--color-muted-foreground)]" />
          </button>
          <button
            className="p-1 rounded hover:bg-[var(--color-destructive)]/20"
            onClick={handleDeleteClick}
            title="删除"
          >
            <Trash2 className="h-3.5 w-3.5 text-[var(--color-muted-foreground)]" />
          </button>
        </div>
      )}

      {!editing && confirmDelete && (
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          <span className="text-xs text-[var(--color-destructive)]">确认删除?</span>
          <button
            className="p-1 rounded hover:bg-[var(--color-destructive)]/20"
            onClick={handleConfirmDelete}
            title="确认"
          >
            <Check className="h-3.5 w-3.5 text-[var(--color-destructive)]" />
          </button>
          <button
            className="p-1 rounded hover:bg-[var(--color-muted)]"
            onClick={handleCancelDelete}
            title="取消"
          >
            <X className="h-3.5 w-3.5 text-[var(--color-muted-foreground)]" />
          </button>
        </div>
      )}
    </div>
  );
}

export function SessionSidebar({ sessions, activeId, onSelect, onNew, onDelete, onRename }: Props) {
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
            <SessionRow
              key={s.id}
              session={s}
              isActive={s.id === activeId}
              onSelect={() => onSelect(s.id)}
              onDelete={onDelete}
              onRename={onRename}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
