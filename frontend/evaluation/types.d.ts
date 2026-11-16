declare module "plotly.js-dist-min" {
  const Plotly: {
    newPlot(
      element: HTMLElement | null,
      data: unknown[],
      layout: object,
      options: object,
    ): Promise<void>;
    react(
      element: HTMLElement,
      data: unknown[],
      layout: object,
      options: object,
    ): Promise<void>;
    relayout(element: HTMLElement | null, layout: object): Promise<void>;
    purge(element: HTMLElement | null): void;
    Plots: { resize(element: HTMLElement): void };
  };
  export default Plotly;
}
declare module "@kitware/vtk.js/Rendering/Core/CubeAxesActor" {
  import type { vtkActor } from "@kitware/vtk.js/Rendering/Core/Actor";
  type TextStyle = { fontColor: string; fontFamily: string; fontSize: number };
  type CubeAxes = vtkActor & {
    setCamera(camera: unknown): void;
    setDataBounds(...bounds: number[]): void;
    setAxisLabels(x: string, y: string, z: string): void;
    setAxisTextStyle(style: TextStyle): void;
    setTickTextStyle(style: TextStyle): void;
    setAxisTitlePixelOffset(offset: number): void;
    setGenerateTicks(
      generate: (bounds: number[]) => {
        ticks: number[][];
        tickStrings: string[][];
      },
    ): void;
  };
  const vtkCubeAxesActor: { newInstance(): CubeAxes };
  export default vtkCubeAxesActor;
}
declare module "d3-scale" {
  export function scaleLinear(): {
    domain(values: number[]): {
      ticks(count: number): number[];
      tickFormat(count: number, specifier: string): (value: number) => string;
    };
  };
}
