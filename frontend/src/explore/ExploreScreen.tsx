import { VolumeScreen } from "../volumes/VolumeScreen";
import { IdentifyDialog } from "../identification/IdentifyDialog";
import { IsotopeMeasurements } from "../identification/IsotopeMeasurements";
import { DepthEditor } from "../calibration/DepthEditor";
import {
  frameToCoordinate,
  coordinateToFrame,
} from "../calibration/coordinates";
import { useEffect, useState } from "react";
import { useAnalysis } from "../app/useAnalysis";
import { hasChanges } from "../app/changes";
import { download, type Analysis, type Command } from "../api/client";
import { PlotPanel } from "../plots/PlotPanel";
import { HelpButton } from "../components/HelpButton";
import { help } from "./help";
import { SaveCopy } from "./SaveCopy";
import { SignalTray } from "./SignalTray";
import { SignalEditor } from "./SignalEditor";
import { useSignalEditor } from "./useSignalEditor";
import { ViewingDepths, availableFrames } from "./ViewingDepths";
import { ROIControls } from "./ROIControls";
import { ImageDisplayControls } from "./ImageDisplayControls";
import { roiFromBounds, roiBounds, frameWindow, type ROI } from "./selection";
export function ExploreScreen({
  initial,
  active,
  onStatus,
  onSaved,
  onSaveDismiss,
  saveRequest = 0,
}: {
  initial: Analysis;
  active: boolean;
  onStatus: (a: Analysis, draft: boolean, busy: boolean) => void;
  onSaved: (a: Analysis) => void;
  onSaveDismiss: () => void;
  saveRequest?: number;
}) {
  const {
    state: a,
    data,
    error,
    send,
    refresh,
    setError,
    accept,
    pendingPanels,
    panelStates,
  } = useAnalysis(initial);
  const editor = useSignalEditor(a, refresh);
  const busy =
    editor.submitting ||
    a.signals.some(
      (row) =>
        row.job_id &&
        (!editor.jobs[row.job_id] ||
          ["queued", "running"].includes(editor.jobs[row.job_id].status)),
    );
  const blockedSave = editor.draft
    ? "Finish or discard the signal draft before saving."
    : busy
      ? "Finish or cancel calculations before saving."
      : "";
  useEffect(
    () => onStatus(a, !!editor.draft, busy),
    [a, !!editor.draft, busy, onStatus],
  );
  const [max, setMax] = useState<string | null>(null),
    [details, setDetails] = useState<string>();
  const act = (c: Command) => void send(c).catch(() => {});
  const bounds = availableFrames(a);
  const frame = (value: number) => {
    if (a.spatial.screen === "volume") return;
    act({
      type: "set_depth",
      depth: {
        mode: "frame",
        index: Math.min(bounds[1], Math.max(bounds[0], Math.round(value))),
      },
    });
  };
  useEffect(() => {
    if (active && a.spatial.screen === "volume" && a.depth.mode === "frame")
      act({ type: "set_depth", depth: { mode: "all" } });
  }, [active, a.spatial.screen, a.depth.mode]);
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
      if (
        a.spatial.screen !== "volume" &&
        (e.key === "ArrowLeft" || e.key === "ArrowRight")
      ) {
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
  const coordinate = (name: "profile" | "front", f: number) => {
    const p = panels?.[name];
    return p
      ? frameToCoordinate(
          f,
          p.axes[name === "front" ? 1 : 0],
          p.acquisition_frames ?? [],
        )
      : undefined;
  };
  const original = (name: "profile" | "front", v: number) => {
    const p = panels?.[name];
    return p
      ? coordinateToFrame(
          v,
          p.axes[name === "front" ? 1 : 0],
          p.acquisition_frames ?? [],
        )
      : undefined;
  };
  const depthSelection = (name: "profile" | "front") => {
    if (!selectedDepth) return undefined;
    const p = panels?.[name];
    if (!p?.acquisition_frames?.length) return undefined;
    const [lo, hi] = [p.acquisition_frames[0], p.acquisition_frames.at(-1)!];
    if (selectedDepth[1] < lo || selectedDepth[0] > hi) return undefined;
    return [
      coordinate(name, Math.max(lo, selectedDepth[0]))!,
      coordinate(name, Math.min(hi, selectedDepth[1]))!,
    ];
  };
  const coverage = (name: "profile" | "front") => {
    const p = panels?.[name];
    return p?.coordinate_kind === "depth"
      ? `${p.omitted_frames || 0} frame${p.omitted_frames === 1 ? "" : "s"} with unknown depth omitted${!p.acquisition_frames?.length ? " · No calibrated depth in acquisition" : ""}`
      : "";
  };
  const ionState = panelStates.ion ?? a;
  const ionFrames = panels?.ion.frame_range;
  return (
    <main
      className="explore-screen"
      data-testid="analysis"
      data-revision={a.revision}
    >
      <div className="analysis-heading">
        <div>
          <h1>{a.dataset.name || a.dataset.relative_path.split("/").pop()}</h1>
          <span>
            {a.shape[0].toLocaleString()} frames · {a.shape[2]} × {a.shape[1]}{" "}
            pixels · {a.peaks.length} stored signals
          </span>
        </div>
        <div
          className="analysis-view-tabs"
          role="tablist"
          aria-label="Analysis view"
          onKeyDown={(event) => {
            const names = ["explore", "volume"] as const;
            const index = names.indexOf(a.spatial.screen);
            const next =
              event.key === "ArrowRight"
                ? (index + 1) % 2
                : event.key === "ArrowLeft"
                  ? (index + 1) % 2
                  : event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? 1
                      : undefined;
            if (next === undefined) return;
            event.preventDefault();
            event.currentTarget
              .querySelectorAll<HTMLButtonElement>('[role="tab"]')
              [next].focus();
            act({
              type: "set_spatial",
              spatial: { ...a.spatial, screen: names[next] },
            });
          }}
        >
          {(["explore", "volume"] as const).map((screen) => (
            <button
              key={screen}
              role="tab"
              id={`${a.id}-${screen}-tab`}
              aria-selected={a.spatial.screen === screen}
              aria-controls={`${a.id}-view-panel`}
              tabIndex={a.spatial.screen === screen ? 0 : -1}
              onClick={() =>
                act({ type: "set_spatial", spatial: { ...a.spatial, screen } })
              }
            >
              {screen === "explore" ? "Explore" : "3D volume"}
            </button>
          ))}
        </div>
        <div className="row">
          <SaveCopy
            analysis={a}
            active={active}
            blocked={blockedSave}
            saveRequest={saveRequest}
            onSaved={(latest) => {
              accept(latest);
              onSaved(latest);
            }}
            onDismiss={onSaveDismiss}
          />
          <small data-testid="save-state">
            {editor.draft || hasChanges(a)
              ? "Unsaved changes"
              : a.saved_revision === a.revision
                ? "Saved"
                : "No changes"}
          </small>
          <HelpButton label="Saving" content={help.saving} />
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
      <div
        className="signal-workspace"
        role="tabpanel"
        id={`${a.id}-view-panel`}
        aria-labelledby={`${a.id}-${a.spatial.screen}-tab`}
      >
        <SignalTray
          active={active}
          analysis={a}
          send={send}
          editor={editor}
          id={details}
          onDetails={setDetails}
        />
        <ViewingDepths analysis={a} send={send}>
          <DepthEditor analysis={a} send={send} active={active} />
        </ViewingDepths>
        <div className={a.spatial.screen === "volume" ? "spatial-panels" : ""}>
          {a.spatial.screen === "volume" &&
            a.depth.mode !== "frame" &&
            active && <VolumeScreen analysis={a} send={send} />}
          {a.spatial.screen !== "volume" && (
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
                toolbarControls={
                  <>
                    <ROIControls analysis={a} send={send} />
                    <ImageDisplayControls analysis={a} display={display} />
                  </>
                }
                mode="xy"
                selection={
                  ionState.display.image === "sims"
                    ? roiBounds(a.roi as ROI, a.shape, a.fov_um)
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
                  spectrumLog={a.display.spectrum_log}
                  onSpectrumLogChange={(log) => display({ spectrum_log: log })}
                  maximized={false}
                  expanded={max === "spectrum"}
                  title="Mass spectrum"
                  help={help.spectrum}
                  panel={panels?.spectrum}
                  selectionMode={d ? "select" : "zoom"}
                  selection={interval?.map(Number)}
                  selectionWindows={d?.intervals.map(
                    ([low, high]) =>
                      [Number(low), Number(high)] as [number, number],
                  )}
                  selectedWindow={d?.selectedInterval}
                  onWindowSelect={(index) =>
                    editor.patchDraft({ selectedInterval: index })
                  }
                  onSelect={draftSelect}
                  zoomWindow={
                    interval
                      ? (interval.map(Number) as [number, number])
                      : undefined
                  }
                  headingControls={
                    <>
                      <span className="plot-status">
                        {spectrumMode}
                        {d?.submittedJobId ? " · calculating" : ""}
                      </span>
                      {!d && (
                        <>
                          <button onClick={editor.openNew}>
                            Create signal
                          </button>
                          <IdentifyDialog
                            analysis={a}
                            spectrum={panels?.spectrum}
                            send={send}
                            active={active}
                            onDraft={editor.openIdentified}
                            refresh={refresh}
                          />
                          <IsotopeMeasurements
                            analysis={a}
                            active={active}
                            refresh={refresh}
                          />
                        </>
                      )}
                    </>
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
                    {panels?.front.signal_name ?? ""} · {coverage("front")}
                    {pendingPanels.has("front") ? " · Updating…" : ""}
                  </span>
                }
                selection={
                  depthSelection("front")
                    ? [0, a.fov_um ?? a.shape[2], ...depthSelection("front")!]
                    : undefined
                }
                mode="y"
                onClick={(_, y) => {
                  const f = original("front", y);
                  if (f !== undefined) frame(f);
                }}
                onSelect={(b) => {
                  const v = b.slice(2).map((x) => original("front", x));
                  if (v.some((x) => x === undefined)) return;
                  const [first, last] = frameWindow(v as number[], bounds);
                  act({
                    type: "set_depth",
                    depth: { mode: "window", first, last },
                  });
                }}
              />
              <PlotPanel
                {...common("profile")}
                title="Depth profile"
                toolbarControls={
                  <button
                    className="plot-csv-button"
                    aria-label="Profile CSV"
                    title="Export depth profile CSV"
                    onClick={() =>
                      void download(a.id, "csv").catch((e) =>
                        setError(e.message),
                      )
                    }
                  >
                    CSV
                  </button>
                }
                help={help.profile}
                panel={panels?.profile}
                status={
                  coverage("profile") || pendingPanels.has("profile") ? (
                    <span>
                      {coverage("profile")}
                      {pendingPanels.has("profile") ? " · Updating…" : ""}
                    </span>
                  ) : undefined
                }
                headingControls={
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
                    act({
                      type: "set_profile_visible",
                      signal_id: id,
                      visible,
                    }),
                }}
                selection={depthSelection("profile")}
                onClick={(x) => {
                  const f = original("profile", x);
                  if (f !== undefined) frame(f);
                }}
                onSelect={(b) => {
                  const v = b.map((x) => original("profile", x));
                  if (v.some((x) => x === undefined)) return;
                  const [first, last] = frameWindow(v as number[], bounds);
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
          )}
        </div>
      </div>
    </main>
  );
}
