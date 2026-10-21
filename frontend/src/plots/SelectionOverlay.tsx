import { useEffect, useRef, useState, type CSSProperties } from "react";
import { gestureBounds, panRange } from "./gesture";
import type { Panel } from "../api/client";
export type Range = [number, number];
type Props = {
  xRange: Range;
  insets?: { left: number; right: number; top: number; bottom: number };
  onHover?: (x: number | null, y?: number) => void;
  panDomain?: Range;
  yRange: Range;
  selection?: number[];
  selectionWindows?: Range[];
  selectedWindow?: number;
  onWindowSelect?: (index: number) => void;
  markers?: number[];
  onSelect: (bounds: number[]) => void;
  onClick?: (x: number, y: number, unitsPerPixel: number) => void;
  onZoom?: (range: Range) => void;
  mode?: "x" | "xy" | "y";
  label?: string;
  reverseY?: boolean;
  image?: boolean;
  palette?: Panel["palette"];
  selectionMode?: "select" | "zoom" | "pan";
};
function SelectionEdge({
  action,
  appearance,
  x1,
  x2,
  y1,
  y2,
}: {
  action: string;
  appearance?: { color: string; halo: string };
  x1: number;
  x2: number;
  y1: number;
  y2: number;
}) {
  const endpoints = { x1, x2, y1, y2 };
  return (
    <>
      {appearance && (
        <line
          {...endpoints}
          data-selection-halo
          stroke={appearance!.halo}
          strokeWidth="3"
          vectorEffect="non-scaling-stroke"
          pointerEvents="none"
        />
      )}
      <line
        {...endpoints}
        data-selection-edge
        stroke={appearance?.color ?? "#b78322"}
        strokeWidth={appearance ? "1.5" : "1"}
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
  insets,
  onHover,
  panDomain,
  selection,
  selectionWindows,
  selectedWindow,
  onWindowSelect,
  markers,
  onSelect,
  onClick,
  onZoom,
  mode = "x",
  label = "Plot selection",
  reverseY = false,
  image = false,
  palette,
  selectionMode = "select",
}: Props) {
  const appearance = image
    ? palette === "magma"
      ? { color: "#22e6ee", halo: "#095a63" }
      : palette === "gray"
        ? { color: "#00b8a9", halo: "#064d49" }
        : { color: "#f02ec4", halo: "#64104e" }
    : undefined;
  const surface = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const element = surface.current;
    if (!element || !onZoom) return;
    const wheel = (event: WheelEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      // React's delegated wheel listener is passive; native cancellation must be explicit.
      event.preventDefault();
      const bounds = element.getBoundingClientRect();
      const center =
        xRange[0] +
        ((event.clientX - bounds.x) / bounds.width) * (xRange[1] - xRange[0]);
      const factor = event.deltaY > 0 ? 1.2 : 1 / 1.2;
      onZoom([
        center + (xRange[0] - center) * factor,
        center + (xRange[1] - center) * factor,
      ]);
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, [onZoom, xRange[0], xRange[1]]);
  const drag = useRef<{
    start: number[];
    pointerStart: [number, number];
    viewRange: Range;
    panStarted: boolean;
    action: string;
    selection?: number[];
    selectionWindows?: Range[];
    selectedWindow?: number;
    onWindowSelect?: (index: number) => void;
  } | null>(null);
  const [preview, setPreview] = useState<number[] | null>(null);
  const [hoverX, setHoverX] = useState<number | null>(null);
  const current = preview || selection;
  const shown =
    current && mode === "y"
      ? [xRange[0], xRange[1], current[2], current[3]]
      : current;
  const panTo = (
    clientX: number,
    start: {
      pointerStart: [number, number];
      viewRange: Range;
      panStarted: boolean;
    },
  ) => {
    const width = surface.current?.getBoundingClientRect().width;
    if (!width) return;
    if (!start.panStarted && Math.abs(clientX - start.pointerStart[0]) < 4)
      return;
    start.panStarted = true;
    const shift =
      (-(clientX - start.pointerStart[0]) / width) *
      (start.viewRange[1] - start.viewRange[0]);
    onZoom?.(panRange(start.viewRange, shift, panDomain ?? start.viewRange));
  };
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
      ref={surface}
      data-testid="selection-overlay"
      data-x-range={xRange.join(",")}
      aria-label={label}
      className={`selection-overlay ${image ? "image" : ""}`}
      style={
        insets
          ? ({
              ...insets,
              cursor: selectionMode === "pan" ? "grab" : undefined,
              width: `calc(100% - ${insets.left + insets.right}px)`,
              height: `calc(100% - ${insets.top + insets.bottom}px)`,
            } as CSSProperties)
          : undefined
      }
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      onPointerDown={(e) => {
        e.preventDefault();
        const windowTarget = (e.target as Element).closest(
          "[data-window-index]",
        );
        if (windowTarget && selectionMode !== "pan") {
          onWindowSelect?.(
            Number(windowTarget.getAttribute("data-window-index")),
          );
          return;
        }
        e.currentTarget.setPointerCapture(e.pointerId);
        drag.current = {
          start: coords(e),
          pointerStart: [e.clientX, e.clientY],
          viewRange: [xRange[0], xRange[1]],
          panStarted: false,
          action:
            (e.target as Element).getAttribute("data-action") === "move" &&
            !e.shiftKey
              ? "draw"
              : (e.target as Element).getAttribute("data-action") || "draw",
          selection: selection?.slice(),
        };
      }}
      onPointerLeave={() => {
        setHoverX(null);
        onHover?.(null);
      }}
      onPointerMove={(e) => {
        if (onHover) {
          const [x, y] = coords(e);
          setHoverX(x);
          onHover(x, y);
        }
        if (drag.current) {
          if (selectionMode === "pan") panTo(e.clientX, drag.current);
          else
            setPreview(
              gestureBounds(drag.current, coords(e), mode, xRange, yRange),
            );
        }
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
        if (selectionMode === "pan") {
          panTo(e.clientX, d);
          return;
        }
        const end = coords(e);
        const isClick =
          Math.hypot(
            e.clientX - d.pointerStart[0],
            e.clientY - d.pointerStart[1],
          ) < 4;
        if (isClick && onClick) {
          onClick(
            end[0],
            end[1],
            (xRange[1] - xRange[0]) /
              e.currentTarget.getBoundingClientRect().width,
          );
          return;
        }
        // Without a picking action, clicks must not collapse zoom or selection bounds.
        if (isClick) return;
        const b = gestureBounds(d, end, mode, xRange, yRange);
        if (selectionMode === "zoom") onZoom?.([b[0], b[1]]);
        else onSelect(b);
      }}
    >
      <rect width="100" height="100" fill="transparent" />
      {hoverX !== null && (
        <line
          x1={px(hoverX)}
          x2={px(hoverX)}
          y1={0}
          y2={100}
          stroke="#526e7c"
          strokeDasharray="3 3"
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
          pointerEvents="none"
        />
      )}
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
      {selectionWindows?.map(
        (bounds, index) =>
          index !== selectedWindow &&
          bounds.every(Number.isFinite) && (
            <g
              key={index}
              data-draft-window={index}
              data-window-index={index}
              role="button"
              tabIndex={0}
              aria-label={`Select spectrum interval ${index + 1}`}
              style={{ cursor: "pointer" }}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onWindowSelect?.(index);
                }
              }}
            >
              <rect
                x={px(bounds[0])}
                y={0}
                width={Math.max(0.2, px(bounds[1]) - px(bounds[0]))}
                height={100}
                fill="#d18c2412"
                stroke="#a87a2c"
                strokeWidth="1"
                strokeDasharray="4 3"
                vectorEffect="non-scaling-stroke"
              />
              <text
                x={(px(bounds[0]) + px(bounds[1])) / 2}
                y={6}
                fontSize="4"
                textAnchor="middle"
                fill="#87601b"
                pointerEvents="none"
              >
                {index + 1}
              </text>
            </g>
          ),
      )}
      {shown && (
        <g data-draft-window={selectedWindow}>
          <rect
            data-action="move"
            x={px(shown[0])}
            y={mode !== "x" ? Math.min(py(shown[2]), py(shown[3])) : 0}
            width={Math.max(0.2, px(shown[1]) - px(shown[0]))}
            height={
              mode !== "x"
                ? Math.max(0.2, Math.abs(py(shown[2]) - py(shown[3])))
                : 100
            }
            fill={image ? "transparent" : "#e4ad3810"}
            stroke={image || mode === "y" ? "none" : "#b78322"}
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
            style={{ cursor: selectionMode === "pan" ? "grab" : "move" }}
          />
          {selectedWindow !== undefined && (
            <text
              x={(px(shown[0]) + px(shown[1])) / 2}
              y={6}
              fontSize="4"
              textAnchor="middle"
              fill="#87601b"
              pointerEvents="none"
            >
              {selectedWindow + 1}
            </text>
          )}
          {mode !== "y" && (
            <>
              <SelectionEdge
                appearance={appearance}
                action="low"
                x1={px(shown[0])}
                x2={px(shown[0])}
                y1={mode !== "x" ? Math.min(py(shown[2]), py(shown[3])) : 0}
                y2={mode !== "x" ? Math.max(py(shown[2]), py(shown[3])) : 100}
              />
              <SelectionEdge
                appearance={appearance}
                action="high"
                x1={px(shown[1])}
                x2={px(shown[1])}
                y1={mode !== "x" ? Math.min(py(shown[2]), py(shown[3])) : 0}
                y2={mode !== "x" ? Math.max(py(shown[2]), py(shown[3])) : 100}
              />
            </>
          )}
          {mode !== "x" && (
            <>
              <SelectionEdge
                appearance={appearance}
                action="bottom"
                x1={px(shown[0])}
                x2={px(shown[1])}
                y1={py(shown[2])}
                y2={py(shown[2])}
              />
              <SelectionEdge
                appearance={appearance}
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
