import type { Analysis } from "../api/client";
import {
  defaultLayer,
  layerRange,
  percentile,
  type SpatialView,
  type SpatialLayer,
  type VolumeData,
} from "./spatialRenderer";
import { formatNumber } from "../shared/numbers";
export function LayerEditor({
  analysis: a,
  view: v,
  data,
  onChange,
}: {
  analysis: Analysis;
  view: SpatialView;
  data: VolumeData | null;
  onChange: (v: SpatialView) => void;
}) {
  const update = (id: string, patch: Partial<SpatialLayer>) =>
    onChange({
      ...v,
      layers: v.layers.map((l) =>
        l.signal_id === id ? { ...l, ...patch } : l,
      ),
    });
  return (
    <aside className="volume-layers" aria-label="Volume layers">
      <h2>3D signals</h2>
      <label>
        Add 3D signal
        <select
          aria-label="Add 3D signal"
          value=""
          onChange={(e) => {
            if (e.target.value)
              onChange({
                ...v,
                layers: [...v.layers, defaultLayer(e.target.value)],
              });
          }}
        >
          <option value="">Choose a named signal…</option>
          {a.signals
            .filter(
              (s) => s.recipe && !v.layers.some((l) => l.signal_id === s.id),
            )
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
        </select>
      </label>
      <div className="volume-layer-list">
        {v.layers.map((l) => {
          const signal = a.signals.find((s) => s.id === l.signal_id)!;
          if (!signal) return null;
          const values = data?.layers.find(
            (d) => d.signal_id === l.signal_id,
          )?.values;
          const range = values ? layerRange(values) : null;
          const threshold = values
            ? percentile(
                values.filter((x): x is number => x !== null),
                l.percentile,
              )
            : null;
          return (
            <fieldset key={l.signal_id} data-testid="volume-layer">
              <legend>{signal.name}</legend>
              <div className="row">
                <label>
                  <input
                    type="checkbox"
                    aria-label={`Show ${signal.name} in 3D`}
                    checked={l.visible}
                    onChange={(e) =>
                      update(l.signal_id, { visible: e.target.checked })
                    }
                  />
                  Visible
                </label>
                <button
                  aria-pressed={v.solo === l.signal_id}
                  onClick={() =>
                    onChange({
                      ...v,
                      solo: v.solo === l.signal_id ? null : l.signal_id,
                    })
                  }
                >
                  Solo {signal.name}
                </button>
                <button
                  aria-label={`Remove ${signal.name} from 3D`}
                  onClick={() =>
                    onChange({
                      ...v,
                      layers: v.layers.filter(
                        (x) => x.signal_id !== l.signal_id,
                      ),
                      solo: v.solo === l.signal_id ? null : v.solo,
                    })
                  }
                >
                  Remove
                </button>
              </div>
              <small>
                Frames {signal.recipe?.frames.join("–")} ·{" "}
                {signal.recipe?.source} ·{" "}
                {signal.recipe?.intervals
                  .map((w) => w.map((x) => formatNumber(x)).join("–"))
                  .join(", ")}{" "}
                Th
              </small>
              <label>
                Colormap
                <select
                  aria-label={`3D colormap for ${signal.name}`}
                  value={l.colorscale}
                  onChange={(e) =>
                    update(l.signal_id, {
                      colorscale: e.target.value as SpatialLayer["colorscale"],
                    })
                  }
                >
                  {[
                    "Viridis",
                    "Magma",
                    "Plasma",
                    "Cividis",
                    "Reds",
                    "Blues",
                    "Greens",
                    "Purples",
                  ].map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label>
                Opacity
                <input
                  aria-label={`3D opacity for ${signal.name}`}
                  type="range"
                  min="0"
                  max="1"
                  step=".01"
                  value={l.opacity}
                  onChange={(e) =>
                    update(l.signal_id, { opacity: Number(e.target.value) })
                  }
                />
                <output>{formatNumber(l.opacity)}</output>
              </label>
              <label>
                Percentile threshold
                <input
                  aria-label={`3D percentile for ${signal.name}`}
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={l.percentile}
                  onChange={(e) =>
                    update(l.signal_id, { percentile: Number(e.target.value) })
                  }
                />
                <output>{l.percentile}%</output>
              </label>
              {range && (
                <small>
                  Intensity {formatNumber(range[0])}–{formatNumber(range[1])} ·
                  cutoff {formatNumber(threshold!)} · {v.scale} scale
                </small>
              )}
            </fieldset>
          );
        })}
      </div>
      {!v.layers.length && (
        <p>
          Add signals from the existing named collection to compare them in 3D.
        </p>
      )}
    </aside>
  );
}
