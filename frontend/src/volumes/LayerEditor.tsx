import { useEffect, useMemo, useState } from "react";
import type { Analysis } from "../api/client";
import {
  defaultLayer,
  volumeDisplayStats,
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
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => {
    if (!selected) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [selected]);
  const percentileKey = JSON.stringify(
    v.layers.map((l) => [l.signal_id, l.percentile]),
  );
  const stats = useMemo(
    () =>
      new Map(
        (data?.layers ?? []).map((layer) => {
          const style = v.layers.find((l) => l.signal_id === layer.signal_id);
          return [
            layer.signal_id,
            volumeDisplayStats(
              layer.values,
              style?.percentile ?? 70,
              a.display.log,
            ),
          ];
        }),
      ),
    [data, percentileKey, a.display.log],
  );
  const signals = a.signals.filter((s) => s.recipe);
  const signal = signals.find((s) => s.id === selected);
  const style = signal
    ? (v.layers.find((l) => l.signal_id === signal.id) ?? {
        ...defaultLayer(signal.id),
        visible: false,
      })
    : null;
  const update = (
    id: string,
    patch: Partial<SpatialLayer>,
    clearSolo = false,
  ) => {
    const existing = v.layers.find((l) => l.signal_id === id);
    const layer = {
      ...(existing ?? { ...defaultLayer(id), visible: false }),
      ...patch,
    };
    onChange({
      ...v,
      solo: clearSolo ? null : v.solo,
      layers: existing
        ? v.layers.map((l) => (l.signal_id === id ? layer : l))
        : [...v.layers, layer],
    });
  };
  const range = signal ? stats.get(signal.id)?.range : null;
  const threshold = signal ? stats.get(signal.id)?.threshold : null;
  return (
    <aside className="volume-layers" aria-label="Volume layers">
      <h2>3D signals</h2>
      <div className="volume-layer-list">
        <table className="volume-signal-table">
          <thead>
            <tr>
              <th scope="col">Show</th>
              <th scope="col">Signal</th>
              <th scope="col">
                <span className="visually-hidden">Settings</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {signals.map((s) => {
              const layer = v.layers.find((l) => l.signal_id === s.id);
              const visible = !!layer?.visible && (!v.solo || v.solo === s.id);
              return (
                <tr key={s.id} data-testid="volume-layer">
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Show ${s.name} in 3D`}
                      checked={visible}
                      onChange={(e) =>
                        update(s.id, { visible: e.target.checked }, true)
                      }
                    />
                  </td>
                  <td>
                    <span data-testid="volume-signal-name">{s.name}</span>
                  </td>
                  <td>
                    <button
                      className="volume-signal-settings"
                      type="button"
                      aria-label={`3D settings for ${s.name}`}
                      aria-haspopup="dialog"
                      aria-expanded={selected === s.id}
                      onClick={() =>
                        setSelected(selected === s.id ? null : s.id)
                      }
                    >
                      ⋯
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {signal && style && (
        <div
          className="volume-signal-popover"
          role="dialog"
          aria-label={`3D settings for ${signal.name}`}
        >
          <div className="volume-popover-heading">
            <strong>{signal.name}</strong>
            <button
              type="button"
              aria-label="Close 3D signal settings"
              onClick={() => setSelected(null)}
            >
              ×
            </button>
          </div>
          <small>
            Frames {signal.recipe?.frames.join("–")} · {signal.recipe?.source} ·{" "}
            m/z {signal.recipe?.intervals
              .map((w) => w.map((x) => formatNumber(x)).join("–"))
              .join(", ")}
          </small>
          <label>
            Colormap
            <select
              aria-label={`3D colormap for ${signal.name}`}
              value={style.colorscale}
              onChange={(e) =>
                update(signal.id, {
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
          <label className="volume-reverse-colormap">
            <input
              type="checkbox"
              aria-label={`Reverse 3D colormap for ${signal.name}`}
              checked={style.colorscale_reversed}
              onChange={(e) =>
                update(signal.id, { colorscale_reversed: e.target.checked })
              }
            />
            Reverse colormap
          </label>
          <label>
            Opacity <output>{formatNumber(style.opacity)}</output>
            <input
              aria-label={`3D opacity for ${signal.name}`}
              type="range"
              min="0"
              max="1"
              step=".01"
              value={style.opacity}
              onChange={(e) =>
                update(signal.id, { opacity: Number(e.target.value) })
              }
            />
          </label>
          <label>
            Nonzero percentile <output>{style.percentile}%</output>
            <input
              aria-label={`3D percentile for ${signal.name}`}
              type="range"
              min="0"
              max="100"
              step="1"
              value={style.percentile}
              onChange={(e) =>
                update(signal.id, { percentile: Number(e.target.value) })
              }
            />
          </label>
          {range && (
            <small>
              Intensity {formatNumber(range[0])}–{formatNumber(range[1])} ·
              cutoff {formatNumber(threshold!)} · {v.scale} scale
            </small>
          )}
        </div>
      )}
      {!signals.length && <p>Add a signal to view it in 3D.</p>}
    </aside>
  );
}
