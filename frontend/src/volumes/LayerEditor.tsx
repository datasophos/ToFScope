import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Analysis } from "../api/client";
import {
  defaultLayer,
  levelStats,
  type SpatialView,
  type SpatialLayer,
  type VolumeData,
} from "./spatialRenderer";
import { formatNumber } from "../shared/numbers";
import { LevelsControl } from "./LevelsControl";

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
  const layerPanel = useRef<HTMLElement>(null);
  const [position, setPosition] = useState({ left: 8, top: 8, width: 300 });
  useLayoutEffect(() => {
    if (!selected) return;
    const place = () => {
      const rect = layerPanel.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(300, window.innerWidth - 16);
      const left =
        rect.right + width + 8 <= window.innerWidth
          ? rect.right + 8
          : Math.max(
              8,
              Math.min(rect.right - width, window.innerWidth - width - 8),
            );
      setPosition({
        left,
        top: Math.max(8, Math.min(rect.top + 12, window.innerHeight - 480)),
        width,
      });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [selected]);
  useEffect(() => {
    if (!selected) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [selected]);
  const signals = [
    ...a.signals.filter((s) => s.recipe),
    ...(a.has_se ? [{ id: "@se", name: "SE", recipe: null }] : []),
  ];
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
  const selectedLayer = data?.layers.find(
    (layer) => layer.signal_id === selected,
  );
  const levelData =
    selectedLayer && style
      ? levelStats(selectedLayer.values, style, false)
      : null;
  return (
    <aside
      ref={layerPanel}
      className="volume-layers"
      aria-label="Volume layers"
    >
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
      {signal &&
        style &&
        createPortal(
          <div
            className="volume-signal-popover"
            style={{
              position: "fixed",
              left: position.left,
              top: position.top,
              width: position.width,
              maxHeight: "calc(100vh - 16px)",
              overflowY: "auto",
              zIndex: 100,
            }}
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
              {signal.recipe ? (
                <>
                  Frames {signal.recipe.frames.join("–")} ·{" "}
                  {signal.recipe.source} · m/z{" "}
                  {signal.recipe.intervals
                    .map((w) => w.map((x) => formatNumber(x)).join("–"))
                    .join(", ")}
                </>
              ) : (
                "Secondary electron"
              )}
            </small>
            {selectedLayer && levelData ? (
              <LevelsControl
                values={selectedLayer.values}
                levels={[levelData.lower, levelData.upper]}
                onChange={(levels) => update(signal.id, { levels })}
                onReset={() => update(signal.id, { levels: null })}
              />
            ) : (
              <small>Show this layer to adjust its levels.</small>
            )}
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
                  "Gray",
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
          </div>,
          document.body,
        )}
      {!signals.length && <p>Add a signal to view it in 3D.</p>}
    </aside>
  );
}
