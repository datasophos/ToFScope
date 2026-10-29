import { colormaps } from "../plots/colormaps";
export type ColorStop = [number, number, number, number];
// Named ramps use the same colors for the vtk transfer function and legend.
const reds: ColorStop[] = [
  [0, 220, 220, 220],
  [0.2, 245, 195, 157],
  [0.4, 245, 160, 105],
  [1, 178, 10, 28],
];
const named: Record<string, ColorStop[]> = {
  Reds: reds,
  Plasma: [
    [0, 13, 8, 135],
    [0.25, 126, 3, 168],
    [0.5, 204, 71, 120],
    [0.75, 248, 149, 64],
    [1, 240, 249, 33],
  ],
  Purples: [
    [0, 252, 251, 253],
    [0.125, 239, 237, 245],
    [0.25, 218, 218, 235],
    [0.375, 188, 189, 220],
    [0.5, 158, 154, 200],
    [0.625, 128, 125, 186],
    [0.75, 106, 81, 163],
    [0.875, 84, 39, 143],
    [1, 63, 0, 125],
  ],
  Blues: [
    [0, 5, 10, 172],
    [0.35, 40, 60, 190],
    [0.5, 70, 100, 245],
    [0.6, 90, 120, 245],
    [0.7, 106, 137, 247],
    [1, 220, 220, 220],
  ],
  Greens: [
    [0, 0, 68, 27],
    [0.125, 0, 109, 44],
    [0.25, 35, 139, 69],
    [0.375, 65, 171, 93],
    [0.5, 116, 196, 118],
    [0.625, 161, 217, 155],
    [0.75, 199, 233, 192],
    [0.875, 229, 245, 224],
    [1, 247, 252, 245],
  ],
};
export function vtkColorStops(name: string, reversed = false): ColorStop[] {
  const table = colormaps[name.toLowerCase() as keyof typeof colormaps];
  const stops: ColorStop[] = table
    ? Array.from({ length: 256 }, (_, i) => [
        i / 255,
        table[i * 3],
        table[i * 3 + 1],
        table[i * 3 + 2],
      ])
    : (named[name] ?? reds);
  return reversed
    ? stops
        .slice()
        .reverse()
        .map(([x, r, g, b]) => [1 - x, r, g, b])
    : stops;
}
