// Both candidates consume precisely the same registered scalar fixture.
import Plotly from "plotly.js-dist-min";
import vtkImageData from "@kitware/vtk.js/Common/DataModel/ImageData";
import vtkDataArray from "@kitware/vtk.js/Common/Core/DataArray";
import vtkVolumeMapper from "@kitware/vtk.js/Rendering/Core/VolumeMapper";
import { createRoot } from "react-dom/client";
import { useEffect, useRef } from "react";
const fixture = {
  x: [0, 1, 2],
  y: [0, 1, 2],
  z: [0, 10, 30, 60],
  layers: [1, 2, 3].map((k) =>
    Array.from({ length: 36 }, (_, i) => (i === 0 ? null : k * (i + 1))),
  ),
};
function Probe() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const run = async () => {
      const image = vtkImageData.newInstance();
      image.setDimensions(3, 3, 4);
      image.setSpacing([1, 1, 20]);
      image
        .getPointData()
        .setScalars(
          vtkDataArray.newInstance({
            values: Float32Array.from(fixture.layers[0].map((v) => v ?? NaN)),
          }),
        );
      const mapper = vtkVolumeMapper.newInstance();
      mapper.setInputData(image);
      const vtkZ = fixture.z.map((_, i) => image.indexToWorld([0, 0, i])[2]);
      const traces = fixture.layers.map((values, k) => {
        const x: number[] = [],
          y: number[] = [],
          z: number[] = [];
        fixture.z.forEach((zz) =>
          fixture.y.forEach((yy) =>
            fixture.x.forEach((xx) => {
              x.push(xx);
              y.push(yy);
              z.push(zz);
            }),
          ),
        );
        return {
          type: "volume",
          x,
          y,
          z,
          value: values,
          isomin: 1,
          isomax: 108,
          opacity: 0.12,
          surface: { count: 6 },
          showscale: false,
          name: `Layer ${k + 1}`,
        };
      });
      const start = performance.now();
      await Plotly.newPlot(
        ref.current,
        traces,
        {
          width: 700,
          height: 450,
          scene: { aspectmode: "data" },
          margin: { t: 10, b: 10, l: 10, r: 10 },
        },
        { displayModeBar: false },
      );
      const times: number[] = [];
      for (let i = 0; i < 30; i++) {
        const t = performance.now();
        await Plotly.relayout(ref.current, {
          "scene.camera.eye": { x: 1.3 + i / 100, y: 1.3, z: 1.3 },
        });
        await new Promise(requestAnimationFrame);
        times.push(performance.now() - t);
      }
      (window as any).spatialProbe = {
        fixture,
        vtkZ,
        plotlyZ: traces[0].z.filter((_, i) => i % 9 === 0),
        bytes: JSON.stringify(fixture).length,
        readyMs: performance.now() - start,
        cameraMs: times.sort((a, b) => a - b),
        vtkInputClass: mapper.getInputData().getClassName(),
      };
      mapper.delete();
      image.delete();
    };
    void run();
    return () => Plotly.purge(ref.current);
  }, []);
  return <div ref={ref} />;
}
createRoot(document.getElementById("root")!).render(<Probe />);
