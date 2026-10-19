import { useEffect, useRef, useState } from "react";
import type { Panel } from "../api/client";
import {
  mountChart,
  type ChartHandle,
  type ChartData,
} from "./selectedRenderer";
import { SelectionOverlay, type Range } from "./SelectionOverlay";
import { HelpHeading } from "../components/HelpButton";
export function PlotPanel({
  name,
  title,
  help,
  panel,
  expectedKind,
  loading = false,
  maximized,
  onMaximize,
  onSelect,
  onClick,
  selection,
  mode = "x",
  onAllDepths,
  zoomWindow,
}: {
  name: string;
  title: string;
  help: string;
  panel?: Panel;
  expectedKind?: Panel["kind"];
  loading?: boolean;
  maximized: boolean;
  onMaximize: () => void;
  onSelect: (bounds: number[]) => void;
  onClick?: (x: number, y: number) => void;
  selection?: number[];
  mode?: "x" | "xy";
  onAllDepths?: () => void;
  zoomWindow?: Range;
}) {
  const body = useRef<HTMLDivElement>(null),
    element = useRef<HTMLDivElement>(null),
    chart = useRef<ChartHandle | null>(null);
  const [stageSize, setStageSize] = useState(0);
  const [zoom, setZoom] = useState<Range | null>(null);
  const [yScale, setYScale] = useState<"log" | "linear">("log");
  const axis = panel?.axes[0];
  const range: Range =
    axis && axis.boundaries.length
      ? [axis.boundaries[0], axis.boundaries.at(-1)!]
      : [0, 1];
  const xRange = zoom || range;
  let high = 1;
  for (const s of panel?.series || [])
    for (const v of s.values) if (v !== null) high = Math.max(high, v);
  if (panel?.relative) high = 1;
  const ya = panel?.axes[1],
    yRange: Range = ya
      ? [ya.boundaries[0], ya.boundaries.at(-1)!]
      : [0, high * 1.08];
  const data: ChartData | undefined = panel
    ? {
        kind: panel.kind,
        x: panel.axes[0].values,
        y: ya?.values,
        values: panel.values,
        series: panel.series,
        xRange,
        yRange,
        range: panel.intensity_range,
        palette: panel.palette,
        log: panel.log,
        yScale: name === "spectrum" ? yScale : undefined,
        relative: panel.relative,
        yReverse: panel.kind === "image",
      }
    : undefined;
  const image = panel?.kind === "image" || expectedKind === "image";
  const stageReady = !image || stageSize > 0;
  useEffect(() => {
    if (!element.current || !body.current) return;
    const observer = new ResizeObserver(() => {
      chart.current?.resize();
      if (image && body.current) {
        const { width, height } = body.current.getBoundingClientRect();
        const side = Math.floor(Math.min(width, height));
        setStageSize((current) => (current === side ? current : side));
      }
    });
    observer.observe(element.current);
    observer.observe(body.current);
    return () => {
      observer.disconnect();
      chart.current?.destroy();
      chart.current = null;
    };
  }, [image]);
  useEffect(() => {
    if (!data || !element.current || (data.kind === "image" && !stageSize))
      return;
    if (!chart.current) chart.current = mountChart(element.current, data);
    else chart.current.update(data);
  }, [panel?.content_version, zoom, stageSize, yScale]);
  return (
    <section
      className={`plot-panel ${maximized ? "maximized" : ""}`}
      data-testid={`panel-${name}`}
      data-kind={panel?.kind}
      data-content-version={panel?.content_version}
      data-y-scale={name === "spectrum" ? yScale : undefined}
    >
      <header>
        <HelpHeading title={title} content={help} />
        <div className="row">
          {onAllDepths && <button onClick={onAllDepths}>All depths</button>}
          {name === "spectrum" && (
            <button
              onClick={() =>
                setYScale((scale) => (scale === "log" ? "linear" : "log"))
              }
              aria-label={`Use ${yScale === "log" ? "linear" : "logarithmic"} y scale`}
              aria-pressed={yScale === "log"}
            >
              {yScale === "log" ? "Log y" : "Linear y"}
            </button>
          )}
          {zoomWindow && (
            <button onClick={() => setZoom(zoomWindow)}>Zoom to draft</button>
          )}
          <button onClick={() => setZoom(null)} title="Reset horizontal zoom">
            Reset zoom
          </button>
          <button
            onClick={() => {
              const href = chart.current?.exportImage();
              if (href) {
                const a = document.createElement("a");
                a.href = href;
                a.download = `tofscope-${name}.png`;
                a.click();
              }
            }}
            aria-label={`Export ${title} PNG`}
          >
            PNG
          </button>
          <button
            aria-label={`${maximized ? "Restore" : "Maximize"} ${title}`}
            onClick={onMaximize}
          >
            {maximized ? "↙" : "↗"}
          </button>
        </div>
      </header>
      <div className="plot-body" ref={body}>
        {image && (loading || !stageReady) && (
          <div
            className="plot-loading"
            role="status"
            aria-label="Loading image plot"
          >
            <span className="plot-spinner" aria-hidden="true" />
            <span>Loading image…</span>
          </div>
        )}
        <div
          className={`plot-stage ${image ? "image" : ""}`}
          data-testid={`plot-stage-${name}`}
          data-stage-ready={stageReady ? "true" : "false"}
          style={
            image && stageSize
              ? { width: stageSize, height: stageSize }
              : undefined
          }
        >
          <div className="chart" ref={element} />
          {panel && (
            <SelectionOverlay
              label={`${title} selection`}
              xRange={xRange}
              yRange={yRange}
              reverseY={image}
              selection={selection}
              onSelect={onSelect}
              onClick={onClick}
              onZoom={setZoom}
              mode={mode}
              image={image}
            />
          )}
        </div>
      </div>
      <footer>
        {axis?.name} · {axis?.unit}
        {ya
          ? ` / ${ya.name} · ${ya.unit}`
          : ` / ${panel?.relative ? "relative intensity" : panel?.units || "intensity"}`}
      </footer>
    </section>
  );
}
