import { useRef, useState } from "react";
import { gestureBounds } from "./gesture";
export type Range = [number, number];
type Props = {
  xRange: Range;
  yRange: Range;
  selection?: number[];
  onSelect: (bounds: number[]) => void;
  onClick?: (x: number, y: number) => void;
  onZoom?: (range: Range) => void;
  mode?: "x" | "xy";
  label?: string;
  reverseY?: boolean;
  image?: boolean;
};
export function SelectionOverlay({
  xRange,
  yRange,
  selection,
  onSelect,
  onClick,
  onZoom,
  mode = "x",
  label = "Plot selection",
  reverseY = false,
  image = false,
}: Props) {
  const drag = useRef<{
    start: number[];
    action: string;
    selection?: number[];
  } | null>(null);
  const [preview, setPreview] = useState<number[] | null>(null);
  const shown = preview || selection;
  const coords = (e: React.PointerEvent<SVGSVGElement>) => {
    const b = e.currentTarget.getBoundingClientRect();
    return [
      xRange[0] +
        Math.max(0, Math.min(1, (e.clientX - b.x) / b.width)) *
          (xRange[1] - xRange[0]),
      reverseY
        ? yRange[0] +
          Math.max(0, Math.min(1, (e.clientY - b.y) / b.height)) *
            (yRange[1] - yRange[0])
        : yRange[1] -
          Math.max(0, Math.min(1, (e.clientY - b.y) / b.height)) *
            (yRange[1] - yRange[0]),
    ];
  };
  const px = (x: number) => (100 * (x - xRange[0])) / (xRange[1] - xRange[0]),
    py = (y: number) =>
      (100 * (reverseY ? y - yRange[0] : yRange[1] - y)) /
      (yRange[1] - yRange[0]);
  return (
    <svg
      data-testid="selection-overlay"
      data-x-range={xRange.join(",")}
      aria-label={label}
      className={`selection-overlay ${image ? "image" : ""}`}
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      onPointerDown={(e) => {
        e.preventDefault();
        e.currentTarget.setPointerCapture(e.pointerId);
        drag.current = {
          start: coords(e),
          action:
            (e.target as Element).getAttribute("data-action") === "move" &&
            !e.shiftKey
              ? "draw"
              : (e.target as Element).getAttribute("data-action") || "draw",
          selection: selection?.slice(),
        };
      }}
      onPointerMove={(e) => {
        if (drag.current)
          setPreview(
            gestureBounds(drag.current, coords(e), mode, xRange, yRange),
          );
      }}
      onPointerCancel={() => {
        drag.current = null;
        setPreview(null);
      }}
      onPointerUp={(e) => {
        const d = drag.current;
        if (!d) return;
        drag.current = null;
        setPreview(null);
        const end = coords(e);
        if (
          Math.hypot(end[0] - d.start[0], end[1] - d.start[1]) < 1e-10 &&
          onClick
        ) {
          onClick(...(end as [number, number]));
          return;
        }
        const b = gestureBounds(d, end, mode, xRange, yRange);
        onSelect(b);
      }}
      onWheel={(e) => {
        if (!onZoom || !(e.ctrlKey || e.metaKey)) return;
        e.preventDefault();
        const b = e.currentTarget.getBoundingClientRect(),
          c =
            xRange[0] + ((e.clientX - b.x) / b.width) * (xRange[1] - xRange[0]),
          f = e.deltaY > 0 ? 1.2 : 1 / 1.2;
        onZoom([c + (xRange[0] - c) * f, c + (xRange[1] - c) * f]);
      }}
    >
      <rect width="100" height="100" fill="transparent" />
      {shown && (
        <g stroke="#b78322" strokeWidth=".6">
          <rect
            data-action="move"
            x={px(shown[0])}
            y={mode === "xy" ? Math.min(py(shown[2]), py(shown[3])) : 0}
            width={Math.max(0.2, px(shown[1]) - px(shown[0]))}
            height={
              mode === "xy"
                ? Math.max(0.2, Math.abs(py(shown[2]) - py(shown[3])))
                : 100
            }
            fill="#e4ad3822"
            style={{ cursor: "move" }}
          />
          <line
            data-action="low"
            x1={px(shown[0])}
            x2={px(shown[0])}
            y1={0}
            y2={100}
            strokeWidth="2"
          />
          <line
            data-action="high"
            x1={px(shown[1])}
            x2={px(shown[1])}
            y1={0}
            y2={100}
            strokeWidth="2"
          />
          {mode === "xy" && (
            <>
              <line
                data-action="bottom"
                x1={px(shown[0])}
                x2={px(shown[1])}
                y1={py(shown[2])}
                y2={py(shown[2])}
                strokeWidth="2"
              />
              <line
                data-action="top"
                x1={px(shown[0])}
                x2={px(shown[1])}
                y1={py(shown[3])}
                y2={py(shown[3])}
                strokeWidth="2"
              />
            </>
          )}
        </g>
      )}
    </svg>
  );
}
