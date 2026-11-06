import { useEffect, useMemo, useRef, useState } from "react";
import { histogram, layerRange } from "./spatialRenderer";
import { moveWindow } from "./levels";

export function LevelsControl({
  values,
  levels,
  onChange,
  onReset,
}: {
  values: (number | null)[];
  levels: [number, number];
  onChange: (levels: [number, number]) => void;
  onReset: () => void;
}) {
  const range = layerRange(values);
  const min = Math.min(range[0], levels[0]),
    max = Math.max(range[1], levels[1]);
  const width = max - min || 1;
  const domain: [number, number] = [min, min + width];
  const [draft, setDraft] = useState<[number, number]>(levels);
  const current = useRef(draft);
  const box = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  useEffect(() => {
    if (!dragging.current) {
      current.current = levels;
      setDraft(levels);
    }
  }, [levels[0], levels[1]]);
  const bars = useMemo(
    () => histogram(values, min, min + width),
    [values, min, width],
  );
  const tallest = Math.max(...bars, 1);
  const positions = draft.map((x) =>
    Math.max(0, Math.min(100, ((x - min) / width) * 100)),
  );
  const drag = (
    kind: "low" | "high" | "window",
    event: React.PointerEvent<HTMLElement>,
  ) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragging.current = true;
    const start = event.clientX,
      initial = current.current,
      element = event.currentTarget;
    const epsilon = width / 10000;
    const move = (e: PointerEvent) => {
      const delta =
        ((e.clientX - start) / (box.current?.clientWidth || 1)) * width;
      const next: [number, number] =
        kind === "window"
          ? moveWindow(initial, delta, domain)
          : kind === "low"
            ? [
                Math.max(
                  min,
                  Math.min(initial[1] - epsilon, initial[0] + delta),
                ),
                initial[1],
              ]
            : [
                initial[0],
                Math.min(
                  domain[1],
                  Math.max(initial[0] + epsilon, initial[1] + delta),
                ),
              ];
      current.current = next;
      setDraft(next);
    };
    const end = () => {
      element.removeEventListener("pointermove", move);
      element.removeEventListener("pointerup", end);
      element.removeEventListener("pointercancel", end);
      dragging.current = false;
      onChange(current.current);
    };
    element.addEventListener("pointermove", move);
    element.addEventListener("pointerup", end);
    element.addEventListener("pointercancel", end);
  };
  const setBound = (which: 0 | 1, value: number) => {
    if (
      !Number.isFinite(value) ||
      (which === 0 ? value >= draft[1] : value <= draft[0])
    )
      return;
    const next: [number, number] =
      which === 0 ? [value, draft[1]] : [draft[0], value];
    current.current = next;
    setDraft(next);
    onChange(next);
  };
  return (
    <div className="levels-control">
      <div className="levels-heading">
        <strong>Levels</strong>
        <button type="button" onClick={onReset}>
          Reset
        </button>
      </div>
      <div className="levels-histogram" ref={box}>
        <svg
          viewBox={`0 0 ${bars.length} 100`}
          preserveAspectRatio="none"
          aria-label="Preview intensity histogram"
        >
          {bars.map((n, i) => (
            <rect
              key={i}
              x={i}
              width=".85"
              y={100 - (n / tallest) * 100}
              height={(n / tallest) * 100}
            />
          ))}
        </svg>
        <div
          className="levels-window"
          style={{
            left: `${positions[0]}%`,
            width: `${positions[1] - positions[0]}%`,
          }}
          onPointerDown={(e) => drag("window", e)}
          title="Drag to move both levels"
        />
        {([0, 1] as const).map((i) => (
          <button
            key={i}
            type="button"
            className="levels-handle"
            style={{ left: `${positions[i]}%` }}
            aria-label={i ? "Upper level" : "Lower level"}
            role="slider"
            aria-valuemin={min}
            aria-valuemax={min + width}
            aria-valuenow={draft[i]}
            onPointerDown={(e) => drag(i ? "high" : "low", e)}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                setBound(
                  i,
                  draft[i] + (width / 100) * (e.key === "ArrowRight" ? 1 : -1),
                );
              }
            }}
          />
        ))}
      </div>
      <div className="levels-gradient" />
      <div className="levels-values">
        {([0, 1] as const).map((i) => (
          <label key={i}>
            {i ? "Upper" : "Lower"}
            <input
              key={draft[i]}
              type="number"
              aria-label={i ? "Upper level value" : "Lower level value"}
              defaultValue={Number(draft[i].toPrecision(6))}
              onBlur={(e) => {
                const input = e.currentTarget;
                const value = input.valueAsNumber;
                if (
                  !Number.isFinite(value) ||
                  (i === 0 ? value >= draft[1] : value <= draft[0])
                ) {
                  input.value = String(Number(draft[i].toPrecision(6)));
                } else setBound(i, value);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") e.currentTarget.blur();
              }}
            />
          </label>
        ))}
      </div>
      <small>Drag a handle to adjust · drag inside to move both</small>
    </div>
  );
}
