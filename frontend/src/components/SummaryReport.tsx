import type { SummaryReportData } from "../types";

interface Props {
  report: SummaryReportData;
}

export function SummaryReport({ report }: Props) {
  return (
    <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl px-5 py-4 shadow-sm">
      <h3 className="text-sm font-semibold text-[var(--color-foreground)] mb-3">📝 {report.title}</h3>
      {report.key_points.length > 0 && (
        <ul className="space-y-1 mb-3">
          {report.key_points.map((point, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-[var(--color-foreground)]">
              <span className="text-[var(--color-primary)] mt-0.5">•</span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-sm text-[var(--color-muted-foreground)] leading-relaxed border-t border-[var(--color-border)] pt-3">
        {report.conclusion}
      </p>
    </div>
  );
}
