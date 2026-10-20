import type { Analysis } from "../api/client";
import { CurveMarker } from "../components/CurveMarker";
import { curveStyle } from "../plots/curveStyle";
import type { Send } from "./SignalDetails";
import type { SignalEditorController } from "./useSignalEditor";

export function SignalCollection({
  analysis: a,
  send,
  editor,
  onDetails,
}: {
  analysis: Analysis;
  send: Send;
  editor: SignalEditorController;
  onDetails: (id: string) => void;
}) {
  const act = (command: Parameters<Send>[0]) =>
    void send(command).catch(() => {});
  const eligible = (row: Analysis["signals"][number]) =>
    !!row.recipe &&
    row.recipe.frames[0] <= a.loaded_frames[1] &&
    row.recipe.frames[1] >= a.loaded_frames[0];
  return (
    <div
      className="signal-table"
      role="group"
      aria-label="Signal display choices"
    >
      <div className="signal-columns" aria-hidden="true">
        <span>Signal / source</span>
        <span>Images</span>
        <span>Profile</span>
        <span>Actions</span>
      </div>
      <div className="signal-rows">
        {a.signals.map((row) => {
          const job = row.job_id ? editor.jobs[row.job_id] : undefined;
          const busy =
            !!row.job_id &&
            (!job || ["queued", "running"].includes(job.status));
          const image = row.id === a.image_signal_id;
          const canRemove =
            !image ||
            a.signals.some((other) => other.id !== row.id && eligible(other));
          return (
            <div
              className="signal-row"
              key={row.id}
              data-testid="signal-row"
              data-signal-id={row.id}
            >
              <div className="signal-name">
                <CurveMarker style={curveStyle(row.style_index)} />
                <div>
                  <button
                    className="text-button"
                    onClick={() => onDetails(row.id)}
                  >
                    {row.name}
                    {a.signals.filter((other) => other.name === row.name)
                      .length > 1
                      ? ` [${row.id.slice(0, 8)}]`
                      : ""}
                  </button>
                  <small>
                    {row.recipe?.source === "stored"
                      ? "Stored channel"
                      : row.recipe
                        ? "Raw integration"
                        : "New signal"}
                    {row.recipe &&
                      ` · frames ${row.recipe.frames[0]}–${row.recipe.frames[1]}`}
                  </small>
                  {busy && (
                    <div role="status">
                      {row.recipe ? "Updating" : "Calculating"} ·{" "}
                      {job?.done ?? 0}/{job?.total ?? "…"}
                      <progress max={job?.total || 1} value={job?.done || 0} />
                      <button onClick={() => void editor.cancel(row.job_id!)}>
                        Cancel
                      </button>
                    </div>
                  )}
                  {job &&
                    ["failed", "cancelled", "obsolete"].includes(
                      job.status,
                    ) && (
                      <small>
                        {job.status} · previous result retained
                        {!row.recipe && (
                          <button onClick={() => editor.openNew()}>
                            Create another signal
                          </button>
                        )}
                      </small>
                    )}
                </div>
              </div>
              <label className="signal-choice">
                <span>Images</span>
                <input
                  type="radio"
                  name={`image-${a.id}`}
                  aria-label={`Show ${row.name} in images`}
                  data-signal-id={row.id}
                  checked={image}
                  disabled={!eligible(row)}
                  title={
                    eligible(row)
                      ? "Use for ion map and front projection"
                      : "No ready coverage in the analysis range"
                  }
                  onChange={() =>
                    act({ type: "select_image_signal", signal_id: row.id })
                  }
                />
              </label>
              <label className="signal-choice">
                <span>Profile</span>
                <input
                  type="checkbox"
                  aria-label={`Show ${row.name} in depth profile`}
                  checked={image || a.profile_signal_ids.includes(row.id)}
                  disabled={image || !row.recipe}
                  title={image ? "Included with image signal" : undefined}
                  onChange={(e) =>
                    act({
                      type: "set_profile_visible",
                      signal_id: row.id,
                      visible: e.target.checked,
                    })
                  }
                />
              </label>
              <div className="row signal-actions">
                <button onClick={() => onDetails(row.id)}>Details</button>
                <button
                  aria-label={`Remove ${row.name}`}
                  disabled={!canRemove}
                  title={
                    canRemove
                      ? "Remove signal"
                      : "Add another ready image signal first"
                  }
                  onClick={() =>
                    act({ type: "remove_signal", signal_id: row.id })
                  }
                >
                  ×
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
