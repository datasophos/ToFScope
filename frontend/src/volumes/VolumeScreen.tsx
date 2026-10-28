import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { canRenderVtkStyles, prepareVtkPreview } from "./vtkPreview";
import { vtkDisplayExtent, vtkSamplingLimited } from "./vtkGeometry";
const VtkScene = lazy(() =>
  import("./VtkScene").then((m) => ({ default: m.VtkScene })),
);
import { request, type Analysis, type Command } from "../api/client";
import { LayerEditor } from "./LayerEditor";
import {
  enabledLayers,
  defaultCamera,
  defaultLayer,
  type VolumeData,
  type SpatialView,
  type Camera,
} from "./spatialRenderer";
function VolumePlaceholder() {
  return (
    <div
      className="volume-canvas volume-loading"
      role="status"
      aria-label="Preparing 3D preview"
    >
      <span className="volume-loading-spinner" aria-hidden="true" />
      <span>Preparing 3D preview…</span>
    </div>
  );
}
function VtkTile({
  source,
  single,
  preview,
  points,
  view,
  log,
  onCamera,
  onError,
}: {
  source: VolumeData;
  single: VolumeData;
  preview: ReturnType<typeof prepareVtkPreview>;
  points: boolean;
  view: SpatialView;
  log: boolean;
  onCamera: (id: string, c: Camera) => void;
  onError: (message: string) => void;
}) {
  const style = view.layers.find(
    (l) => l.signal_id === single.layers[0].signal_id,
  )!;
  const tileView = {
    ...view,
    camera: view.linked ? view.camera : style.camera,
  };
  return (
    <div className="vtk-tile">
      <div className="vtk-tile-title">{single.layers[0]?.label}</div>
      <Suspense fallback={<p>Loading 3D renderer…</p>}>
        <VtkScene
          data={!points && preview.kind === "vtk" ? preview.data : single}
          source={source}
          view={tileView}
          log={log}
          onCamera={onCamera}
          onError={onError}
          points={points}
          tile
        />
      </Suspense>
    </div>
  );
}
export function VolumeScreen({
  analysis: a,
  send,
}: {
  analysis: Analysis;
  send: (c: Command) => Promise<Analysis>;
}) {
  const v = a.spatial;
  const [data, setData] = useState<VolumeData | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [retry, setRetry] = useState(0),
    [max, setMax] = useState(false),
    [controlsHidden, setControlsHidden] = useState(false),
    [vtkError, setVtkError] = useState("");
  const [localDraft, setDraft] = useState<SpatialView>(v);
  const draft = useMemo(() => {
    const ids = new Set(a.signals.filter((s) => s.recipe).map((s) => s.id));
    return {
      ...localDraft,
      layers: localDraft.layers.filter((l) => ids.has(l.signal_id)),
      solo:
        localDraft.solo && ids.has(localDraft.solo) ? localDraft.solo : null,
    };
  }, [localDraft, a.signals]);
  const current = useRef(v);
  current.current = draft;
  const pending = useRef(0);
  useEffect(() => {
    if (!pending.current) setDraft(v);
  }, [v]);
  const change = (next: SpatialView) => {
    current.current = next;
    setDraft(next);
    pending.current++;
    void send({ type: "set_spatial", spatial: next })
      .catch((e) => {
        setError(e.message);
        setDraft(v);
      })
      .finally(() => pending.current--);
  };
  useEffect(() => {
    if (
      !v.layers.length &&
      !pending.current &&
      a.signals.some((s) => s.id === a.image_signal_id && s.recipe)
    )
      change({ ...v, layers: [defaultLayer(a.image_signal_id)] });
  }, [a.id, a.image_signal_id, v.layers.length]);
  const styles = enabledLayers(draft);
  const key = JSON.stringify([
    a.dataset.generation,
    a.roi,
    a.depth,
    a.depth_anchors,
    a.depth_coordinates,
    styles.map((l) => l.signal_id),
    draft.quality,
    a.signals.map((s) => [s.id, s.recipe, s.materialization_id]),
  ]);
  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    setLoading(true);
    setError("");
    setData(null);
    // Await authoritative commands before fetching geometry selected optimistically.
    if (
      JSON.stringify(enabledLayers(v).map((l) => l.signal_id)) !==
        JSON.stringify(styles.map((l) => l.signal_id)) ||
      v.quality !== draft.quality
    )
      return () => controller.abort();
    void request<VolumeData>(`/analyses/${a.id}/volumes`, {
      signal: controller.signal,
    })
      .then((d) => {
        if (!disposed) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!disposed) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => {
      disposed = true;
      controller.abort();
    };
  }, [
    key,
    retry,
    v.quality,
    JSON.stringify(enabledLayers(v).map((l) => l.signal_id)),
  ]);
  useEffect(() => {
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMax(false);
        setControlsHidden(false);
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, []);
  const displayData = useMemo(
    () =>
      data
        ? {
            ...data,
            layers: data.layers.map((l) => ({
              ...l,
              label:
                a.signals.find((s) => s.id === l.signal_id)?.name ?? l.label,
            })),
          }
        : null,
    [data, JSON.stringify(a.signals.map((s) => [s.id, s.name]))],
  );
  const visibleKey = JSON.stringify(styles.map((style) => style.signal_id));
  const vtkSource = useMemo(() => {
    if (!displayData) return null;
    const ids = new Set(JSON.parse(visibleKey) as string[]);
    return {
      ...displayData,
      layers: displayData.layers.filter((layer) => ids.has(layer.signal_id)),
    };
  }, [displayData, visibleKey]);
  const vtkPreview = useMemo(
    () =>
      vtkSource && draft.mode === "overlay"
        ? prepareVtkPreview(vtkSource)
        : null,
    [vtkSource, draft.mode],
  );
  const styleKey = JSON.stringify(
    styles.map((style) => [style.signal_id, style.percentile]),
  );
  const vtkStylesSupported = useMemo(
    () =>
      !!vtkSource &&
      vtkPreview?.kind === "vtk" &&
      canRenderVtkStyles(vtkSource, styles, a.display.log, vtkPreview.data),
    [vtkSource, vtkPreview, styleKey, a.display.log],
  );
  const useVtk =
    draft.mode === "overlay" &&
    !vtkError &&
    vtkPreview?.kind === "vtk" &&
    vtkStylesSupported;
  const useVtkPoints =
    draft.mode === "overlay" &&
    !!vtkSource?.layers.length &&
    !vtkError &&
    !useVtk;
  const hybrid = useMemo(() => {
    if (!vtkSource || !useVtkPoints) return null;
    const volumeIds: string[] = [];
    for (const layer of vtkSource.layers) {
      const single = { ...vtkSource, layers: [layer] };
      const preview = prepareVtkPreview(single);
      const style = styles.find((s) => s.signal_id === layer.signal_id);
      if (
        style &&
        preview.kind === "vtk" &&
        canRenderVtkStyles(single, [style], a.display.log, preview.data)
      )
        volumeIds.push(layer.signal_id);
    }
    const volumeSource = {
      ...vtkSource,
      layers: vtkSource.layers.filter((l) => volumeIds.includes(l.signal_id)),
    };
    const preview = volumeIds.length ? prepareVtkPreview(volumeSource) : null;
    const pointIds = vtkSource.layers
      .filter(
        (l) => !volumeIds.includes(l.signal_id) || preview?.kind !== "vtk",
      )
      .map((l) => l.signal_id);
    const data =
      preview?.kind === "vtk"
        ? {
            ...preview.data,
            layers: [
              ...preview.data.layers,
              ...vtkSource.layers.filter((l) => pointIds.includes(l.signal_id)),
            ],
          }
        : vtkSource;
    return { data, pointIds, preview };
  }, [vtkSource, useVtkPoints, styleKey, a.display.log]);
  const pages = Math.max(1, Math.ceil(styles.length / 4)),
    page = Math.min(draft.page, pages - 1);
  const tiles = useMemo(() => {
    if (!vtkSource || draft.mode !== "tiles") return [];
    return vtkSource.layers.slice(page * 4, page * 4 + 4).map((layer) => {
      const single = { ...vtkSource, layers: [layer] };
      const preview = prepareVtkPreview(single);
      const style = styles.find((s) => s.signal_id === layer.signal_id)!;
      return {
        single,
        preview,
        points:
          preview.kind !== "vtk" ||
          !canRenderVtkStyles(single, [style], a.display.log, preview.data),
      };
    });
  }, [vtkSource, draft.mode, page, styleKey, a.display.log]);
  const camera = (id: string, c: Camera) => {
    const state = current.current;
    const next =
      state.linked || state.mode === "overlay"
        ? { ...state, camera: c }
        : {
            ...state,
            layers: state.layers.map((l) =>
              l.signal_id === id ? { ...l, camera: c } : l,
            ),
          };
    if (JSON.stringify(next) !== JSON.stringify(state)) change(next);
  };
  return (
    <section
      className={`volume-workspace ${max ? "maximized" : ""} ${max && controlsHidden ? "controls-hidden" : ""}`}
      aria-label="3D visualization"
    >
      <LayerEditor analysis={a} view={draft} data={data} onChange={change} />
      <div className="volume-display">
        {max && controlsHidden && (
          <div className="volume-compact-controls">
            <button onClick={() => setControlsHidden(false)}>
              Show controls
            </button>
            <button
              onClick={() => {
                setControlsHidden(false);
                setMax(false);
              }}
            >
              Restore 3D
            </button>
          </div>
        )}
        <div className="volume-controls">
          <div className="volume-toolbar">
            <div className="volume-choice-control">
              <span>View</span>
              <button
                type="button"
                role="switch"
                aria-label="Tiles view"
                aria-checked={draft.mode === "tiles"}
                className="volume-choice"
                onClick={() =>
                  change({
                    ...draft,
                    mode: draft.mode === "overlay" ? "tiles" : "overlay",
                  })
                }
              >
                <span className={draft.mode === "overlay" ? "active" : ""}>
                  Overlay
                </span>
                <span className={draft.mode === "tiles" ? "active" : ""}>
                  Tiles
                </span>
              </button>
            </div>
            <div className="volume-choice-control">
              <span>Preview</span>
              <button
                type="button"
                role="switch"
                aria-label="Detailed preview"
                aria-checked={draft.quality === "Detailed"}
                className="volume-choice"
                onClick={() =>
                  change({
                    ...draft,
                    quality: draft.quality === "Fast" ? "Detailed" : "Fast",
                  })
                }
              >
                <span className={draft.quality === "Fast" ? "active" : ""}>
                  Fast
                </span>
                <span className={draft.quality === "Detailed" ? "active" : ""}>
                  Detailed
                </span>
              </button>
            </div>
            <details className="volume-options">
              <summary>Display settings</summary>
              <div className="volume-options-panel">
                <label>
                  Intensity scale
                  <select
                    aria-label="3D intensity scale"
                    value={draft.scale}
                    onChange={(e) =>
                      change({
                        ...draft,
                        scale: e.target.value as SpatialView["scale"],
                      })
                    }
                  >
                    <option value="independent">Independent</option>
                    <option value="shared">Shared numerical</option>
                  </select>
                </label>
                <label className="volume-log-control">
                  <input
                    type="checkbox"
                    checked={a.display.log}
                    onChange={(e) =>
                      void send({
                        type: "set_display",
                        ...a.display,
                        log: e.target.checked,
                        image: a.display.image as "sims" | "se",
                      }).catch((e) => setError(e.message))
                    }
                  />
                  Log colors
                </label>
                {draft.mode === "tiles" && (
                  <label>
                    <input
                      type="checkbox"
                      checked={draft.linked}
                      onChange={(e) =>
                        change({ ...draft, linked: e.target.checked })
                      }
                    />
                    Linked cameras
                  </label>
                )}
                <label>
                  {data && data.z_unit !== "frame"
                    ? "Depth exaggeration"
                    : "Frame stretch"}
                  <input
                    aria-label={
                      data && data.z_unit !== "frame"
                        ? "Depth exaggeration"
                        : "Frame stretch"
                    }
                    type="number"
                    min=".01"
                    max="1000"
                    step=".1"
                    value={
                      data && data.z_unit !== "frame"
                        ? draft.depth_exaggeration
                        : draft.frame_stretch
                    }
                    onChange={(e) => {
                      const n = Number(e.target.value);
                      if (n >= 0.01 && n <= 1000)
                        change({
                          ...draft,
                          ...(data && data.z_unit !== "frame"
                            ? { depth_exaggeration: n }
                            : { frame_stretch: n }),
                        });
                    }}
                  />
                </label>
              </div>
            </details>
          </div>
          <div className="volume-camera-toolbar">
            <button
              onClick={() =>
                change({
                  ...draft,
                  camera: defaultCamera,
                  layers: draft.layers.map((l) => ({
                    ...l,
                    camera: defaultCamera,
                  })),
                })
              }
            >
              Reset cameras
            </button>
            <button
              onClick={() =>
                change({
                  ...draft,
                  camera: {
                    ...draft.camera,
                    projection:
                      draft.camera.projection === "perspective"
                        ? "orthographic"
                        : "perspective",
                  },
                  layers: draft.layers.map((l) => ({
                    ...l,
                    camera: {
                      ...l.camera,
                      projection:
                        l.camera.projection === "perspective"
                          ? "orthographic"
                          : "perspective",
                    },
                  })),
                })
              }
            >
              {draft.camera.projection === "perspective"
                ? "Orthographic"
                : "Perspective"}{" "}
              camera
            </button>
            <button
              onClick={() => {
                setMax(!max);
                if (max) setControlsHidden(false);
              }}
            >
              {max ? "Restore 3D" : "Maximize 3D"}
            </button>
            {max && (
              <button onClick={() => setControlsHidden(true)}>
                Hide controls
              </button>
            )}
          </div>
          {draft.mode === "tiles" && pages > 1 && (
            <div className="row volume-page-controls">
              <button
                disabled={!page}
                onClick={() => change({ ...draft, page: page - 1 })}
              >
                Previous 3D page
              </button>
              <span>
                Page {page + 1} of {pages}
              </span>
              <button
                disabled={page + 1 >= pages}
                onClick={() => change({ ...draft, page: page + 1 })}
              >
                Next 3D page
              </button>
            </div>
          )}
        </div>
        {error && (
          <div role="alert" className="error">
            {error}
            <button onClick={() => setRetry((x) => x + 1)}>Retry 3D</button>
          </div>
        )}
        {vtkError && (
          <div role="alert" className="error">
            3D renderer failed: {vtkError}
            <button onClick={() => setVtkError("")}>Retry vtk renderer</button>
          </div>
        )}
        {loading ? (
          <VolumePlaceholder />
        ) : data && data.layers.length > 0 ? (
          draft.mode === "tiles" && vtkSource && !vtkError ? (
            <div
              className="volume-canvas vtk-tiles"
              data-testid="volume-canvas"
              data-renderer="vtk"
              data-tile-count={
                vtkSource.layers.slice(page * 4, page * 4 + 4).length
              }
            >
              {tiles.map(({ single, preview, points }) => (
                <VtkTile
                  key={single.layers[0].signal_id}
                  source={vtkSource}
                  single={single}
                  preview={preview}
                  points={points}
                  view={draft}
                  log={a.display.log}
                  onCamera={camera}
                  onError={setVtkError}
                />
              ))}
            </div>
          ) : useVtkPoints || (useVtk && vtkPreview?.kind === "vtk") ? (
            <Suspense fallback={<VolumePlaceholder />}>
              <VtkScene
                data={
                  useVtkPoints
                    ? hybrid!.data
                    : (
                        vtkPreview as Extract<
                          NonNullable<typeof vtkPreview>,
                          { kind: "vtk" }
                        >
                      ).data
                }
                source={vtkSource!}
                view={draft}
                log={a.display.log}
                onCamera={camera}
                onError={setVtkError}
                pointIds={useVtkPoints ? hybrid!.pointIds : undefined}
              />
            </Suspense>
          ) : null
        ) : (
          !loading && (
            <p>
              No visible covered volume. Add or show a signal, or choose frames
              with known depth.
            </p>
          )
        )}
        <div className="volume-footer">
          <div className="volume-footer-help">
            <div className="volume-interaction-hint">
              Drag to orbit · scroll to zoom · shift-drag to pan
            </div>
            <details className="volume-rendering-notes">
              <summary>Rendering and geometry details</summary>{" "}
              <small>
                Drag to orbit · scroll to zoom · shift-drag to pan. Overlay
                transparency is qualitative; show one signal or use tiles to
                inspect occluded signals.{" "}
                {data?.physical_aspect
                  ? "At 1×, calibrated depth and XY use the same physical scale."
                  : "Frame stretch is a display ratio; physical proportions require calibrated depth and known XY."}{" "}
                vtk uses a qualitative preview; intensity hover is not yet
                available. Missing samples remain missing. Thin, constant and
                incomplete selections use points.
              </small>
            </details>
          </div>
          <div className="volume-footer-notes">
            <p className="volume-status" data-testid="volume-status">
              {loading
                ? "Preparing 3D…"
                : data
                  ? `${data.layers.length} layers · ${data.shape.join(" × ")} preview · ${data.total_voxels.toLocaleString()} / 500,000 voxels · ${data.omitted_frames} frames with unknown depth omitted`
                  : ""}
            </p>
            {useVtk && vtkPreview?.kind === "vtk" && vtkPreview.resampled && (
              <p className="volume-resampling-warning">
                {vtkPreview.resampledXY && vtkPreview.resampledDepth
                  ? vtkPreview.data.z_unit === "frame"
                    ? "Nonuniform XY and frame coordinates are resampled"
                    : "Nonuniform XY and depth are resampled"
                  : vtkPreview.resampledXY
                    ? "Nonuniform XY is resampled"
                    : vtkPreview.data.z_unit === "frame"
                      ? "Nonuniform frame coordinates are resampled"
                      : "Nonuniform depth is resampled"}{" "}
                for the 3D preview; profiles, measurements and exports use the
                original data.
              </p>
            )}
            {tiles.some(
              (tile) =>
                !tile.points &&
                tile.preview.kind === "vtk" &&
                tile.preview.resampled,
            ) && (
              <p className="volume-resampling-warning">
                Nonuniform preview coordinates are resampled for display;
                profiles, measurements and exports use the original data.
              </p>
            )}
            {tiles.some(
              (tile) =>
                !tile.points &&
                tile.preview.kind === "vtk" &&
                vtkSamplingLimited(vtkDisplayExtent(tile.preview.data, draft)),
            ) && (
              <p className="volume-sampling-warning">
                3D sampling is reduced for this aspect ratio; fine features may
                be missed.
              </p>
            )}
            {tiles.some((tile) => tile.points) && (
              <p>Some signals use original preview samples shown as points.</p>
            )}
            {useVtk &&
              vtkPreview?.kind === "vtk" &&
              vtkSamplingLimited(vtkDisplayExtent(vtkPreview.data, draft)) && (
                <p className="volume-sampling-warning">
                  3D sampling is reduced for this aspect ratio; fine features
                  may be missed.
                </p>
              )}
            {useVtkPoints && (
              <p>
                Showing some original preview samples as points for this
                selection.
              </p>
            )}
            {useVtkPoints &&
              hybrid?.preview?.kind === "vtk" &&
              hybrid.preview.resampled && (
                <p className="volume-resampling-warning">
                  Nonuniform coordinates are resampled for the 3D preview;
                  profiles, measurements and exports use the original data.
                </p>
              )}
            {useVtkPoints &&
              hybrid?.preview?.kind === "vtk" &&
              vtkSamplingLimited(
                vtkDisplayExtent(hybrid.preview.data, draft),
              ) && (
                <p className="volume-sampling-warning">
                  3D sampling is reduced for this aspect ratio; fine features
                  may be missed.
                </p>
              )}
          </div>
        </div>
      </div>
    </section>
  );
}
