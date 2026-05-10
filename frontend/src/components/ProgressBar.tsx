interface Props {
  content: string;
}

export function ProgressBar({ content }: Props) {
  return (
    <div className="flex items-center gap-2.5 text-sm text-[var(--color-muted-foreground)] py-1 px-1">
      <div className="animate-spin w-3.5 h-3.5 border-2 border-[var(--color-primary)] border-t-transparent rounded-full shrink-0" />
      <span>{content}</span>
    </div>
  );
}
