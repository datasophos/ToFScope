import { useState } from "react";
import type { Analysis } from "../api/client";
import { CurveMarker } from "../components/CurveMarker";
import { HelpHeading } from "../components/HelpButton";
import { curveStyle } from "../plots/curveStyle";
import { ToolPopover } from "./ToolPopover";
import { SignalCollection } from "./SignalCollection";
import { SignalPicker } from "./SignalPicker";
import { SignalDetails, type Send } from "./SignalDetails";
import type { SignalEditorController } from "./useSignalEditor";
import { help } from "./help";
export function SignalTray({
  analysis: a,
  active,
  send,
  editor,
  onDetails,
  id,
}: {
  analysis: Analysis;
  active: boolean;
  send: Send;
  editor: SignalEditorController;
  onDetails: (id: string | undefined) => void;
  id?: string;
}) {
  const act = (command: Parameters<Send>[0]) =>
    void send(command).catch(() => {});
  const eligible = (row: Analysis["signals"][number]) => !!row.recipe;
  const [managing, setManaging] = useState(false);
  const image = a.signals.find((row) => row.id === a.image_signal_id);
  const label = (row: Analysis["signals"][number]) =>
    row.name +
    (a.signals.filter((other) => other.name === row.name).length > 1
      ? ` [${row.id.slice(0, 8)}]`
      : "");
  const busy = (row: Analysis["signals"][number]) =>
    !!row.job_id &&
    (!editor.jobs[row.job_id] ||
      ["queued", "running"].includes(editor.jobs[row.job_id].status));
  const details = a.signals.find((row) => row.id === id);
  return (
    <section className="signal-tray" role="region" aria-label="Signals">
      <div className="signal-strip">
        <HelpHeading title="Signals" content={help.signal} />
        <label className="image-signal-choice">
          Images
          {image && <CurveMarker style={curveStyle(image.style_index)} />}
          <select
            aria-label="Image signal"
            value={a.image_signal_id ?? ""}
            onChange={(event) =>
              act({
                type: "select_image_signal",
                signal_id: event.target.value,
              })
            }
          >
            {!image && (
              <option value="" disabled>
                Choose signal
              </option>
            )}
            {a.signals.map((row) => (
              <option key={row.id} value={row.id} disabled={!eligible(row)}>
                {label(row)}
              </option>
            ))}
          </select>
        </label>
        {a.spatial.screen !== "volume" && (
          <div
            className="signal-profiles"
            role="group"
            aria-label="Visible profiles"
          >
            <span>Profiles</span>
            <div className="signal-chips">
              {a.signals
                .filter(
                  (row) =>
                    row.id === a.image_signal_id ||
                    a.profile_signal_ids.includes(row.id) ||
                    busy(row),
                )
                .map((row) => {
                  const job = row.job_id ? editor.jobs[row.job_id] : undefined;
                  return (
                    <div
                      className="signal-chip"
                      key={row.id}
                      data-testid="profile-chip"
                      data-signal-id={row.id}
                    >
                      <button
                        className="signal-chip-details"
                        title={`${label(row)} · ${row.recipe?.source === "stored" ? "Stored channel" : "Raw integration"}${row.recipe ? ` · frames ${row.recipe.frames[0]}–${row.recipe.frames[1]}` : ""}`}
                        onClick={() => onDetails(row.id)}
                      >
                        <CurveMarker style={curveStyle(row.style_index)} />
                        <span>{label(row)}</span>
                        {busy(row) && (
                          <span role="status">
                            {job?.status === "queued"
                              ? "Queued"
                              : `Calculating ${job?.done ?? 0}/${job?.total ?? "…"}`}
                          </span>
                        )}
                        {job &&
                          ["failed", "cancelled", "obsolete"].includes(
                            job.status,
                          ) && <span>{job.status}</span>}
                      </button>
                      {busy(row) ? (
                        <button
                          aria-label={`Cancel ${row.name} calculation`}
                          onClick={() => void editor.cancel(row.job_id!)}
                        >
                          ×
                        </button>
                      ) : (
                        <button
                          aria-label={`Hide ${row.name} profile`}
                          disabled={row.id === a.image_signal_id}
                          title={
                            row.id === a.image_signal_id
                              ? "Image signal is always included"
                              : "Hide profile; keep signal"
                          }
                          onClick={() =>
                            act({
                              type: "set_profile_visible",
                              signal_id: row.id,
                              visible: false,
                            })
                          }
                        >
                          ×
                        </button>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>
        )}
        <div className="signal-strip-actions">
          <SignalPicker
            options={a.peaks}
            buttonLabel="Add signal"
            listboxLabel="Stored signals"
            placeholder="＋ Add signal"
            onChoose={(index) =>
              act({ type: "add_stored_signal", index, duplicate: false })
            }
            onOpen={() => setManaging(false)}
            onCreate={editor.openNew}
            createDisabled={editor.submitting || !!editor.draft?.submittedJobId}
          />
          <button
            onClick={() => setManaging(true)}
            aria-haspopup="dialog"
            aria-expanded={managing}
          >
            Manage signals
          </button>
        </div>
      </div>
      {managing && active && (
        <ToolPopover
          title="Manage signals"
          width={680}
          onClose={() => setManaging(false)}
        >
          <SignalCollection
            analysis={a}
            send={send}
            editor={editor}
            onDetails={onDetails}
          />
        </ToolPopover>
      )}
      {details && active && (
        <SignalDetails
          key={details.id}
          signal={details}
          send={send}
          editor={editor}
          onClose={() => onDetails(undefined)}
        />
      )}
    </section>
  );
}
