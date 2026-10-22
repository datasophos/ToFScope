import { PreciseNumberInput } from "../components/PreciseNumberInput";
import { formatNumber } from "../shared/numbers";
import { useEffect, useRef, useState } from "react";
import type { Analysis, Panel } from "../api/client";
import type { Send } from "../explore/SignalDetails";
import { ToolPopover } from "../explore/ToolPopover";
import { PlotPanel } from "../plots/PlotPanel";
import { coordinateToFrame, anchorError } from "./coordinates";
const scales = { nm: 1, um: 1000, mm: 1e6 };
export function DepthEditor({
  analysis: a,
  send,
  active,
}: {
  analysis: Analysis;
  send: Send;
  active: boolean;
}) {
  const [open, setOpen] = useState(false),
    [frame, setFrame] = useState("1"),
    [depth, setDepth] = useState("");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const errorMessage = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (error) errorMessage.current?.scrollIntoView({ block: "nearest" });
  }, [error]);
  const scale = scales[a.depth_unit];
  const choose = (n: number) => {
    setFrame(String(n));
    const anchor = a.depth_anchors.find((x) => x.frame === n);
    setDepth(anchor ? String(anchor.depth_nm / scale) : "");
  };
  // Keep draft physical values canonical across display-unit changes.
  const [previousScale, setPreviousScale] = useState(scale);
  useEffect(() => {
    if (depth !== "") setDepth(String((Number(depth) * previousScale) / scale));
    setPreviousScale(scale);
  }, [scale]);
  const commit = async (command: Parameters<Send>[0]) => {
    if (command.type === "set_depth_anchors") {
      const invalid = anchorError(command.anchors, a.shape[0]);
      if (invalid) {
        setError(invalid);
        return;
      }
    }
    setBusy(true);
    setError("");
    try {
      await send(command);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  // The editor must show every analysis frame even when physical views clip unknown samples.
  const [full, setFull] = useState<Panel>();
  useEffect(() => {
    if (!open) return;
    let alive = true;
    import("../api/client")
      .then(({ request }) =>
        request<{ panels: { profile: Panel } }>(
          `/analyses/${a.id}/data?panels=profile&coordinates=frame`,
        ),
      )
      .then((d) => {
        if (alive) setFull(d.panels.profile);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [open, a.revision]);
  useEffect(() => {
    if (!active) setOpen(false);
  }, [active]);
  useEffect(() => {
    setFull(undefined);
    setFrame("1");
    setDepth("");
    setError("");
  }, [a.dataset.generation]);
  const graph = full;
  return (
    <>
      <button onClick={() => setOpen(true)} aria-label="Calibrate depth">
        Depth calibration…
      </button>
      {open && (
        <ToolPopover
          title="Depth calibration"
          width={720}
          placement="center"
          className="calibration-editor"
          onClose={() => setOpen(false)}
        >
          <p>
            Click a profile to choose an acquisition frame, then enter its known
            depth. Drag to zoom.
          </p>
          <div className="calibration-graph">
            <PlotPanel
              name="calibration"
              title="Calibration profiles"
              help="Original frame coordinates; anchor editing never changes signal values."
              markers={a.depth_anchors.map((x) => x.frame)}
              panel={graph}
              maximized={false}
              onMaximize={() => {}}
              selectionMode="zoom"
              selection={
                Number.isFinite(Number(frame))
                  ? [Number(frame), Number(frame)]
                  : undefined
              }
              onSelect={() => {}}
              onClick={(x) => {
                if (graph) {
                  const n = coordinateToFrame(
                    x,
                    graph.axes[0],
                    graph.acquisition_frames ?? [],
                  );
                  if (n !== undefined) choose(Math.round(n));
                }
              }}
            />
            {a.depth_anchors.length > 1 && (
              <p className="anchor-summary">
                Anchors:{" "}
                {a.depth_anchors
                  .map(
                    (x) =>
                      `frame ${x.frame}: ${formatNumber(x.depth_nm / scale)} ${a.depth_unit === "um" ? "µm" : a.depth_unit}`,
                  )
                  .join(" · ")}
              </p>
            )}
          </div>
          {error && (
            <p className="calibration-error" role="alert" ref={errorMessage}>
              {error}
            </p>
          )}
          <fieldset disabled={busy}>
            <div className="row anchor-entry">
              <label>
                Selected frame
                <input
                  aria-label="Anchor frame"
                  type="number"
                  min={0}
                  max={a.shape[0] - 1}
                  step={1}
                  value={frame}
                  onChange={(e) => choose(Number(e.target.value))}
                />
              </label>
              <label>
                Known depth ({a.depth_unit === "um" ? "µm" : a.depth_unit})
                <PreciseNumberInput
                  label="Known depth"
                  value={depth}
                  disabled={frame === "0"}
                  onChange={setDepth}
                />
              </label>
              <button
                disabled={frame === "0"}
                onClick={() => {
                  if (frame === "" || depth === "") {
                    setError("Enter a frame and known depth.");
                    return;
                  }
                  void commit({
                    type: "set_depth_anchors",
                    anchors: [
                      ...a.depth_anchors.filter(
                        (x) => x.frame !== Number(frame),
                      ),
                      { frame: Number(frame), depth_nm: Number(depth) * scale },
                    ],
                  });
                }}
              >
                {a.depth_anchors.some((x) => x.frame === Number(frame))
                  ? "Update anchor"
                  : "Add anchor"}
              </button>
            </div>
            <p>Frame 0 is fixed at depth 0.</p>
            <div className="row">
              <label>
                Depth display unit
                <select
                  aria-label="Depth display unit"
                  value={a.depth_unit}
                  onChange={(e) =>
                    void commit({
                      type: "set_depth_display",
                      unit: e.target.value as Analysis["depth_unit"],
                      coordinates: a.depth_coordinates,
                    })
                  }
                >
                  <option value="nm">nm</option>
                  <option value="um">µm</option>
                  <option value="mm">mm</option>
                </select>
              </label>
            </div>
            <table className="anchor-table">
              <thead>
                <tr>
                  <th>Frame</th>
                  <th>Known depth</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {a.depth_anchors.map((anchor) => (
                  <AnchorRow
                    key={`${anchor.frame}:${a.depth_unit}:${anchor.depth_nm}`}
                    frame={anchor.frame}
                    value={anchor.depth_nm / scale}
                    unit={a.depth_unit === "um" ? "µm" : a.depth_unit}
                    onUpdate={(v) =>
                      void commit({
                        type: "set_depth_anchors",
                        anchors: a.depth_anchors.map((x) =>
                          x.frame === anchor.frame
                            ? { ...x, depth_nm: v * scale }
                            : x,
                        ),
                      })
                    }
                    onRemove={() =>
                      void commit({
                        type: "set_depth_anchors",
                        anchors: a.depth_anchors.filter(
                          (x) => x.frame !== anchor.frame,
                        ),
                      })
                    }
                  />
                ))}
              </tbody>
            </table>
          </fieldset>
          <p>
            {a.depth_anchors.length > 1
              ? `Calibrated frames 0–${a.depth_anchors.at(-1)!.frame}; later depths are unknown and omitted in physical views.`
              : "Add a positive-depth anchor to enable physical coordinates."}{" "}
            Applies to profiles and front projections. Intensities and frame
            selections stay unchanged. Switch Frames / Physical depth in the
            main Viewing depths controls.
          </p>

          <button onClick={() => setOpen(false)}>Done</button>
        </ToolPopover>
      )}
    </>
  );
}
function AnchorRow({
  frame,
  value,
  unit,
  onUpdate,
  onRemove,
}: {
  frame: number;
  value: number;
  unit: string;
  onUpdate: (v: number) => void;
  onRemove: () => void;
}) {
  const [draft, setDraft] = useState(String(value));
  return (
    <tr>
      <td>{frame}</td>
      <td>
        {frame === 0 ? (
          `0 ${unit}`
        ) : (
          <PreciseNumberInput
            label={`Depth at frame ${frame}`}
            value={draft}
            onChange={setDraft}
          />
        )}
      </td>
      <td>
        {frame === 0 ? (
          "Fixed"
        ) : (
          <>
            <button onClick={() => onUpdate(Number(draft))}>Update</button>
            <button
              aria-label={`Remove anchor at frame ${frame}`}
              onClick={onRemove}
            >
              Remove
            </button>
          </>
        )}
      </td>
    </tr>
  );
}
