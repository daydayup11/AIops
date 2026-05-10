import * as echarts from "echarts";

const techTheme = {
  color: ["#0088cc", "#0099dd", "#00aaee", "#4a7fa5", "#2a5f85", "#006699", "#005588"],
  backgroundColor: "transparent",
  textStyle: { color: "#4a7fa5" },
  title: { textStyle: { color: "#7eb8d4" } },
  legend: { textStyle: { color: "#4a7fa5" } },
  tooltip: {
    backgroundColor: "#0d1422",
    borderColor: "#1e3a5f",
    textStyle: { color: "#a0c4d8" },
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: "#1e3a5f" } },
    axisTick: { lineStyle: { color: "#1e3a5f" } },
    axisLabel: { color: "#2a5f85" },
    splitLine: { lineStyle: { color: "rgba(30,58,95,0.4)" } },
  },
  valueAxis: {
    axisLine: { lineStyle: { color: "#1e3a5f" } },
    axisTick: { lineStyle: { color: "#1e3a5f" } },
    axisLabel: { color: "#2a5f85" },
    splitLine: { lineStyle: { color: "rgba(30,58,95,0.4)" } },
  },
  line: { itemStyle: { borderWidth: 2 } },
  bar: { itemStyle: { borderRadius: [3, 3, 0, 0] } },
};

echarts.registerTheme("tech", techTheme);
