interface Props {
  render: "image" | "text";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any;
}

export function ChartRenderer({ render, content }: Props) {
  if (render === "image") {
    return (
      <img
        src={`data:image/png;base64,${content}`}
        alt="分析图表"
        className="w-full rounded"
        style={{ maxHeight: 600, objectFit: "contain" }}
      />
    );
  }
  return (
    <p className="text-sm text-[var(--color-foreground)] whitespace-pre-wrap">
      {content}
    </p>
  );
}
