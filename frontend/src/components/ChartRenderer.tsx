import ReactECharts from "echarts-for-react";

interface Props {
  render: "echarts" | "html" | "text";
  content: any;
  insight?: string;
}

export function ChartRenderer({ render, content, insight }: Props) {
  if (render === "echarts") {
    return (
      <div className="w-full">
        {insight && <p className="text-sm text-gray-600 mb-2">{insight}</p>}
        <ReactECharts option={content} style={{ height: 350 }} />
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
  return <p className="text-sm text-gray-700 whitespace-pre-wrap">{content}</p>;
}
