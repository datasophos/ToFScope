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
function PlotToolbarIcon({ action }: { action: "reset" | "save" }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {action === "reset" ? (
        <>
          <g strokeOpacity="0.4">
            <circle cx="10" cy="10" r="7.5" />
            <path d="m15.5 15.5 6 6" />
          </g>
          <path d="M6.5 9a3.6 3.6 0 1 1 .8 3.5M6.5 6v3h3" />
        </>
      ) : (
        <>
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="m3 17 6-6 4 4 3-3 5 5" />
        </>
      )}
    </svg>
  );
}

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
  markers,
  mode = "x",
  onAllDepths,
  zoomWindow,
  controls,
  status,
  legendActions,
  expanded = false,
  selectionMode = "select",
  spectrumLog,
  onSpectrumLogChange,
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
  markers?: number[];
  mode?: "x" | "xy";
  onAllDepths?: () => void;
  zoomWindow?: Range;
  controls?: ReactNode;
  status?: ReactNode;
  expanded?: boolean;
  selectionMode?: "select" | "zoom";
  spectrumLog?: boolean;
  onSpectrumLogChange?: (log: boolean) => void;
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
  useEffect(() => {
    if (spectrumLog !== undefined) setYScale(spectrumLog ? "log" : "linear");
  }, [spectrumLog]);
  const [exportError, setExportError] = useState<string | null>(null);
  const legend: LegendEntry[] =
    name === "profile" || name === "calibration"
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
  const coordinateKey = panel?.axes.map((a) => `${a.name}:${a.unit}`).join("/");
  useEffect(() => setZoom(null), [coordinateKey]);
  const xRange = zoom || range;
  let high = 1;
  for (const s of panel?.series || [])
    for (const v of s.values) if (v !== null) high = Math.max(high, v);
  if (panel?.relative) high = 1;
  const ya = panel?.axes[1],
    yRange: Range =
      ya && ya.boundaries.length
        ? [ya.boundaries[0], ya.boundaries.at(-1)!]
        : [0, high * 1.08];
  const data: ChartData | undefined = panel
    ? {
        kind: panel.kind,
        x: panel.axes[0].values,
        y: ya?.values,
        xBoundaries: panel.axes[0].boundaries,
        yBoundaries: ya?.boundaries,
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
              onClick={() => {
                const log = yScale !== "log";
                setYScale(log ? "log" : "linear");
                onSpectrumLogChange?.(log);
              }}
              aria-label={`Use ${yScale === "log" ? "linear" : "logarithmic"} y scale`}
              aria-pressed={yScale === "log"}
            >
              {yScale === "log" ? "Log y" : "Linear y"}
            </button>
          )}
          {zoomWindow && (
            <button onClick={() => setZoom(zoomWindow)}>Zoom to draft</button>
          )}
          <button
            className="plot-icon-button"
            onClick={() => setZoom(null)}
            aria-label="Reset zoom"
            title="Reset zoom"
          >
            <PlotToolbarIcon action="reset" />
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
            className="plot-icon-button"
            aria-label={`Export ${title} PNG`}
            title="Save plot/image as PNG"
          >
            <PlotToolbarIcon action="save" />
          </button>
          <button
            className="plot-icon-button"
            aria-label={`${maximized || expanded ? "Restore" : "Maximize"} ${title}`}
            title={`${maximized || expanded ? "Restore" : "Maximize"} ${title}`}
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
              markers={markers}
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
