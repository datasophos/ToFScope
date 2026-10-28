import { useEffect, useMemo, useRef, useState } from "react";
import { request, type Analysis, type Command } from "../api/client";
import { LayerEditor } from "./LayerEditor";
import {
  mountSpatial,
  enabledLayers,
  defaultCamera,
  type VolumeData,
  type SpatialView,
  type Camera,
} from "./spatialRenderer";
function Scene({
  data,
  view,
  onCamera,
  log,
}: {
  data: VolumeData;
  view: SpatialView;
  onCamera: (id: string, c: Camera) => void;
  log: boolean;
}) {
  const element = useRef<HTMLDivElement>(null),
    handle = useRef<Awaited<ReturnType<typeof mountSpatial>> | null>(null);
  const latest = useRef({ data, view, onCamera, log });
  latest.current = { data, view, onCamera, log };
  const [error, setError] = useState("");
  useEffect(() => {
    let disposed = false;
    const observer = new ResizeObserver(() => handle.current?.resize());
    observer.observe(element.current!);
    void mountSpatial(element.current!, (id, c) =>
      latest.current.onCamera(id, c),
    )
      .then((h) => {
        if (disposed) {
          h.destroy();
          return;
        }
        handle.current = h;
        return h.update(latest.current.data, latest.current.view, {
          log: latest.current.log,
        });
      })
      .catch((e) => {
        if (!disposed) setError(e.message);
      });
    return () => {
      disposed = true;
      observer.disconnect();
      handle.current?.destroy();
      handle.current = null;
    };
  }, []);
  useEffect(() => {
    void handle.current
      ?.update(data, view, { log })
      .catch((e) => setError(e.message));
  }, [data, view, log]);
  return (
    <>
      {error && <div role="alert">{error}</div>}
      <div
        ref={element}
        className="volume-canvas"
        data-testid="volume-canvas"
      />
    </>
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
    [max, setMax] = useState(false);
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
      if (e.key === "Escape") setMax(false);
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
    [data, a.signals],
  );
  const pages = Math.max(1, Math.ceil(styles.length / 4)),
    page = Math.min(draft.page, pages - 1);
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
      className={`volume-workspace ${max ? "maximized" : ""}`}
      aria-label="3D visualization"
    >
      <LayerEditor analysis={a} view={draft} data={data} onChange={change} />
      <div className="volume-display">
        <div className="volume-toolbar">
          <label>
            View
            <select
              aria-label="3D view mode"
              value={draft.mode}
              onChange={(e) =>
                change({
                  ...draft,
                  mode: e.target.value as SpatialView["mode"],
                })
              }
            >
              <option value="overlay">Overlay</option>
              <option value="tiles">Tiles</option>
            </select>
          </label>
          <label>
            Preview
            <select
              aria-label="3D preview quality"
              value={draft.quality}
              onChange={(e) =>
                change({
                  ...draft,
                  quality: e.target.value as SpatialView["quality"],
                })
              }
            >
              <option>Fast</option>
              <option>Detailed</option>
            </select>
          </label>
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
        </div>
        <div className="volume-camera-toolbar">
          <label>
            <input
              type="checkbox"
              checked={draft.linked}
              onChange={(e) => change({ ...draft, linked: e.target.checked })}
            />
            Linked cameras
          </label>
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
          <button onClick={() => setMax(!max)}>
            {max ? "Restore 3D" : "Maximize 3D"}
          </button>
        </div>
        {draft.mode === "tiles" && (
          <div className="row">
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
        {error && (
          <div role="alert" className="error">
            {error}
            <button onClick={() => setRetry((x) => x + 1)}>Retry 3D</button>
          </div>
        )}
        <p className="volume-status" data-testid="volume-status">
          {loading
            ? "Preparing 3D…"
            : data
              ? `${data.layers.length} layers · ${data.shape.join(" × ")} preview · ${data.total_voxels.toLocaleString()} / 500,000 voxels · ${data.omitted_frames} frames with unknown depth omitted`
              : ""}
        </p>
        {data && data.layers.length > 0 ? (
          <Scene
            key={`${draft.mode}-${page}`}
            data={displayData!}
            view={draft}
            log={a.display.log}
            onCamera={camera}
          />
        ) : (
          !loading && (
            <p>
              No visible covered volume. Add or show a signal, or choose frames
              with known depth.
            </p>
          )
        )}
        <div className="volume-interaction-hint">
          Drag to orbit · scroll to zoom · right-drag to pan
        </div>
        <details className="volume-rendering-notes">
          <summary>Rendering and geometry details</summary>{" "}
          <small>
            Drag to orbit · scroll to zoom · right-drag to pan. Overlay
            transparency is qualitative; use Solo or tiles to inspect occluded
            signals.{" "}
            {data?.physical_aspect
              ? "At 1×, calibrated depth and XY use the same physical scale."
              : "Frame stretch is a display ratio; physical proportions require calibrated depth and known XY."}{" "}
            Missing samples remain missing. Thin, constant and irregular missing
            coverage uses points.
          </small>
        </details>
      </div>
    </section>
  );
}
