import { describe, expect, it } from "vitest";
import { vtkColorStops } from "./vtkColors";
describe("vtk layer colors", () => {
  it("reverses each colormap without changing the original ramp", () => {
    const forward = vtkColorStops("Reds");
    const reversed = vtkColorStops("Reds", true);
    expect(reversed[0]).toEqual([0, 178, 10, 28]);
    expect(reversed.at(-1)).toEqual([1, 220, 220, 220]);
    expect(reversed[1]).toEqual([0.6, 245, 160, 105]);
    expect(vtkColorStops("Reds")).toEqual(forward);
  });
  it("preserves Plotly Reds and Blues stops for saved layer styles", () => {
    expect(vtkColorStops("Reds")[0]).toEqual([0, 220, 220, 220]);
    expect(vtkColorStops("Reds").at(-1)).toEqual([1, 178, 10, 28]);
    expect(vtkColorStops("Blues")[0]).toEqual([0, 5, 10, 172]);
  });
  it("gives Plasma and Purples their own recognizable colors", () => {
    expect(vtkColorStops("Plasma")[0]).toEqual([0, 13, 8, 135]);
    expect(vtkColorStops("Plasma").at(-1)).toEqual([1, 240, 249, 33]);
    expect(vtkColorStops("Purples")[0]).toEqual([0, 252, 251, 253]);
    expect(vtkColorStops("Purples").at(-1)).toEqual([1, 63, 0, 125]);
    expect(vtkColorStops("Plasma")).not.toEqual(vtkColorStops("Reds"));
    expect(vtkColorStops("Purples")).not.toEqual(vtkColorStops("Reds"));
  });
});
