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

/** Serialize the captured spectrum with its provenance and original mass bins. */
export function spectrumCsv(
  panel: Panel,
  filename: string,
  result: SpectrumResult | null,
  exportedAt: Date,
): string {
  const field = (value: string | number | null) => {
    const text = String(value ?? "");
    return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  };
  const rows: (string | number | null)[][] = [
    ["# ToFScope mass spectrum export", ""],
    ["# Exported at (UTC)", exportedAt.toISOString()],
    ["# Acquisition", filename],
    ["# Spectrum", result ? "ROI" : "Total sum"],
  ];
  if (result) {
    const [x0, x1, y0, y1] = result.roi;
    rows.push(
      ["# ROI X pixels", `${x0}–${x1}`],
      ["# ROI Y pixels", `${y0}–${y1}`],
      ["# Frames", `${result.frames[0]}–${result.frames[1]}`],
    );
  }
  rows.push([], ["m/z", "intensity"]);
  const intensities = panel.series?.[0]?.values ?? [];
  panel.axes[0].values.forEach((mass, i) =>
    rows.push([mass, intensities[i] ?? null]),
  );
  return rows.map((row) => row.map(field).join(",")).join("\r\n") + "\r\n";
}

/** Download the original-resolution values currently shown in the spectrum. */
export function downloadSpectrumCsv(
  panel: Panel,
  filename: string,
  result: SpectrumResult | null,
): void {
  const csv = spectrumCsv(panel, filename, result, new Date());
  const url = URL.createObjectURL(
    new Blob([csv], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `tofscope-${result ? "roi" : "sum"}-spectrum.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
