import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Panel } from "../api/client";
import {
  mountChart,
  type ChartHandle,
  type ChartData,
} from "./selectedRenderer";
import { SelectionOverlay, type Range } from "./SelectionOverlay";
import { HelpHeading } from "../components/HelpButton";
import { CurveMarker } from "../components/CurveMarker";
import {
  curveStyle,
  imageWithLegend,
  type CurveStyle,
  type LegendEntry,
} from "./curveStyle";
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
  controls,
  status,
  legendActions,
  expanded = false,
  selectionMode = "select",
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
  controls?: ReactNode;
  status?: ReactNode;
  expanded?: boolean;
  selectionMode?: "select" | "zoom";
  legendActions?: {
    imageSignalId: string;
    onDetails: (id: string) => void;
    onVisibility: (id: string, visible: boolean) => void;
  };
}) {
  const body = useRef<HTMLDivElement>(null),
    element = useRef<HTMLDivElement>(null),
    chart = useRef<ChartHandle | null>(null);
  const [stageSize, setStageSize] = useState(0);
  const [zoom, setZoom] = useState<Range | null>(null);
  const [yScale, setYScale] = useState<"log" | "linear">("log");
  const [exportError, setExportError] = useState<string | null>(null);
  const legend: LegendEntry[] =
    name === "profile"
      ? (panel?.series || []).map((series, index) => ({
          id: series.signal_id,
          label: series.label,
          ...curveStyle(series.style_index),
        }))
      : [];
  const series = legend.length
    ? panel!.series!.map((series, index) => ({ ...series, ...legend[index] }))
    : panel?.series;
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
        series,
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
            onClick={async () => {
              setExportError(null);
              try {
                const href = chart.current?.exportImage();
                if (href) {
                  const a = document.createElement("a");
                  a.href = legend.length
                    ? await imageWithLegend(href, legend)
                    : href;
                  a.download = `tofscope-${name}.png`;
                  a.click();
                }
              } catch {
                setExportError("PNG export failed. Please try again.");
              }
            }}
            aria-label={`Export ${title} PNG`}
          >
            PNG
          </button>
          <button
            aria-label={`${maximized || expanded ? "Restore" : "Maximize"} ${title}`}
            onClick={onMaximize}
          >
            {maximized || expanded ? "↙" : "↗"}
          </button>
        </div>
      </header>
      {(status || controls) && (
        <div className="plot-context">
          {status && <div className="plot-status">{status}</div>}
          {controls && <div className="plot-controls">{controls}</div>}
        </div>
      )}
      {legend.length > 0 && (
        <ul className="profile-legend" aria-label="Depth profile legend">
          {legend.map((entry) => (
            <li key={entry.id} data-curve-id={entry.id}>
              <CurveMarker style={entry} />
              {legendActions ? (
                <>
                  <button
                    className="text-button"
                    onClick={() => legendActions.onDetails(entry.id)}
                  >
                    {entry.label}
                    {entry.id === legendActions.imageSignalId
                      ? " · Images"
                      : ""}
                  </button>
                  {entry.id !== legendActions.imageSignalId && (
                    <button
                      aria-label={`Hide ${entry.label}`}
                      onClick={() =>
                        legendActions.onVisibility(entry.id, false)
                      }
                    >
                      ×
                    </button>
                  )}
                </>
              ) : (
                <span>{entry.label}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {exportError && <p role="alert">{exportError}</p>}
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
              selectionMode={selectionMode}
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
