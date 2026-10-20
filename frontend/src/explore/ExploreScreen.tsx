import { useEffect, useState } from "react";
import { useAnalysis } from "../app/useAnalysis";
import { download, type Analysis, type Command } from "../api/client";
import { PlotPanel } from "../plots/PlotPanel";
import { HelpButton } from "../components/HelpButton";
import { help } from "./help";
import { SignalTray } from "./SignalTray";
import { SignalEditor } from "./SignalEditor";
import { useSignalEditor } from "./useSignalEditor";
import { ViewingDepths, availableFrames } from "./ViewingDepths";
import { ROIControls } from "./ROIControls";
import { AnalysisSettings } from "./AnalysisSettings";
import { roiFromBounds, roiBounds, frameWindow, type ROI } from "./selection";
export function ExploreScreen({
  initial,
  active,
  onReplace,
}: {
  initial: Analysis;
  active: boolean;
  onReplace: (a: Analysis) => void;
}) {
  const {
    state: a,
    data,
    error,
    send,
    refresh,
    setError,
    pendingPanels,
    panelStates,
  } = useAnalysis(initial);
  const editor = useSignalEditor(a, refresh);
  const [max, setMax] = useState<string | null>(null),
    [details, setDetails] = useState<string>();
  const act = (c: Command) => void send(c).catch(() => {});
  const bounds = availableFrames(a);
  const frame = (value: number) =>
    act({
      type: "set_depth",
      depth: {
        mode: "frame",
        index: Math.min(bounds[1], Math.max(bounds[0], Math.round(value))),
      },
    });
  useEffect(() => {
    if (!active) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMax(null);
      if (
        (e.target as HTMLElement).closest(
          'input,select,textarea,button,[role="dialog"]',
        )
      )
        return;
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        frame(
          (a.depth.mode === "frame" ? a.depth.index : bounds[0]) +
            (e.key === "ArrowRight" ? 1 : -1),
        );
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [a.revision, active]);
  const selectedDepth =
    a.depth.mode === "frame"
      ? [a.depth.index, a.depth.index]
      : a.depth.mode === "window"
        ? [a.depth.first, a.depth.last]
        : undefined;
  const display = (patch: Partial<Analysis["display"]>) =>
    act({
      type: "set_display",
      ...a.display,
      ...patch,
      image: (patch.image ?? a.display.image) as "sims" | "se",
    });
  const panels = data?.panels;
  const d = editor.draft;
  const interval = d?.intervals[d.selectedInterval];
  const spectrumMode = d
    ? `${d.signalId ? "Editing" : "Creating"} ${d.name}`
    : "Viewing spectrum";
  const draftSelect = (values: number[]) => {
    if (d && !d.submittedJobId)
      editor.patchDraft({
        intervals: d.intervals.map((v, i) =>
          i === d.selectedInterval ? [String(values[0]), String(values[1])] : v,
        ),
      });
  };
  const common = (name: string) => ({
    name,
    maximized: max === name,
    onMaximize: () => setMax(max === name ? null : name),
    loading: pendingPanels.has(name),
  });
  const imageName =
    panels?.ion.signal_name ??
    a.signals.find((s) => s.id === a.image_signal_id)?.name ??
    "";
  const ionState = panelStates.ion ?? a;
  const ionFrames = panels?.ion.frame_range;
  return (
    <main className="explore-screen">
      <div className="analysis-heading">
        <div>
          <span className="eyebrow">Independent analysis</span>
          <h1>{a.dataset.relative_path.split("/").pop()}</h1>
          <span>
            {a.shape[0].toLocaleString()} frames · {a.shape[2]} × {a.shape[1]}{" "}
            pixels · {a.peaks.length} stored signals
          </span>
        </div>
        <div className="row">
          <small>
            Revision{" "}
            <output
              style={{ display: "inline" }}
              data-testid="analysis-revision"
            >
              {a.revision}
            </output>
          </small>
          <AnalysisSettings analysis={a} send={send} />
          <button onClick={() => onReplace(a)}>Replace file</button>
          <button
            onClick={() =>
              void download(a.id, "csv").catch((e) => setError(e.message))
            }
          >
            Profile CSV
          </button>
          <button
            onClick={() =>
              void download(a.id, "json").catch((e) => setError(e.message))
            }
          >
            Settings JSON
          </button>
          <HelpButton label="Exports" content={help.exports} />
        </div>
      </div>
      {error && (
        <div role="alert" className="error">
          {error}
          <button onClick={() => void refresh()}>Retry</button>
        </div>
      )}
      {editor.error && !d && (
        <div role="alert" className="error">
          {editor.error}
          <button onClick={editor.dismissError}>Dismiss</button>
        </div>
      )}
      <div className="signal-workspace">
        <SignalTray
          analysis={a}
          send={send}
          editor={editor}
          id={details}
          onDetails={setDetails}
        />
        <ViewingDepths analysis={a} send={send} />
        <div className="plot-grid">
          <PlotPanel
            {...common("ion")}
            title={ionState.display.image === "se" ? "SE Image" : "Ion map"}
            help={ionState.display.image === "se" ? help.se : help.ion}
            panel={panels?.ion}
            expectedKind="image"
            status={
              <span>
                {ionState.display.image === "se"
                  ? "Unregistered SE · native pixels"
                  : imageName}
                {ionFrames && ` · frames ${ionFrames[0]}–${ionFrames[1]}`}
                {pendingPanels.has("ion") ? " · Updating…" : ""}
              </span>
            }
            controls={
              <>
                <ROIControls analysis={a} send={send} />
                <label>
                  <input
                    type="checkbox"
                    checked={a.display.log}
                    onChange={(e) => display({ log: e.target.checked })}
                  />
                  Log colors
                </label>
                <label>
                  Image{" "}
                  <select
                    aria-label="Image"
                    value={a.display.image}
                    onChange={(e) => display({ image: e.target.value })}
                  >
                    <option value="sims">SIMS</option>
                    {a.has_se && <option value="se">SE (unregistered)</option>}
                  </select>
                </label>
              </>
            }
            mode="xy"
            selection={
              ionState.display.image === "sims"
                ? roiBounds(ionState.roi as ROI, a.shape, a.fov_um)
                : undefined
            }
            onSelect={(b) => {
              if (a.display.image === "sims")
                act({
                  type: "set_roi",
                  roi: roiFromBounds(b, a.shape, a.fov_um),
                });
            }}
          />
          <div
            className={`spectrum-workbench ${max === "spectrum" ? "maximized" : ""} ${d ? "has-editor" : ""}`}
          >
            <SignalEditor editor={editor} analysis={a} />
            <PlotPanel
              {...common("spectrum")}
              maximized={false}
              expanded={max === "spectrum"}
              title="Mass spectrum"
              help={help.spectrum}
              panel={panels?.spectrum}
              selectionMode={d ? "select" : "zoom"}
              selection={interval?.map(Number)}
              onSelect={draftSelect}
              zoomWindow={
                interval
                  ? (interval.map(Number) as [number, number])
                  : undefined
              }
              status={
                <span>
                  {spectrumMode}
                  {d?.submittedJobId ? " · calculating" : ""}
                </span>
              }
              controls={
                !d ? (
                  <button onClick={editor.openNew}>Create signal</button>
                ) : undefined
              }
            />
          </div>
          <PlotPanel
            {...common("front")}
            title="Front projection"
            help={help.front}
            panel={panels?.front}
            expectedKind="image"
            status={
              <span>
                {panels?.front.signal_name ?? ""}
                {pendingPanels.has("front") ? " · Updating…" : ""}
              </span>
            }
            selection={
              selectedDepth
                ? [0, a.fov_um ?? a.shape[2], ...selectedDepth]
                : undefined
            }
            mode="xy"
            onClick={(_, y) => frame(y)}
            onSelect={(b) => {
              const [first, last] = frameWindow(b.slice(2), bounds);
              act({
                type: "set_depth",
                depth: { mode: "window", first, last },
              });
            }}
          />
          <PlotPanel
            {...common("profile")}
            title="Depth profile"
            help={help.profile}
            panel={panels?.profile}
            status={
              pendingPanels.has("profile") ? <span>Updating…</span> : undefined
            }
            controls={
              <label>
                <input
                  type="checkbox"
                  checked={a.display.relative}
                  onChange={(e) => display({ relative: e.target.checked })}
                />
                Relative profiles
              </label>
            }
            legendActions={{
              imageSignalId:
                panelStates.profile?.image_signal_id ?? a.image_signal_id,
              onDetails: (id) => {
                setDetails(id);
                document
                  .querySelector(".signal-tray")
                  ?.scrollIntoView({ block: "nearest" });
              },
              onVisibility: (id, visible) =>
                act({ type: "set_profile_visible", signal_id: id, visible }),
            }}
            selection={selectedDepth}
            onClick={(x) => frame(x)}
            onSelect={(b) => {
              const [first, last] = frameWindow(b, bounds);
              act({
                type: "set_depth",
                depth: { mode: "window", first, last },
              });
            }}
            onAllDepths={() =>
              act({ type: "set_depth", depth: { mode: "all" } })
            }
          />
        </div>
        <p className="scope-note">
          Original-resolution values drive profiles and CSV exports. Color and
          relative scaling affect display only. Acquisition files are read only.
        </p>
      </div>
    </main>
  );
}
