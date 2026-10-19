import type { CurveStyle } from "../plots/curveStyle";

export function CurveMarker({ style }: { style: CurveStyle }) {
  return (
    <span
      className="curve-marker"
      aria-hidden="true"
      style={{
        borderTopColor: style.color,
        borderTopStyle: style.dash,
      }}
    />
  );
}
