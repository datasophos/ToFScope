import { formatNumber } from "../shared/numbers";
/** Shared renderer/gesture margins keep physical selections aligned with labels. */
export function plotInsets(kind: "image" | "line") {
  return kind === "image"
    ? { left: 62, right: 22, top: 18, bottom: 66 }
    : { left: 76, right: 24, top: 20, bottom: 56 };
}
export function axisTitle(axis: { name: string; unit: string }) {
  if (axis.name === "frame") return "Frame";
  const name =
    axis.name === "m/z"
      ? "m/z"
      : axis.name.charAt(0).toUpperCase() + axis.name.slice(1);
  return axis.unit && axis.unit !== axis.name ? `${name} (${axis.unit})` : name;
}
export function formatTick(value: number) {
  if (!Number.isFinite(value)) return "";
  if (value === 0) return "0";
  const rounded = Number(value.toPrecision(5));
  return Math.abs(value) >= 1e5 || Math.abs(value) < 1e-3
    ? rounded.toExponential().replace("e+", "e")
    : String(rounded);
}

export function formatFrameTick(value: number) {
  return Number.isInteger(value) ? String(value) : "";
}
export function formatPosition(
  value: number,
  axis: { unit: string; values: number[] },
) {
  return axis.unit === "frame"
    ? String(
        Math.round(
          Math.max(
            axis.values[0] ?? value,
            Math.min(axis.values.at(-1) ?? value, value),
          ),
        ),
      )
    : formatNumber(value);
}
