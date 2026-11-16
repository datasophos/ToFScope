import type { components } from "../api/generated";
import type { Analysis, Panel } from "../api/client";

export type SpectrumResult = components["schemas"]["SpectrumResult"];

export function spectrumIsOutOfDate(
  result: SpectrumResult,
  analysis: Analysis,
): boolean {
  const depth = analysis.depth;
  const frames =
    depth.mode === "frame"
      ? [depth.index, depth.index]
      : depth.mode === "window"
        ? [depth.first, depth.last]
        : [0, analysis.shape[0] - 1];
  return (
    result.roi.some((value, index) => value !== analysis.roi[index]) ||
    result.frames.some((value, index) => value !== frames[index])
  );
}

export function spectrumSelection(result: SpectrumResult): string {
  const [x0, x1, y0, y1] = result.roi;
  const [first, last] = result.frames;
  return `x ${x0}–${x1}, y ${y0}–${y1}, frames ${first}–${last}`;
}

export function subvolumePanel(base: Panel, result: SpectrumResult): Panel {
  return {
    ...base,
    content_version: result.job_id,
    aggregation: "raw-event subvolume spectrum",
    series: [
      {
        signal_id: "subvolume-spectrum",
        style_index: 0,
        label: `Selected spectrum · ${spectrumSelection(result)}`,
        values: result.values,
        coverage: result.values.map(() => true),
      },
    ],
  };
}
