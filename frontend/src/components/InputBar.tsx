import { useState, type KeyboardEvent } from "react";
import { SendHorizonal } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function InputBar({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");

  const handleSend = () => {
    if (!value.trim()) return;
    onSend(value.trim());
    setValue("");
  };

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex gap-2 px-5 py-4 border-t bg-[var(--color-card)] items-center">
      <div className="relative flex-1">
        <Input
          className="pr-16 h-10 text-sm"
          placeholder="输入分析问题，例如：分析昨天各出口线路的流量分布"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKey}
          disabled={disabled}
        />
        {!value && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[var(--color-muted-foreground)] pointer-events-none select-none">
            ⏎ 发送
          </span>
        )}
      </div>
      <Button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        size="icon"
        className="h-10 w-10 shrink-0"
      >
        <SendHorizonal className="h-4 w-4" />
      </Button>
    </div>
  );
}
