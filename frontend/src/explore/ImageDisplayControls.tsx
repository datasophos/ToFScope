import { useMemo, useState } from "react";
import type { Analysis, Panel } from "../api/client";
import { ToolPopover } from "./ToolPopover";
import { ColormapPicker } from "../shared/ColormapPicker";
import { LevelsControl } from "../shared/LevelsControl";

export function ImageDisplayControls({
  analysis: a,
  display,
  sePanel,
  seLevels,
  onSeLevels,
}: {
  analysis: Analysis;
  sePanel?: Panel;
  seLevels: [number, number] | null;
  onSeLevels: (value: [number, number] | null) => void;
  display: (patch: Partial<Analysis["display"]>) => void;
}) {
  const [open, setOpen] = useState(false);
  const values = useMemo(
    () => (open ? (sePanel?.values?.flat() ?? []) : []),
    [open, sePanel?.values],
  );
  return (
    <>
      <button
        aria-label="Image display settings"
        aria-expanded={open}
        aria-haspopup="dialog"
        title="Image display settings"
        onClick={() => setOpen(!open)}
      >
        Display…
      </button>
      {open && (
        <ToolPopover
          title="Image display"
          width={300}
          placement="beside-image"
          className="image-display-settings"
          onClose={() => setOpen(false)}
        >
          <label>
            <input
              type="checkbox"
              checked={a.display.log}
              onChange={(e) => display({ log: e.target.checked })}
            />
            Log colors
          </label>
          <div className="image-display-colormap">
            <span>SIMS colormap</span>
            <ColormapPicker
              label="SIMS colormap"
              value={
                a.display.colormap === "ion"
                  ? "viridis"
                  : (a.display.colormap ?? "viridis")
              }
              options={[
                { value: "viridis", label: "Viridis", palette: "Viridis" },
                { value: "cividis", label: "Cividis", palette: "Cividis" },
                { value: "magma", label: "Magma", palette: "Magma" },
                { value: "gray", label: "Grayscale", palette: "Gray" },
              ]}
              onChange={(value) =>
                display({ colormap: value as Analysis["display"]["colormap"] })
              }
            />
          </div>
          <label>
            Image{" "}
            <select
              aria-label="Image"
              value={a.display.image}
              onChange={(e) => display({ image: e.target.value })}
            >
              <option value="sims">SIMS</option>
              {a.has_se && <option value="se">SE</option>}
            </select>
          </label>
          {a.display.image === "se" &&
            (sePanel && values.length ? (
              <LevelsControl
                values={values}
                levels={seLevels ?? sePanel.intensity_range}
                onChange={onSeLevels}
                onReset={() => onSeLevels(null)}
              />
            ) : (
              <small>Loading SE image…</small>
            ))}
        </ToolPopover>
      )}
    </>
  );
}
