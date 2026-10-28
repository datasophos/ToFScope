import { describe, expect, it } from "vitest";
import { canRenderVtkStyles, prepareVtkPreview } from "./vtkPreview";
import { defaultLayer, type VolumeData } from "./spatialRenderer";

describe("vtk threshold admission", () => {
  it("falls back when resampling drops a narrow peak below the original cutoff", () => {
    const values = [1, 1, 1, 1, 8, 9, 10, 10, 1, 1, 1, 1];
    const data = {
      x: [0, 1],
      y: [0, 1],
      z: [0, 1, 10],
      layers: [
        { signal_id: "a", label: "a", values, coverage: Array(12).fill(1) },
      ],
    } as VolumeData;
    const preview = prepareVtkPreview(data);
    expect(preview.kind).toBe("vtk");
    if (preview.kind !== "vtk") return;
    expect(
      Math.max(...(preview.data.layers[0].values as number[])),
    ).toBeLessThan(10);
    const styles = [{ ...defaultLayer("a"), percentile: 80 }];
    expect(canRenderVtkStyles(data, styles, false, preview.data)).toBe(false);
    expect(canRenderVtkStyles(data, styles, true, preview.data)).toBe(false);
  });
  it("uses the point renderer when a percentile cutoff equals the maximum", () => {
    const data = {
      layers: [{ signal_id: "a", values: [0, 2, 2, 2, 2, 2, 2, 2] }],
    } as VolumeData;
    expect(
      canRenderVtkStyles(
        data,
        [{ ...defaultLayer("a"), percentile: 70 }],
        false,
      ),
    ).toBe(false);
    expect(
      canRenderVtkStyles(
        data,
        [{ ...defaultLayer("a"), percentile: 70 }],
        true,
      ),
    ).toBe(false);
  });
  it("allows a threshold below the maximum", () => {
    const data = {
      layers: [{ signal_id: "a", values: [0, 1, 2, 3, 4, 5, 6, 7] }],
    } as VolumeData;
    expect(
      canRenderVtkStyles(
        data,
        [{ ...defaultLayer("a"), percentile: 70 }],
        false,
      ),
    ).toBe(true);
  });
});
