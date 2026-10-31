import { useId, useState } from "react";
import type { Analysis, Command, Signal } from "../api/client";
import { ToolPopover } from "./ToolPopover";
import { ExactForm } from "./ExactForm";
import type { SignalEditorController } from "./useSignalEditor";
export type Send = (command: Command) => Promise<Analysis>;
export function SignalDetails({
  signal,
  send,
  editor,
  onClose,
}: {
  signal: Signal;
  send: Send;
  editor: SignalEditorController;
  onClose: () => void;
}) {
  const [name, setName] = useState(signal.name);
  const [saving, setSaving] = useState(false);
  const nameId = useId();
  const changed = name !== signal.name;
  const recipe = signal.recipe;
  return (
    <ToolPopover title={`Signal details: ${signal.name}`} onClose={onClose}>
      <form
        className="signal-rename"
        onSubmit={(e) => {
          e.preventDefault();
          if (!changed || !name.trim() || saving) return;
          setSaving(true);
          void send({ type: "rename_signal", signal_id: signal.id, name })
            .then(onClose)
            .catch(() => {})
            .finally(() => setSaving(false));
        }}
      >
        <label htmlFor={nameId}>Rename signal</label>
        <div className="row">
          <input
            id={nameId}
            aria-label="Rename signal"
            value={name}
            maxLength={128}
            required
            disabled={saving}
            onChange={(e) => setName(e.target.value)}
          />
          {changed && (
            <button
              type="submit"
              aria-label="Save signal name"
              title="Save signal name"
              disabled={!name.trim() || saving}
            >
              ✓
            </button>
          )}
        </div>
      </form>
      {recipe && (
        <>
          <p>
            <strong>
              {recipe.source === "stored"
                ? "Stored channel"
                : "Raw integration"}
            </strong>{" "}
            · {recipe.frames[0]}–{recipe.frames[1]} frames
          </p>
          <p
            data-mass-intervals
            title={`m/z ${recipe.intervals.map(([a, b]) => `${a}–${b}`).join(" ∪ ")}`}
          >
            m/z {recipe.intervals
              .map(([a, b]) => `${a.toFixed(2)}–${b.toFixed(2)}`)
              .join(" ∪ ")}
          </p>
          {recipe.source === "stored" && (
            <ExactForm
              labels={["Coverage first", "Coverage last"]}
              values={recipe.frames}
              button="Update coverage"
              onApply={(frames) =>
                void send({
                  type: "set_stored_coverage",
                  signal_id: signal.id,
                  frames: frames as [number, number],
                }).catch(() => {})
              }
            />
          )}
          <div className="row">
            {recipe.source === "custom" && (
              <button
                onClick={() => {
                  editor.openEdit(signal.id);
                  onClose();
                }}
              >
                Edit signal
              </button>
            )}
            <button
              onClick={() => {
                editor.openCopy(signal.id);
                onClose();
              }}
            >
              {recipe.source === "stored" ? "Create custom copy" : "Duplicate"}
            </button>
            {recipe.source === "stored" && (
              <button
                onClick={() =>
                  void send({
                    type: "add_stored_signal",
                    index: recipe.stored_index!,
                    duplicate: true,
                    frames: recipe.frames,
                  })
                    .then(onClose)
                    .catch(() => {})
                }
              >
                Duplicate stored signal
              </button>
            )}
          </div>
        </>
      )}
    </ToolPopover>
  );
}
