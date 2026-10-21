import { imageRaster } from "./imageRaster";
import { curveStyle, type CurveStyle } from "./curveStyle";
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
  series?: ({
    label: string;
    values: (number | null)[];
  } & Partial<CurveStyle>)[];
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
  let rasterData: ChartData | undefined;
  let source: HTMLCanvasElement | undefined;
  const scaled = document.createElement("canvas");
  function update(d: ChartData) {
    if (
      d.kind === "image" &&
      (!source ||
        rasterData?.values !== d.values ||
        rasterData?.log !== d.log ||
        rasterData?.palette !== d.palette ||
        rasterData?.yReverse !== d.yReverse ||
        rasterData?.range?.[0] !== d.range?.[0] ||
        rasterData?.range?.[1] !== d.range?.[1])
    ) {
      source = imageRaster(d);
      rasterData = d;
    }
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
                color: s.color || curveStyle(i).color,
                type: s.dash || curveStyle(i).dash,
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
              // A single cached raster replaces one chart object per acquisition pixel.
              silent: true,
              clip: true,
              data: [0],
              renderItem: (
                params: {
                  coordSys?: {
                    x: number;
                    y: number;
                    width: number;
                    height: number;
                  };
                },
                api: { coord: (xy: number[]) => number[] },
              ) => {
                const grid = params.coordSys!;
                const dx = d.x.length > 1 ? d.x[1] - d.x[0] : 1;
                const dy = d.y!.length > 1 ? d.y![1] - d.y![0] : 1;
                const first = api.coord([d.x[0] - dx / 2, d.y![0] - dy / 2]);
                const last = api.coord([
                  d.x.at(-1)! + dx / 2,
                  d.y!.at(-1)! + dy / 2,
                ]);
                const left = Math.min(first[0], last[0]),
                  top = Math.min(first[1], last[1]);
                const fullWidth = Math.abs(last[0] - first[0]),
                  fullHeight = Math.abs(last[1] - first[1]);
                const x = Math.max(left, grid.x),
                  y = Math.max(top, grid.y);
                const width =
                  Math.min(left + fullWidth, grid.x + grid.width) - x;
                const height =
                  Math.min(top + fullHeight, grid.y + grid.height) - y;
                if (width <= 0 || height <= 0) return;
                // Crop before scaling so deep zooms cannot allocate an unbounded canvas.
                const ratio = window.devicePixelRatio || 1;
                scaled.width = Math.max(1, Math.round(width * ratio));
                scaled.height = Math.max(1, Math.round(height * ratio));
                const context = scaled.getContext("2d")!;
                context.imageSmoothingEnabled = false;
                context.drawImage(
                  source!,
                  ((x - left) / fullWidth) * source!.width,
                  ((y - top) / fullHeight) * source!.height,
                  (width / fullWidth) * source!.width,
                  (height / fullHeight) * source!.height,
                  0,
                  0,
                  scaled.width,
                  scaled.height,
                );
                return {
                  type: "image",
                  style: { image: scaled, x, y, width, height },
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
    resize: () => {
      const width = element.clientWidth,
        height = element.clientHeight;
      if (
        width > 0 &&
        height > 0 &&
        (chart.getWidth() !== width || chart.getHeight() !== height)
      )
        chart.resize();
    },
    destroy: () => chart.dispose(),
    exportImage: () =>
      chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" }),
  };
}
