import { useRef, useState } from "react";
import { gestureBounds } from "./gesture";
export type Range = [number, number];
type Props = {
  xRange: Range;
  yRange: Range;
  selection?: number[];
  markers?: number[];
  onSelect: (bounds: number[]) => void;
  onClick?: (x: number, y: number) => void;
  onZoom?: (range: Range) => void;
  mode?: "x" | "xy";
  label?: string;
  reverseY?: boolean;
  image?: boolean;
  selectionMode?: "select" | "zoom";
};
function SelectionEdge({
  action,
  x1,
  x2,
  y1,
  y2,
}: {
  action: string;
  x1: number;
  x2: number;
  y1: number;
  y2: number;
}) {
  const endpoints = { x1, x2, y1, y2 };
  return (
    <>
      <line
        {...endpoints}
        stroke="#b78322"
        strokeWidth="1"
        vectorEffect="non-scaling-stroke"
        pointerEvents="none"
      />
      <line
        {...endpoints}
        data-action={action}
        stroke="transparent"
        strokeWidth="12"
        vectorEffect="non-scaling-stroke"
        pointerEvents="stroke"
        style={{
          cursor:
            action === "top" || action === "bottom" ? "ns-resize" : "ew-resize",
        }}
      />
    </>
  );
}
export function SelectionOverlay({
  xRange,
  yRange,
  selection,
  markers,
  onSelect,
  onClick,
  onZoom,
  mode = "x",
  label = "Plot selection",
  reverseY = false,
  image = false,
  selectionMode = "select",
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
        if (selectionMode === "zoom") onZoom?.([b[0], b[1]]);
        else onSelect(b);
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
      {markers
        ?.filter((x) => x >= xRange[0] && x <= xRange[1])
        .map((x) => (
          <line
            key={x}
            x1={px(x)}
            x2={px(x)}
            y1={0}
            y2={100}
            stroke="#b78322"
            strokeDasharray="3 3"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
        ))}
      {shown && (
        <g>
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
            fill="#e4ad3810"
            stroke="#b78322"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
            style={{ cursor: "move" }}
          />
          <SelectionEdge
            action="low"
            x1={px(shown[0])}
            x2={px(shown[0])}
            y1={0}
            y2={100}
          />
          <SelectionEdge
            action="high"
            x1={px(shown[1])}
            x2={px(shown[1])}
            y1={0}
            y2={100}
          />
          {mode === "xy" && (
            <>
              <SelectionEdge
                action="bottom"
                x1={px(shown[0])}
                x2={px(shown[1])}
                y1={py(shown[2])}
                y2={py(shown[2])}
              />
              <SelectionEdge
                action="top"
                x1={px(shown[0])}
                x2={px(shown[1])}
                y1={py(shown[3])}
                y2={py(shown[3])}
              />
            </>
          )}
        </g>
      )}
    </svg>
  );
}
