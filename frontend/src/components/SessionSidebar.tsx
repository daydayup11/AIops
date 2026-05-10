import type { Session } from "../types";

interface Props {
  sessions: Session[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export function SessionSidebar({ sessions, activeId, onSelect, onNew }: Props) {
  return (
    <div className="w-56 border-r bg-gray-50 flex flex-col">
      <div className="p-3 border-b">
        <button
          className="w-full bg-blue-500 hover:bg-blue-600 text-white text-sm py-2 rounded-lg"
          onClick={onNew}
        >
          + 新对话
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 truncate ${
              s.id === activeId
                ? "bg-blue-50 text-blue-600 font-medium"
                : "text-gray-700"
            }`}
            onClick={() => onSelect(s.id)}
          >
            {s.title}
          </div>
        ))}
      </div>
    </div>
  );
}
