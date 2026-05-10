interface VizBlueprintItem {
  task_id: string;
  chart_type: string;
  title: string;
  x_field: string;
  y_field: string;
  insight_hint: string;
}

const CHART_ICON: Record<string, string> = {
  bar: "📊",
  line: "📈",
  pie: "🥧",
  scatter: "✦",
  heatmap: "🗺",
};

interface Props {
  items: VizBlueprintItem[];
}

export function PlanCard({ items }: Props) {
  return (
    <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl px-4 py-3 shadow-sm max-w-lg">
      <p className="text-xs text-[var(--color-muted-foreground)] mb-2 font-medium">📋 分析规划</p>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item.task_id} className="flex items-center gap-2 text-sm text-[var(--color-foreground)]">
            <span>{CHART_ICON[item.chart_type] ?? "📉"}</span>
            <span className="font-medium">{item.title}</span>
            <span className="text-xs text-[var(--color-muted-foreground)]">({item.chart_type})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
