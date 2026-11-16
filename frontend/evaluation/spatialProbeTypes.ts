export type SpatialProbeResult = {
  fixture: {
    x: number[];
    y: number[];
    z: number[];
    layers: (number | null)[][];
  };
  vtkZ: number[];
  plotlyZ: number[];
  bytes: number;
  readyMs: number;
  cameraMs: number[];
  vtkInputClass: string;
};

export type SpatialProbeWindow = Window & { spatialProbe: SpatialProbeResult };
