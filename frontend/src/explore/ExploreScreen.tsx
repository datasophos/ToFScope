import { useEffect, useState } from "react";
import { useAnalysis } from "../app/useAnalysis";
import {
  post,
  request,
  download,
  type Analysis,
  type Command,
  type Job,
  type JobInput,
} from "../api/client";
import { PlotPanel } from "../plots/PlotPanel";
import { SignalPicker } from "./SignalPicker";
import { roiFromBounds, roiBounds, frameWindow, type ROI } from "./selection";
function ExactForm({
  labels,
  values,
  onApply,
  button,
}: {
  labels: string[];
  values: number[];
  onApply: (values: number[]) => void;
  button: string;
}) {
  const [draft, setDraft] = useState(values.map(String));
  useEffect(() => setDraft(values.map(String)), [values.join(",")]);
  return (
    <form
      className="exact-form"
      onSubmit={(e) => {
        e.preventDefault();
        onApply(draft.map(Number));
      }}
    >
      {labels.map((label, i) => (
        <label key={label}>
          {label}
          <input
            type="number"
            step="1"
            aria-label={label}
            value={draft[i]}
            onChange={(e) =>
              setDraft((a) => a.map((v, j) => (j === i ? e.target.value : v)))
            }
          />
        </label>
      ))}
      <button>{button}</button>
    </form>
  );
}
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
  } = useAnalysis(initial);
  const [search, setSearch] = useState(""),
    [recent, setRecent] = useState<number[]>([]),
    [draft, setDraft] = useState<[string, string][]>(
      initial.active_recipe.intervals.map(([x, y]) => [String(x), String(y)]),
    ),
    [draftIndex, setDraftIndex] = useState(0),
    [integrationFrames, setIntegrationFrames] = useState<[number, number]>(
      initial.loaded_frames,
    ),
    [target, setTarget] = useState<"active" | "comparison">("active"),
    [job, setJob] = useState<Job | null>(null),
    [max, setMax] = useState<string | null>(null),
    [slider, setSlider] = useState(initial.loaded_frames[0]);
  const command = (c: Command) => void send(c).catch(() => {});
  const currentFrame =
    a.depth.mode === "frame" ? a.depth.index : a.loaded_frames[0];
  useEffect(() => setSlider(currentFrame), [currentFrame]);
  useEffect(() => {
    if (!active) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMax(null);
      if ((e.target as HTMLElement).matches("input,select,textarea")) return;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        command({
          type: "set_depth",
          depth: {
            mode: "frame",
            index: Math.max(
              a.loaded_frames[0],
              Math.min(
                a.loaded_frames[1],
                currentFrame + (e.key === "ArrowRight" ? 1 : -1),
              ),
            ),
          },
        });
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [a.revision, active]);
  useEffect(() => {
    if (
      !job ||
      ["succeeded", "failed", "obsolete", "cancelled"].includes(job.status)
    )
      return;
    let alive = true;
    const poll = async () => {
      try {
        const j = await request<Job>(`/jobs/${job.id}`);
        if (alive) {
          setJob(j);
          if (j.status === "succeeded") await refresh();
          if (j.safe_error) setError(j.safe_error);
        }
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    };
    void poll();
    const t = setInterval(() => void poll(), 250);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [job?.id, job?.status]);
  const selectedDepth =
    a.depth.mode === "window"
      ? [a.depth.first, a.depth.last]
      : a.depth.mode === "frame"
        ? [a.depth.index, a.depth.index]
        : undefined;
  const apply = async () => {
    try {
      const spec: JobInput = {
        request_id: crypto.randomUUID(),
        expected_revision: a.revision,
        dataset_generation: a.dataset.generation,
        spec: {
          intervals: draft.map(([x, y]) => [Number(x), Number(y)]),
          frames: integrationFrames,
          target,
        },
      };
      setError("");
      let j: Job;
      try {
        j = await post(`/analyses/${a.id}/jobs`, spec);
      } catch (e) {
        if (!(e instanceof TypeError)) throw e;
        j = await post(`/analyses/${a.id}/jobs`, spec);
      }
      setJob(j);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const busy = job && ["queued", "running"].includes(job.status);
  const filtered = a.peaks.filter(
    (p) =>
      p.label.toLowerCase().includes(search.toLowerCase()) ||
      String(p.mass).includes(search),
  );
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
        </div>
      </div>
      {error && (
        <div role="alert" className="error">
          {error}
          <button onClick={() => void refresh()}>Retry</button>
          <span> Export settings before reopening a changed source.</span>
        </div>
      )}
      <div className="analysis-layout">
        <aside className="sidebar">
          <section>
            <h2>Signal</h2>
            <input
              aria-label="Search signals"
              placeholder="Search mass or label"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <SignalPicker
              buttonLabel="Select stored signal"
              listboxLabel="Stored signals"
              placeholder="Choose a stored signal"
              options={filtered}
              value={
                a.active_recipe.source === "stored"
                  ? (a.active_recipe.stored_index ?? undefined)
                  : undefined
              }
              onChoose={(i) => {
                setRecent((old) =>
                  [i, ...old.filter((v) => v !== i)].slice(0, 5),
                );
                command({ type: "select_stored", index: i });
              }}
            />
            <p data-testid="active-source">
              <strong>{a.active_recipe.label}</strong> ·{" "}
              {a.active_recipe.source}
            </p>
            {recent.length > 0 && (
              <div className="recent">
                Recent:{" "}
                {recent.map((i) => (
                  <button
                    key={i}
                    onClick={() => command({ type: "select_stored", index: i })}
                  >
                    {a.peaks[i].mass}
                  </button>
                ))}
              </div>
            )}
            <SignalPicker
              buttonLabel="Add stored comparison"
              listboxLabel="Stored comparison signals"
              placeholder="Add stored comparison…"
              options={filtered}
              onChoose={(index) =>
                command({ type: "add_stored_comparison", index })
              }
            />
            {a.comparisons.map((r) => (
              <p className="row" key={r.id}>
                <span>{r.label}</span>
                <button
                  aria-label={`Remove ${r.label}`}
                  onClick={() =>
                    command({ type: "remove_comparison", recipe_id: r.id! })
                  }
                >
                  ×
                </button>
              </p>
            ))}
          </section>
          <section>
            <h2>
              Mass windows <span className="badge">Draft</span>
            </h2>
            <p className="muted">
              Inclusive endpoints in Th. Apply reads raw events; editing does
              not.
            </p>
            {draft.map(([lo, hi], i) => (
              <div
                className={`mass-row ${i === draftIndex ? "selected" : ""}`}
                key={i}
                onFocus={() => setDraftIndex(i)}
              >
                <input
                  aria-label={`Mass lower ${i + 1}`}
                  type="number"
                  step="any"
                  value={lo}
                  onChange={(e) =>
                    setDraft((old) =>
                      old.map((w, j) => (j === i ? [e.target.value, w[1]] : w)),
                    )
                  }
                />
                <span>–</span>
                <input
                  aria-label={`Mass upper ${i + 1}`}
                  type="number"
                  step="any"
                  value={hi}
                  onChange={(e) =>
                    setDraft((old) =>
                      old.map((w, j) => (j === i ? [w[0], e.target.value] : w)),
                    )
                  }
                />
                <button
                  aria-label={`Remove interval ${i + 1}`}
                  onClick={() => {
                    setDraft((old) => old.filter((_, j) => i !== j));
                    setDraftIndex(0);
                  }}
                >
                  ×
                </button>
              </div>
            ))}
            <button
              onClick={() => {
                setDraft((old) => [
                  ...old,
                  [String(a.mass_limits[0]), String(a.mass_limits[1])],
                ]);
                setDraftIndex(draft.length);
              }}
            >
              Add interval
            </button>
            <ExactForm
              labels={["Integration first", "Integration last"]}
              values={integrationFrames}
              onApply={(v) => setIntegrationFrames(v as [number, number])}
              button="Set integration range"
            />
            <select
              aria-label="Integration target"
              value={target}
              onChange={(e) => setTarget(e.target.value as typeof target)}
            >
              <option value="active">Apply as active signal</option>
              <option value="comparison">Add to comparisons</option>
            </select>
            <button
              className="primary"
              disabled={!!busy || draft.length === 0}
              onClick={() => void apply()}
            >
              Apply custom window
            </button>
            {job && (
              <div className="job">
                <output data-testid="job-status">
                  {job.status} · {job.done}/{job.total}
                </output>
                <progress max={Math.max(1, job.total)} value={job.done} />
                {busy && (
                  <button
                    onClick={() =>
                      post<Job>(`/jobs/${job.id}/cancel`)
                        .then(setJob)
                        .catch((e) => setError(e.message))
                    }
                  >
                    Cancel integration
                  </button>
                )}
              </div>
            )}
          </section>
          <section>
            <h2>Spatial ROI</h2>
            <ExactForm
              labels={[
                "ROI x first",
                "ROI x last",
                "ROI y first",
                "ROI y last",
              ]}
              values={a.roi}
              onApply={(v) => command({ type: "set_roi", roi: v as ROI })}
              button="Apply ROI"
            />
            <button
              onClick={() =>
                command({
                  type: "set_roi",
                  roi: [0, a.shape[2] - 1, 0, a.shape[1] - 1],
                })
              }
            >
              Reset to full field
            </button>
          </section>
          <section>
            <h2>Loaded frames</h2>
            <ExactForm
              labels={["Loaded first", "Loaded last"]}
              values={a.loaded_frames}
              onApply={(v) =>
                command({
                  type: "set_loaded_frames",
                  frames: v as [number, number],
                })
              }
              button="Load frame range"
            />
          </section>
          <section>
            <h2>Display</h2>
            <label>
              <input
                type="checkbox"
                checked={a.display.log}
                onChange={(e) =>
                  command({
                    type: "set_display",
                    ...a.display,
                    log: e.target.checked,
                    image: a.display.image as "sims" | "se",
                  })
                }
              />{" "}
              Log colors
            </label>
            <label>
              <input
                type="checkbox"
                checked={a.display.relative}
                onChange={(e) =>
                  command({
                    type: "set_display",
                    ...a.display,
                    relative: e.target.checked,
                    image: a.display.image as "sims" | "se",
                  })
                }
              />{" "}
              Relative profiles
            </label>
            <label>
              Image
              <select
                aria-label="Image signal"
                value={a.display.image}
                onChange={(e) =>
                  command({
                    type: "set_display",
                    ...a.display,
                    image: e.target.value as "sims" | "se",
                  })
                }
              >
                <option value="sims">SIMS</option>
                <option value="se">SE · unregistered</option>
              </select>
            </label>
          </section>
        </aside>
        <div className="explore-main">
          <section className="depth-strip">
            <div>
              <strong>
                {a.depth.mode === "all"
                  ? "All depths"
                  : a.depth.mode === "frame"
                    ? `Frame ${a.depth.index}`
                    : `Window ${a.depth.first}–${a.depth.last}`}
              </strong>
              <span className="muted"> · zero based, inclusive</span>
            </div>
            <div className="row">
              <button
                onClick={() =>
                  command({ type: "set_depth", depth: { mode: "all" } })
                }
              >
                All depths
              </button>
              <button
                aria-label="Previous frame"
                onClick={() =>
                  command({
                    type: "set_depth",
                    depth: {
                      mode: "frame",
                      index: Math.max(a.loaded_frames[0], currentFrame - 1),
                    },
                  })
                }
              >
                ←
              </button>
              <input
                aria-label="Frame"
                type="number"
                min={a.loaded_frames[0]}
                max={a.loaded_frames[1]}
                value={slider}
                onChange={(e) => setSlider(Number(e.target.value))}
                onBlur={() => {
                  if (slider !== currentFrame)
                    command({
                      type: "set_depth",
                      depth: { mode: "frame", index: slider },
                    });
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter")
                    command({
                      type: "set_depth",
                      depth: { mode: "frame", index: slider },
                    });
                }}
              />
              <button
                aria-label="Next frame"
                onClick={() =>
                  command({
                    type: "set_depth",
                    depth: {
                      mode: "frame",
                      index: Math.min(a.loaded_frames[1], currentFrame + 1),
                    },
                  })
                }
              >
                →
              </button>
              <input
                aria-label="Frame slider"
                type="range"
                min={a.loaded_frames[0]}
                max={a.loaded_frames[1]}
                value={slider}
                onChange={(e) => setSlider(Number(e.target.value))}
                onPointerUp={() =>
                  command({
                    type: "set_depth",
                    depth: { mode: "frame", index: slider },
                  })
                }
                onKeyUp={() =>
                  command({
                    type: "set_depth",
                    depth: { mode: "frame", index: slider },
                  })
                }
              />
            </div>
            <ExactForm
              labels={["Window first", "Window last"]}
              values={
                a.depth.mode === "window"
                  ? [a.depth.first, a.depth.last]
                  : a.loaded_frames
              }
              onApply={(v) =>
                command({
                  type: "set_depth",
                  depth: { mode: "window", first: v[0], last: v[1] },
                })
              }
              button="Select window"
            />
          </section>
          <div className="plot-grid">
            <PlotPanel
              name="ion"
              title={a.display.image === "se" ? "SE image" : "Ion map"}
              panel={data?.panels.ion}
              expectedKind="image"
              loading={!data?.panels.ion && !error}
              maximized={max === "ion"}
              onMaximize={() => setMax(max === "ion" ? null : "ion")}
              mode="xy"
              selection={
                a.display.image === "sims"
                  ? roiBounds(a.roi, a.shape, a.fov_um)
                  : undefined
              }
              onSelect={(b) => {
                if (a.display.image === "sims")
                  command({
                    type: "set_roi",
                    roi: roiFromBounds(b, a.shape, a.fov_um),
                  });
              }}
            />
            <PlotPanel
              zoomWindow={draft[draftIndex]?.map(Number) as [number, number]}
              name="spectrum"
              title="Spectrum"
              panel={data?.panels.spectrum}
              maximized={max === "spectrum"}
              onMaximize={() => setMax(max === "spectrum" ? null : "spectrum")}
              selection={draft[draftIndex]?.map(Number)}
              onSelect={(b) => {
                const low = Math.max(a.mass_limits[0], Math.min(...b)),
                  high = Math.min(a.mass_limits[1], Math.max(...b));
                if (low >= high) return;
                setDraft((old) =>
                  old.length
                    ? old.map((w, i) =>
                        i === draftIndex ? [String(low), String(high)] : w,
                      )
                    : [[String(low), String(high)]],
                );
                if (!draft.length) setDraftIndex(0);
              }}
            />
            <PlotPanel
              name="front"
              title="Front projection"
              panel={data?.panels.front}
              expectedKind="image"
              loading={!data?.panels.front && !error}
              maximized={max === "front"}
              onMaximize={() => setMax(max === "front" ? null : "front")}
              onClick={(_x, y) =>
                command({
                  type: "set_depth",
                  depth: {
                    mode: "frame",
                    index: Math.max(
                      a.loaded_frames[0],
                      Math.min(a.loaded_frames[1], Math.round(y)),
                    ),
                  },
                })
              }
              onSelect={() => {}}
            />
            <PlotPanel
              onAllDepths={() =>
                command({ type: "set_depth", depth: { mode: "all" } })
              }
              name="profile"
              title="Depth profile"
              panel={data?.panels.profile}
              maximized={max === "profile"}
              onMaximize={() => setMax(max === "profile" ? null : "profile")}
              selection={selectedDepth}
              onClick={(x) =>
                command({
                  type: "set_depth",
                  depth: {
                    mode: "frame",
                    index: Math.max(
                      a.loaded_frames[0],
                      Math.min(a.loaded_frames[1], Math.round(x)),
                    ),
                  },
                })
              }
              onSelect={(b) => {
                const [first, last] = frameWindow(b, a.loaded_frames);
                command({
                  type: "set_depth",
                  depth: { mode: "window", first, last },
                });
              }}
            />
          </div>
          <p className="scope-note">
            Original-resolution values drive profiles and exports. Log colors
            and relative scaling affect display only. Calibration editors,
            identification, 3D and acquisition saves are planned separately.
          </p>
        </div>
      </div>
    </main>
  );
}
