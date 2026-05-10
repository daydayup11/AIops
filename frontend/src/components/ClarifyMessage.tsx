interface Props {
  question: string;
  options: string[];
  onSelect: (text: string) => void;
}

export function ClarifyMessage({ question, options, onSelect }: Props) {
  return (
    <div className="flex justify-start">
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-2xl rounded-bl-sm px-4 py-3 max-w-lg shadow-sm">
        <p className="text-sm text-[var(--color-foreground)] leading-relaxed mb-2">{question}</p>
        {options.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {options.map((opt) => (
              <button
                key={opt}
                onClick={() => onSelect(opt)}
                className="text-xs px-3 py-1.5 rounded-full border border-[var(--color-primary)] text-[var(--color-primary)] hover:bg-[var(--color-primary)] hover:text-[var(--color-primary-foreground)] transition-colors"
              >
                {opt}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
