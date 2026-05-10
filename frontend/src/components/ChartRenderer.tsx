import { useEffect, useRef, useState } from "react";
import type { RenderType } from "../types";

const API_BASE = "http://localhost:8000/api/v1";

interface Props {
  render: RenderType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any;
  sessionId?: string;
  msgId?: number;
}

export function ChartRenderer({ render, content, sessionId, msgId }: Props) {
  const [imgSrc, setImgSrc] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const placeholderRef = useRef<HTMLDivElement>(null);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (render !== "image-placeholder" || !sessionId || msgId === undefined) return;
    if (fetchedRef.current) return;

    const el = placeholderRef.current;
    if (!el) return;

    const controller = new AbortController();

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          fetchedRef.current = true;
          observer.disconnect();
          fetch(`${API_BASE}/sessions/${sessionId}/messages/${msgId}/image`, {
            signal: controller.signal,
          })
            .then((r) => {
              if (!r.ok) throw new Error("not found");
              return r.json();
            })
            .then((data) => setImgSrc(`data:image/png;base64,${data.image_data}`))
            .catch((err) => {
              if (err.name !== "AbortError") setLoadError(true);
            });
        }
      },
      { threshold: 0.1 },
    );
    observer.observe(el);
    return () => {
      observer.disconnect();
      controller.abort();
    };
  }, [render, sessionId, msgId]);

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

  if (render === "image-placeholder") {
    if (imgSrc) {
      return (
        <img
          src={imgSrc}
          alt="分析图表"
          className="w-full rounded"
          style={{ maxHeight: 600, objectFit: "contain" }}
        />
      );
    }
    if (loadError) {
      return (
        <div className="flex items-center justify-center h-40 rounded bg-[var(--color-muted)] text-sm text-[var(--color-muted-foreground)]">
          图表加载失败
        </div>
      );
    }
    return (
      <div
        ref={placeholderRef}
        className="w-full rounded bg-[var(--color-muted)] animate-pulse"
        style={{ height: 300 }}
      />
    );
  }

  return (
    <p className="text-sm text-[var(--color-foreground)] whitespace-pre-wrap">
      {content}
    </p>
  );
}
