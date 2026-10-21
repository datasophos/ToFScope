import { useState } from "react";
import type { Analysis } from "../api/client";
import type { Send } from "./SignalDetails";
import { ToolPopover } from "./ToolPopover";
import { ExactForm } from "./ExactForm";
export function AnalysisSettings({
  analysis: a,
  send,
}: {
  analysis: Analysis;
  send: Send;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="control-popover">
      <button onClick={() => setOpen(!open)}>Analysis settings</button>
      {open && (
        <ToolPopover title="Analysis settings" onClose={() => setOpen(false)}>
          <p>
            Analysis frame range controls the profile domain and depth
            navigation. Existing signal coverage stays unchanged.
          </p>
          <ExactForm
            labels={["Analysis first", "Analysis last"]}
            values={a.loaded_frames}
            button="Set analysis range"
            onApply={(v) =>
              void send({
                type: "set_analysis_frames",
                frames: v as [number, number],
              })
                .then(() => setOpen(false))
                .catch(() => {})
            }
          />
        </ToolPopover>
      )}
    </div>
  );
}
