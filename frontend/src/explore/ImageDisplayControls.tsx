import { useState } from "react";
import type { Analysis } from "../api/client";
import { ToolPopover } from "./ToolPopover";

export function ImageDisplayControls({
  analysis: a,
  display,
  brightness,
  contrast,
  onBrightness,
  onContrast,
}: {
  analysis: Analysis;
  brightness: number;
  contrast: number;
  onBrightness: (value: number) => void;
  onContrast: (value: number) => void;
  display: (patch: Partial<Analysis["display"]>) => void;
}) {
  const [open, setOpen] = useState(false);
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
          <label>
            SIMS colormap{" "}
            <select
              aria-label="SIMS colormap"
              value={
                a.display.colormap === "ion"
                  ? "viridis"
                  : (a.display.colormap ?? "viridis")
              }
              onChange={(e) =>
                display({
                  colormap: e.target.value as Analysis["display"]["colormap"],
                })
              }
            >
              <option value="viridis">Viridis</option>
              <option value="cividis">Cividis</option>
              <option value="magma">Magma</option>
              <option value="gray">Grayscale</option>
            </select>
          </label>
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
          {a.display.image === "se" && (
            <>
              <label>
                Brightness{" "}
                <input
                  aria-label="SE brightness"
                  type="range"
                  min="-1"
                  max="1"
                  step="0.01"
                  value={brightness}
                  onChange={(e) => onBrightness(Number(e.target.value))}
                />
              </label>
              <label>
                Contrast{" "}
                <input
                  aria-label="SE contrast"
                  type="range"
                  min="0.25"
                  max="4"
                  step="0.05"
                  value={contrast}
                  onChange={(e) => onContrast(Number(e.target.value))}
                />
              </label>
              <button
                className="se-display-reset"
                onClick={() => {
                  onBrightness(0);
                  onContrast(1);
                }}
              >
                Reset SE display
              </button>
            </>
          )}
        </ToolPopover>
      )}
    </>
  );
}
