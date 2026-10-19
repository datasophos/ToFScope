import * as echarts from "echarts/core";
import { LineChart, CustomChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
echarts.use([
  LineChart,
  CustomChart,
  GridComponent,
  TooltipComponent,
  CanvasRenderer,
]);
export type ChartData = {
  kind: "line" | "image";
  yReverse?: boolean;
  x: number[];
  y?: number[];
  values?: (number | null)[][];
  series?: { label: string; values: (number | null)[] }[];
  xRange: [number, number];
  yRange: [number, number];
  palette?: "ion" | "gray";
  log?: boolean;
  yScale?: "log" | "linear";
  relative?: boolean;
  range?: [number, number];
};
export type ChartHandle = {
  update: (data: ChartData) => void;
  resize: () => void;
  destroy: () => void;
  exportImage: () => string;
};
export function mountChart(element: HTMLElement, data: ChartData): ChartHandle {
  const chart = echarts.init(element, undefined, { renderer: "canvas" });
  function update(d: ChartData) {
    const [min, max] = d.range || [0, 1],
      transform = (v: number) => (d.log ? Math.log1p(Math.max(0, v)) : v),
      lo = transform(min),
      hi = transform(max);
    const positiveValues = (d.series || []).flatMap((s) =>
      s.values.filter((v): v is number => v !== null && v > 0),
    );
    const series =
      d.kind === "line"
        ? (d.series || []).map((s, i) => {
            let scale = 1;
            if (d.relative) {
              scale = 1e-30;
              for (const v of s.values)
                if (v !== null) scale = Math.max(scale, v);
            }
            return {
              type: "line" as const,
              name: s.label,
              showSymbol: s.values.filter((v) => v !== null).length === 1,
              symbolSize: 6,
              connectNulls: false,
              lineStyle: {
                width: 1.5,
                color: ["#167d9a", "#b05e20", "#8560b4", "#337c45"][i % 4],
              },
              data: d.x.map((x, j) => {
                const value = s.values[j];
                return [
                  x,
                  value === null || (d.yScale === "log" && value <= 0)
                    ? null
                    : value / scale,
                ];
              }),
            };
          })
        : [
            {
              type: "custom",
              progressive: 0,
              encode: { x: 0, y: 1, tooltip: [0, 1, 2] },
              dimensions: ["x", "y", "intensity"],
              data: d.values!.flatMap((row, j) =>
                row.map((v, i) => [d.x[i], d.y![j], v]),
              ),
              renderItem: (
                _params: unknown,
                api: {
                  value: (i: number) => number;
                  coord: (xy: number[]) => number[];
                  size: (xy: number[]) => number[];
                },
              ) => {
                const v = api.value(2);
                if (!Number.isFinite(v)) return;
                const point = api.coord([api.value(0), api.value(1)]),
                  dx = d.x.length > 1 ? d.x[1] - d.x[0] : 1,
                  dy = d.y!.length > 1 ? d.y![1] - d.y![0] : 1,
                  size = api.size([dx, dy]),
                  t = Math.max(
                    0,
                    Math.min(1, (transform(v) - lo) / (hi - lo || 1)),
                  );
                return {
                  type: "rect",
                  shape: {
                    x: point[0] - Math.abs(size[0]) / 2,
                    y: point[1] - Math.abs(size[1]) / 2,
                    width: Math.abs(size[0]) + 0.5,
                    height: Math.abs(size[1]) + 0.5,
                  },
                  style: {
                    fill:
                      d.palette === "gray"
                        ? `rgb(${Math.round(255 * t)},${Math.round(255 * t)},${Math.round(255 * t)})`
                        : `rgb(${Math.round(25 + 220 * t)},${Math.round(30 + 190 * t)},${Math.round(90 - 50 * t)})`,
                  },
                };
              },
            },
          ];
    chart.setOption(
      {
        animation: false,
        grid:
          d.kind === "image"
            ? { left: 40, right: 40, top: 40, bottom: 40 }
            : { left: 60, right: 20, top: 20, bottom: 40 },
        tooltip: { trigger: "item", renderMode: "richText" },
        xAxis: {
          type: "value",
          min: d.xRange[0],
          max: d.xRange[1],
          axisLabel: { fontSize: 10 },
        },
        yAxis: {
          type: d.kind === "line" && d.yScale === "log" ? "log" : "value",
          inverse: !!d.yReverse,
          min:
            d.kind === "line" && d.yScale === "log"
              ? Math.min(...positiveValues, d.yRange[1])
              : d.yRange[0],
          max: d.yRange[1],
          axisLabel: { fontSize: 10 },
        },
        series,
      },
      true,
    );
  }
  update(data);
  return {
    update,
    resize: () => chart.resize(),
    destroy: () => chart.dispose(),
    exportImage: () =>
      chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" }),
  };
}
