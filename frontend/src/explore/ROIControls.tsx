import { useState } from "react";
import type { Analysis } from "../api/client";
import type { Send } from "./SignalDetails";
import { ExactForm } from "./ExactForm";
import { ToolPopover } from "./ToolPopover";
export function ROIControls({
  analysis: a,
  send,
}: {
  analysis: Analysis;
  send: Send;
}) {
  const [open, setOpen] = useState(false);
  const full =
    a.roi.join(",") === [0, a.shape[2] - 1, 0, a.shape[1] - 1].join(",");
  return (
    <div className="control-popover">
      <button onClick={() => setOpen(!open)}>
        ROI:{" "}
        {full
          ? "Full field"
          : `x ${a.roi[0]}–${a.roi[1]}, y ${a.roi[2]}–${a.roi[3]}`}
      </button>
      {open && (
        <ToolPopover title="Spatial ROI" onClose={() => setOpen(false)}>
          <ExactForm
            labels={["ROI x first", "ROI x last", "ROI y first", "ROI y last"]}
            values={a.roi}
            button="Apply ROI"
            onApply={(v) =>
              void send({
                type: "set_roi",
                roi: v as [number, number, number, number],
              })
                .then(() => setOpen(false))
                .catch(() => {})
            }
          />
          <button
            onClick={() =>
              void send({
                type: "set_roi",
                roi: [0, a.shape[2] - 1, 0, a.shape[1] - 1],
              })
                .then(() => setOpen(false))
                .catch(() => {})
            }
          >
            Full field
          </button>
        </ToolPopover>
      )}
    </div>
  );
}
