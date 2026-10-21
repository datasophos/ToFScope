import { useEffect, useState, type ReactNode } from "react";
import type { Analysis } from "../api/client";
import type { Send } from "./SignalDetails";
import { HelpHeading } from "../components/HelpButton";
import { help } from "./help";
export function availableFrames(a: Analysis): [number, number] {
  const recipe = a.signals.find((s) => s.id === a.image_signal_id)!.recipe!;
  return [recipe.frames[0], recipe.frames[1]];
}
export function ViewingDepths({
  analysis: a,
  send,
  children,
}: {
  analysis: Analysis;
  send: Send;
  children?: ReactNode;
}) {
  const bounds = availableFrames(a),
    current = a.depth.mode === "frame" ? a.depth.index : bounds[0];
  const [slider, setSlider] = useState(current);
  useEffect(() => setSlider(current), [current]);
  const frame = (n: number) =>
    void send({
      type: "set_depth",
      depth: {
        mode: "frame",
        index: Math.min(bounds[1], Math.max(bounds[0], n)),
      },
    }).catch(() => {});
  const range =
    a.depth.mode === "window"
      ? [a.depth.first, a.depth.last]
      : a.depth.mode === "frame"
        ? [a.depth.index, a.depth.index]
        : bounds;
  const [draft, setDraft] = useState(range.map(String));
  useEffect(() => setDraft(range.map(String)), [range[0], range[1]]);
  const selectMode = (mode: Analysis["depth"]["mode"]) => {
    if (mode === a.depth.mode) return;
    if (mode === "frame") return frame(current);
    void send({
      type: "set_depth",
      depth:
        mode === "all"
          ? { mode: "all" }
          : { mode: "window", first: range[0], last: range[1] },
    }).catch(() => {});
  };
  const summary =
    a.depth.mode === "all"
      ? `Summing frames ${bounds[0]}–${bounds[1]} · ${bounds[1] - bounds[0] + 1} frames`
      : a.depth.mode === "frame"
        ? `Showing frame ${a.depth.index} of ${bounds[0]}–${bounds[1]}`
        : `Summing frames ${a.depth.first}–${a.depth.last} · ${a.depth.last - a.depth.first + 1} ${a.depth.last === a.depth.first ? "frame" : "frames"}`;
  return (
    <section className="depth-strip" aria-label="Viewing depths">
      <HelpHeading title="Viewing depths" content={help.depth} />
      <div
        className="depth-mode-controls"
        role="group"
        aria-label="Depth viewing mode"
      >
        {(
          [
            ["all", "All frames"],
            ["frame", "Single frame"],
            ["window", "Frame range"],
          ] as const
        ).map(([mode, label]) => (
          <button
            key={mode}
            aria-pressed={a.depth.mode === mode}
            onClick={() => selectMode(mode)}
          >
            {label}
          </button>
        ))}
      </div>
      {a.depth.mode === "frame" && (
        <div
          className="depth-selection-controls"
          role="group"
          aria-label="Frame navigation"
        >
          <button
            aria-label="Previous frame"
            disabled={current <= bounds[0]}
            onClick={() => frame(current - 1)}
          >
            ←
          </button>
          <input
            aria-label="Frame"
            type="number"
            min={bounds[0]}
            max={bounds[1]}
            value={current}
            onChange={(e) => frame(Number(e.target.value))}
          />
          <button
            aria-label="Next frame"
            disabled={current >= bounds[1]}
            onClick={() => frame(current + 1)}
          >
            →
          </button>
          <input
            aria-label="Depth slider"
            type="range"
            min={bounds[0]}
            max={bounds[1]}
            value={slider}
            onChange={(e) => setSlider(Number(e.target.value))}
            onPointerUp={() => frame(slider)}
            onKeyUp={(e) => {
              if (
                [
                  "ArrowLeft",
                  "ArrowRight",
                  "ArrowUp",
                  "ArrowDown",
                  "Home",
                  "End",
                  "PageUp",
                  "PageDown",
                ].includes(e.key)
              ) {
                e.stopPropagation();
                frame(slider);
              }
            }}
          />
        </div>
      )}
      {a.depth.mode === "window" && (
        <form
          className="exact-form"
          aria-label="Frame range"
          onSubmit={(e) => {
            e.preventDefault();
            void send({
              type: "set_depth",
              depth: {
                mode: "window",
                first: Number(draft[0]),
                last: Number(draft[1]),
              },
            }).catch(() => {});
          }}
        >
          {["First frame", "Last frame"].map((label, i) => (
            <label key={label}>
              {label}
              <input
                type="number"
                aria-label={label}
                required
                step="1"
                min={
                  i === 0 ? bounds[0] : Math.max(bounds[0], Number(draft[0]))
                }
                max={bounds[1]}
                value={draft[i]}
                onChange={(e) =>
                  setDraft((previous) =>
                    previous.map((value, j) =>
                      i === j ? e.target.value : value,
                    ),
                  )
                }
              />
            </label>
          ))}
          <button>Apply</button>
        </form>
      )}
      <span className="depth-view-status" role="status">
        {summary}
      </span>
      <div
        className="depth-axis-settings"
        role="group"
        aria-label="Depth axis settings"
      >
        <span className="depth-axis-label">Axis units</span>
        <div
          className="depth-coordinate-controls"
          role="group"
          aria-label="Depth coordinates"
        >
          <button
            aria-pressed={a.depth_coordinates === "frame"}
            onClick={() =>
              void send({
                type: "set_depth_display",
                unit: a.depth_unit,
                coordinates: "frame",
              }).catch(() => {})
            }
          >
            Frames
          </button>
          <button
            aria-label="Physical depth"
            aria-pressed={a.depth_coordinates === "depth"}
            disabled={a.depth_anchors.length < 2}
            title={
              a.depth_anchors.length < 2
                ? "Add a positive-depth anchor with Depth calibration first."
                : "Show profiles and front projections in physical depth."
            }
            onClick={() =>
              void send({
                type: "set_depth_display",
                unit: a.depth_unit,
                coordinates: "depth",
              }).catch(() => {})
            }
          >
            Physical depth
            {a.depth_coordinates === "depth"
              ? ` (${a.depth_unit === "um" ? "µm" : a.depth_unit})`
              : ""}
          </button>
        </div>
        {children}
      </div>
    </section>
  );
}
