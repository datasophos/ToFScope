import { useEffect, useMemo, useRef } from "react";
import "@kitware/vtk.js/Rendering/Profiles/Volume";
import "@kitware/vtk.js/Rendering/Profiles/Geometry";
import vtkCubeAxesActor from "@kitware/vtk.js/Rendering/Core/CubeAxesActor";
import vtkGenericRenderWindow from "@kitware/vtk.js/Rendering/Misc/GenericRenderWindow";
import vtkImageData from "@kitware/vtk.js/Common/DataModel/ImageData";
import vtkDataArray from "@kitware/vtk.js/Common/Core/DataArray";
import vtkVolume from "@kitware/vtk.js/Rendering/Core/Volume";
import { ColorMixPreset } from "@kitware/vtk.js/Rendering/Core/VolumeProperty/Constants";
import vtkVolumeMapper from "@kitware/vtk.js/Rendering/Core/VolumeMapper";
import vtkColorTransferFunction from "@kitware/vtk.js/Rendering/Core/ColorTransferFunction";
import vtkPiecewiseFunction from "@kitware/vtk.js/Common/DataModel/PiecewiseFunction";
import vtkPolyData from "@kitware/vtk.js/Common/DataModel/PolyData";
import vtkMapper from "@kitware/vtk.js/Rendering/Core/Mapper";
import vtkActor from "@kitware/vtk.js/Rendering/Core/Actor";
import { buildVtkPoints } from "./vtkPoints";
import { scaleLinear } from "d3-scale";
import { vtkColorStops } from "./vtkColors";
import type { VtkVolumeData } from "./vtkPreview";
import {
  enabledLayers,
  volumeDisplayStats,
  type Camera,
  type SpatialView,
  type VolumeData,
} from "./spatialRenderer";
import { toVtkCamera, fromVtkCamera, type VtkCamera } from "./vtkCamera";
import { registerVolumeCapture } from "./exportVolume";
import { vtkDisplayExtent, vtkSampleDistance } from "./vtkGeometry";

type Props = {
  data: VtkVolumeData;
  source: VolumeData;
  view: SpatialView;
  log: boolean;
  onCamera: (id: string, c: Camera) => void;
  onError: (message: string) => void;
  points?: boolean;
  pointIds?: string[];
  tile?: boolean;
};
type Handle = {
  resize: () => void;
  applyCamera: (c: Camera) => void;
  destroy: () => void;
  capture: () => Promise<string>;
};

function createScene(
  el: HTMLDivElement,
  { data, source, view, log, onCamera, points, pointIds = [] }: Props,
): Handle {
  const styles = enabledLayers(view),
    layers = data.layers.filter((l) =>
      styles.some((s) => s.signal_id === l.signal_id),
    );
  const pointSet = new Set(points ? layers.map((l) => l.signal_id) : pointIds);
  const volumeLayers = layers.filter((l) => !pointSet.has(l.signal_id));
  const pointLayers = layers.filter((l) => pointSet.has(l.signal_id));
  const extent = vtkDisplayExtent(data, view);
  const volumeObjects: Array<{
    image: ReturnType<typeof vtkImageData.newInstance>;
    mapper: ReturnType<typeof vtkVolumeMapper.newInstance>;
    volume: ReturnType<typeof vtkVolume.newInstance>;
  }> = [];
  const funcs: ReturnType<typeof vtkColorTransferFunction.newInstance>[] = [],
    opacities: ReturnType<typeof vtkPiecewiseFunction.newInstance>[] = [];
  const pointObjects: Array<{
    actor: ReturnType<typeof vtkActor.newInstance>;
    mapper: ReturnType<typeof vtkMapper.newInstance>;
    poly: ReturnType<typeof vtkPolyData.newInstance>;
  }> = [];
  let axes: ReturnType<typeof vtkCubeAxesActor.newInstance> | undefined;
  const rw = vtkGenericRenderWindow.newInstance({
    background: [0.063, 0.122, 0.18],
  });
  try {
    rw.setContainer(el);
    rw.resize();
    const renderer = rw.getRenderer();
    const shared = volumeDisplayStats(
      source.layers.flatMap((l) => l.values),
      0,
      log,
    ).upper;
    for (let offset = 0; offset < volumeLayers.length; offset += 3) {
      const group = volumeLayers.slice(offset, offset + 3);
      const values = new Float32Array(group[0].values.length * group.length);
      group.forEach((layer, j) =>
        layer.values.forEach((v, i) => {
          values[i * group.length + j] = log ? Math.log1p(Math.max(v!, 0)) : v!;
        }),
      );
      const image = vtkImageData.newInstance();
      image.setDimensions(data.x.length, data.y.length, data.z.length);
      image.setSpacing(
        extent.map(
          (n, i) =>
            n /
            Math.max(1, [data.x.length, data.y.length, data.z.length][i] - 1),
        ),
      );
      image.getPointData().setScalars(
        vtkDataArray.newInstance({
          name: "intensity",
          values,
          numberOfComponents: group.length,
        }),
      );
      const mapper = vtkVolumeMapper.newInstance();
      const volume = vtkVolume.newInstance();
      volumeObjects.push({ image, mapper, volume });
      mapper.setInputData(image);
      mapper.setSampleDistance(vtkSampleDistance(extent));
      if (group.length > 1) {
        // vtk's default independent-component mix adds colors even for fully
        // transparent components. Weight each color by its opacity instead.
        volume.getProperty().setColorMixPreset(ColorMixPreset.CUSTOM);
        (mapper as any).setViewSpecificProperties({
          OpenGL: {
            ShaderReplacements: [
              {
                shaderType: "Fragment",
                originalValue: "//VTK::CustomColorMix",
                replacementValue: `
                vec3 weightedColor = vec3(0.0);
                float totalOpacity = 0.0;
                for (int component = 0; component < vtkNumberOfComponents; ++component) {
                  float height = volume.transferFunctionsSampleHeight[component];
                  float opacity = getOpacityFromTexture(tValue[component], component, height);
                  weightedColor += opacity * getColorFromTexture(tValue[component], component, height);
                  totalOpacity += opacity;
                }
                return totalOpacity > 0.0
                  ? vec4(weightedColor / totalOpacity, min(totalOpacity, 1.0))
                  : vec4(0.0);
              `,
                replaceFirst: true,
                replaceAll: false,
              },
            ],
          },
        });
      }
      volume.setMapper(mapper);
      group.forEach((layer, i) => {
        const style = styles.find((s) => s.signal_id === layer.signal_id)!;
        const original = source.layers.find(
          (l) => l.signal_id === layer.signal_id,
        )!;
        const stats = volumeDisplayStats(
          original.values,
          style.percentile,
          log,
        );
        const upper = view.scale === "shared" ? shared : stats.upper;
        const color = vtkColorTransferFunction.newInstance();
        for (const [fraction, r, g, b] of vtkColorStops(
          style.colorscale,
          style.colorscale_reversed,
        ))
          color.addRGBPoint(upper * fraction, r / 255, g / 255, b / 255);
        const opacity = vtkPiecewiseFunction.newInstance();
        opacity.addPoint(0, 0);
        opacity.addPoint(stats.lower, 0);
        opacity.addPoint(Math.max(upper, stats.lower + 1e-6), style.opacity);
        volume.getProperty().setRGBTransferFunction(i, color);
        volume.getProperty().setScalarOpacity(i, opacity);
        volume
          .getProperty()
          .setScalarOpacityUnitDistance(
            i,
            Math.max(Math.min(...extent) / 10, 1e-6),
          );
        funcs.push(color);
        opacities.push(opacity);
      });
      volume.getProperty().setInterpolationTypeToLinear();
      renderer.addVolume(volume);
    }
    if (pointLayers.length)
      pointLayers.forEach((layer) => {
        const style = styles.find((s) => s.signal_id === layer.signal_id)!;
        const original = source.layers.find(
          (l) => l.signal_id === layer.signal_id,
        )!;
        const geometry = buildVtkPoints(source, original, style, log, extent);
        const poly = vtkPolyData.newInstance();
        poly.getPoints().setData(new Float32Array(geometry.positions), 3);
        const verts = new Uint32Array(geometry.intensities.length * 2);
        geometry.intensities.forEach((_, i) => {
          verts[i * 2] = 1;
          verts[i * 2 + 1] = i;
        });
        poly.getVerts().setData(verts);
        poly.getPointData().setScalars(
          vtkDataArray.newInstance({
            name: "intensity",
            values: new Float32Array(geometry.intensities),
            numberOfComponents: 1,
          }),
        );
        const color = vtkColorTransferFunction.newInstance();
        const stats = volumeDisplayStats(
          original.values,
          style.percentile,
          log,
        );
        const upper = view.scale === "shared" ? shared : stats.upper;
        for (const [fraction, r, g, b] of vtkColorStops(
          style.colorscale,
          style.colorscale_reversed,
        ))
          color.addRGBPoint(upper * fraction, r / 255, g / 255, b / 255);
        funcs.push(color);
        const pointMapper = vtkMapper.newInstance();
        pointMapper.setInputData(poly);
        pointMapper.setLookupTable(color);
        pointMapper.setUseLookupTableScalarRange(true);
        const actor = vtkActor.newInstance();
        actor.setMapper(pointMapper);
        actor.getProperty().setPointSize(5);
        actor.getProperty().setOpacity(style.opacity);
        renderer.addActor(actor);
        pointObjects.push({ actor, mapper: pointMapper, poly });
      });
    const camera = renderer.getActiveCamera();
    axes = vtkCubeAxesActor.newInstance();
    axes.setCamera(camera);
    axes.setDataBounds(0, extent[0], 0, extent[1], 0, extent[2]);
    axes.setAxisLabels(
      `X (${data.xy_unit})`,
      `Y (${data.xy_unit})`,
      data.z_unit === "frame" ? "Frame" : `Depth (${data.z_unit})`,
    );
    axes.setAxisTextStyle({
      fontColor: "#c2d1dc",
      fontFamily: "sans-serif",
      fontSize: 18,
    });
    axes.setTickTextStyle({
      fontColor: "#c2d1dc",
      fontFamily: "sans-serif",
      fontSize: 15,
    });
    axes.setAxisTitlePixelOffset(48);
    axes.getProperty().setColor(0.72, 0.8, 0.86);
    const coordinates = [data.x, data.y, data.z];
    axes.setGenerateTicks((bounds: number[]) => {
      const ticks: number[][] = [],
        tickStrings: string[][] = [];
      coordinates.forEach((axis, i) => {
        const first = axis[0],
          last = axis.at(-1)!,
          scale = scaleLinear().domain([first, last]),
          vals = scale.ticks(5),
          format = scale.tickFormat(5, "~f");
        if (first === last) {
          ticks.push([(bounds[i * 2] + bounds[i * 2 + 1]) / 2]);
          tickStrings.push([String(first)]);
          return;
        }
        ticks.push(
          vals.map(
            (v) =>
              bounds[i * 2] +
              ((bounds[i * 2 + 1] - bounds[i * 2]) * (v - first)) /
                (last - first),
          ),
        );
        tickStrings.push(vals.map(format));
      });
      return { ticks, tickStrings };
    });
    renderer.addActor(axes);
    const applyCamera = (c: Camera) => {
      const v = toVtkCamera(c, extent);
      camera.setFocalPoint(...v.focalPoint);
      camera.setPosition(...v.position);
      camera.setViewUp(...v.viewUp);
      camera.setParallelProjection(c.projection === "orthographic");
      if (c.projection === "orthographic")
        camera.setParallelScale(
          Math.hypot(...v.position.map((x, i) => x - v.focalPoint[i])) * 0.4,
        );
      renderer.resetCameraClippingRange();
      rw.getRenderWindow().render();
    };
    applyCamera(view.camera);
    const sub = rw
      .getRenderWindow()
      .getInteractor()
      .getInteractorStyle()
      .onEndInteractionEvent(() => {
        const projection = camera.getParallelProjection()
          ? "orthographic"
          : "perspective";
        const pos = camera.getPosition() as [number, number, number],
          focal = camera.getFocalPoint() as [number, number, number],
          up = camera.getViewUp() as [number, number, number];
        let position = pos;
        if (projection === "orthographic") {
          const dist = Math.hypot(...pos.map((n, i) => n - focal[i])),
            ratio = camera.getParallelScale() / (dist * 0.4);
          position = pos.map((n, i) => focal[i] + (n - focal[i]) * ratio) as [
            number,
            number,
            number,
          ];
        }
        const c: VtkCamera = {
          position,
          focalPoint: focal,
          viewUp: up,
          projection,
        };
        onCamera(layers[0].signal_id, fromVtkCamera(c, extent));
      });
    return {
      resize() {
        rw.resize();
      },
      applyCamera,
      capture: () => rw.getRenderWindow().captureImages("image/png")[0],
      destroy() {
        sub.unsubscribe();
        renderer.removeActor(axes!);
        axes!.delete();
        volumeObjects.forEach(({ image, mapper, volume }) => {
          renderer.removeVolume(volume);
          mapper.delete();
          volume.delete();
          image.delete();
        });
        pointObjects.forEach(({ actor, mapper: pointMapper, poly }) => {
          renderer.removeActor(actor);
          actor.delete();
          pointMapper.delete();
          poly.delete();
        });
        rw.delete();
        funcs.forEach((f) => f.delete());
        opacities.forEach((f) => f.delete());
      },
    };
  } catch (error) {
    rw.delete();
    volumeObjects.forEach(({ image, mapper, volume }) => {
      mapper.delete();
      volume.delete();
      image.delete();
    });
    pointObjects.forEach(({ actor, mapper, poly }) => {
      actor.delete();
      mapper.delete();
      poly.delete();
    });
    axes?.delete();
    funcs.forEach((f) => f.delete());
    opacities.forEach((f) => f.delete());
    throw error;
  }
}
export function VtkScene(props: Props) {
  const el = useRef<HTMLDivElement>(null),
    handle = useRef<Handle | null>(null),
    latest = useRef(props);
  latest.current = props;
  const styleKey = JSON.stringify([
    props.view.layers.map((l) => [
      l.signal_id,
      l.visible,
      l.colorscale,
      l.colorscale_reversed,
      l.opacity,
      l.percentile,
    ]),
    props.view.scale,
    props.view.frame_stretch,
    props.view.depth_exaggeration,
    props.log,
    props.points,
    props.pointIds,
  ]);
  const sceneElement = useRef<HTMLDivElement>(null);
  const cameraKey = JSON.stringify(props.view.camera);
  useEffect(() => {
    if (!el.current) return;
    let h: Handle;
    try {
      h = createScene(el.current, latest.current);
    } catch (e) {
      latest.current.onError(e instanceof Error ? e.message : String(e));
      return;
    }
    handle.current = h;
    const unregister = registerVolumeCapture(sceneElement.current!, h.capture);
    const observer = new ResizeObserver(() => h.resize());
    observer.observe(el.current);
    return () => {
      observer.disconnect();
      unregister();
      h.destroy();
      handle.current = null;
    };
  }, [props.data, props.source, styleKey]);
  useEffect(() => {
    handle.current?.applyCamera(latest.current.view.camera);
  }, [cameraKey]);
  const legends = useMemo(() => {
    const styles = enabledLayers(props.view);
    const shared =
      props.view.scale === "shared"
        ? volumeDisplayStats(
            props.source.layers.flatMap((layer) => layer.values),
            0,
            props.log,
          ).upper
        : 0;
    return props.data.layers.map((layer) => {
      const style = styles.find((s) => s.signal_id === layer.signal_id)!,
        original = props.source.layers.find(
          (l) => l.signal_id === layer.signal_id,
        )!;
      const upper =
        props.view.scale === "shared"
          ? shared
          : volumeDisplayStats(original.values, style.percentile, props.log)
              .upper;
      const stops = vtkColorStops(
        style.colorscale,
        style.colorscale_reversed,
      ).map(([fraction, r, g, b]) => `rgb(${r},${g},${b}) ${fraction * 100}%`);
      return {
        id: layer.signal_id,
        label: layer.label,
        upper,
        gradient: `linear-gradient(to top,${stops.join(",")})`,
        stops: vtkColorStops(style.colorscale, style.colorscale_reversed),
      };
    });
  }, [props.data, props.source, styleKey]);
  return (
    <div
      ref={sceneElement}
      className="volume-canvas vtk-volume-view"
      data-testid={props.tile ? "vtk-tile" : "volume-canvas"}
      data-renderer="vtk"
      data-camera={JSON.stringify(props.view.camera)}
      data-volume-signals={
        props.points
          ? 0
          : props.data.layers.length - (props.pointIds?.length ?? 0)
      }
    >
      <div className="vtk-volume-viewport" ref={el} />
      <div className="vtk-volume-legends" aria-label="3D intensity scales">
        {legends.map((legend) => (
          <div className="vtk-volume-legend" key={legend.id}>
            <div>
              {legends.length > 1 ? `${legend.label} · ` : ""}
              {props.log ? "log(1+I)" : "Intensity"}
            </div>
            <div className="vtk-volume-scale">
              <span
                className="vtk-volume-ramp"
                data-stops={JSON.stringify(legend.stops)}
                style={{ background: legend.gradient }}
              />
              <span className="vtk-volume-ticks">
                <span>{Number(legend.upper.toPrecision(3))}</span>
                <span>{Number((legend.upper / 2).toPrecision(3))}</span>
                <span>0</span>
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
