import { useEffect, useState, type ReactNode } from "react";
import type { Analysis } from "../api/client";
import type { Send } from "./SignalDetails";
import { HelpHeading } from "../components/HelpButton";
import { ExactForm } from "./ExactForm";
import { help } from "./help";
export function availableFrames(a: Analysis): [number, number] {
  const recipe = a.signals.find((s) => s.id === a.image_signal_id)!.recipe!;
  return [
    Math.max(a.loaded_frames[0], recipe.frames[0]),
    Math.min(a.loaded_frames[1], recipe.frames[1]),
  ];
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
  const summary =
    a.depth.mode === "all"
      ? `All depths · frames ${bounds[0]}–${bounds[1]}`
      : a.depth.mode === "frame"
        ? `Frame ${a.depth.index}`
        : `Frames ${a.depth.first}–${a.depth.last}`;
  return (
    <section className="depth-strip" aria-label="Viewing depths">
      <HelpHeading title={`Viewing depths: ${summary}`} content={help.depth} />
      {children}
      <div className="row">
        <button
          onClick={() =>
            void send({ type: "set_depth", depth: { mode: "all" } }).catch(
              () => {},
            )
          }
        >
          All depths
        </button>
        <button aria-label="Previous frame" onClick={() => frame(current - 1)}>
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
        <button aria-label="Next frame" onClick={() => frame(current + 1)}>
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
            if (e.key.startsWith("Arrow")) {
              e.stopPropagation();
              frame(slider);
            }
          }}
        />
      </div>
      <ExactForm
        labels={["Window first", "Window last"]}
        values={
          a.depth.mode === "window" ? [a.depth.first, a.depth.last] : bounds
        }
        button="View depth window"
        onApply={(v) =>
          void send({
            type: "set_depth",
            depth: { mode: "window", first: v[0], last: v[1] },
          }).catch(() => {})
        }
      />
    </section>
  );
}
