import ReactECharts from "echarts-for-react";
import "../lib/echartsTheme";
import type { Theme } from "../hooks/useTheme";

interface Props {
  render: "echarts" | "html" | "table" | "text";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any;
  insight?: string;
  theme?: Theme;
}

export function ChartRenderer({ render, content, insight, theme }: Props) {
  if (render === "echarts") {
    return (
      <div className="w-full">
        {insight && (
          <p className="text-sm text-[var(--color-muted-foreground)] mb-2">
            {insight}
          </p>
        )}
        <ReactECharts
          key={theme}
          option={content}
          theme={theme === "tech" ? "tech" : undefined}
          style={{ height: 350 }}
        />
      </div>
    );
  }
  if (render === "html") {
    return (
      <iframe
        srcDoc={content}
        className="w-full border rounded"
        style={{ height: 500 }}
        sandbox="allow-scripts"
      />
    );
  }
  return (
    <p className="text-sm text-[var(--color-foreground)] whitespace-pre-wrap">
      {content}
    </p>
  );
}
