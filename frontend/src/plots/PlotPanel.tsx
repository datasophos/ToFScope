import { useEffect, useRef, useState } from "react";
import type { Panel } from "../api/client";
import {
  mountChart,
  type ChartHandle,
  type ChartData,
} from "./selectedRenderer";
import { SelectionOverlay, type Range } from "./SelectionOverlay";
export function PlotPanel({
  name,
  title,
  panel,
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
  panel?: Panel;
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
        relative: panel.relative,
        yReverse: panel.kind === "image",
      }
    : undefined;
  useEffect(() => {
    if (!element.current || !body.current) return;
    const observer = new ResizeObserver(() => {
      chart.current?.resize();
      if (panel?.kind === "image" && body.current) {
        const { width, height } = body.current.getBoundingClientRect();
        const side = Math.floor(Math.min(width, height));
        setStageSize((current) => current === side ? current : side);
      }
    });
    observer.observe(element.current);
    observer.observe(body.current);
    return () => {
      observer.disconnect();
      chart.current?.destroy();
      chart.current = null;
    };
  }, [panel?.kind]);
  useEffect(() => {
    if (!data || !element.current) return;
    if (!chart.current) chart.current = mountChart(element.current, data);
    else chart.current.update(data);
  }, [panel?.content_version, zoom]);
  return (
    <section
      className={`plot-panel ${maximized ? "maximized" : ""}`}
      data-testid={`panel-${name}`}
      data-content-version={panel?.content_version}
    >
      <header>
        <div>
          <h2>{title}</h2>
          <small>{panel?.aggregation || "Preparing data…"}</small>
        </div>
        <div className="row">
          {onAllDepths && <button onClick={onAllDepths}>All depths</button>}
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
        <div
          className={`plot-stage ${panel?.kind === "image" ? "image" : ""}`}
          data-testid={`plot-stage-${name}`}
          style={
            panel?.kind === "image" && stageSize
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
            reverseY={panel.kind === "image"}
            selection={selection}
            onSelect={onSelect}
            onClick={onClick}
            onZoom={setZoom}
            mode={mode}
          image={panel.kind === "image"}
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
