declare module "plotly.js-dist-min" {
  const Plotly: any;
  export default Plotly;
}
declare module "@kitware/vtk.js/Rendering/Core/CubeAxesActor" {
  const vtkCubeAxesActor: any;
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
