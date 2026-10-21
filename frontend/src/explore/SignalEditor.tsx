import { useLayoutEffect, useRef, useState } from "react";
import type { Analysis } from "../api/client";
import type { SignalEditorController } from "./useSignalEditor";
import { HelpHeading } from "../components/HelpButton";
import { help } from "./help";
function MassBoundInput({
  value,
  label,
  onFocus,
  onChange,
}: {
  value: string;
  label: string;
  onFocus: () => void;
  onChange: (value: string) => void;
}) {
  const [focused, setFocused] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  useLayoutEffect(() => {
    if (focused) input.current?.select();
  }, [focused]);
  const compact =
    value.trim() && Number.isFinite(Number(value))
      ? String(Number(Number(value).toFixed(2)))
      : value;
  return (
    <input
      ref={input}
      type="number"
      step="any"
      required
      aria-label={label}
      title={`Exact bound: ${value} Th`}
      value={focused ? value : compact}
      onFocus={() => {
        setFocused(true);
        onFocus();
      }}
      onBlur={() => setFocused(false)}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function SignalEditor({
  editor: e,
  analysis,
}: {
  editor: SignalEditorController;
  analysis: Analysis;
}) {
  const d = e.draft;
  if (!d) return null;
  const busy = e.submitting || !!d.submittedJobId;
  return (
    <section className="signal-editor" role="region" aria-label="Signal editor">
      <HelpHeading
        title={
          d.signalId &&
          analysis.signals.find((s) => s.id === d.signalId)?.recipe
            ? "Edit signal"
            : "New signal"
        }
        content={help.windows}
      />
      <p className="draft-status">
        {busy
          ? "Calculation submitted"
          : d.signalId
            ? "Changes not calculated"
            : "Draw on the spectrum or enter mass intervals."}
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void e.submit();
        }}
      >
        <fieldset disabled={busy}>
          <label className="signal-name-field">
            Signal name <span className="editable-hint">Editable</span>
            <input
              aria-label="Signal name"
              maxLength={128}
              required
              value={d.name}
              onChange={(event) => e.patchDraft({ name: event.target.value })}
            />
          </label>
          {d.intervals.map(([a, b], i) => (
            <div
              className={`mass-row ${i === d.selectedInterval ? "selected" : ""}`}
              key={i}
            >
              <button
                type="button"
                aria-label={`Edit interval ${i + 1}`}
                aria-pressed={i === d.selectedInterval}
                onClick={() => e.patchDraft({ selectedInterval: i })}
              >
                {i + 1}
              </button>
              <MassBoundInput
                label={`Mass lower ${i + 1}`}
                value={a}
                onFocus={() => e.patchDraft({ selectedInterval: i })}
                onChange={(value) =>
                  e.patchDraft({
                    intervals: d.intervals.map((v, j) =>
                      j === i ? [value, v[1]] : v,
                    ),
                  })
                }
              />
              <span>–</span>
              <MassBoundInput
                label={`Mass upper ${i + 1}`}
                value={b}
                onFocus={() => e.patchDraft({ selectedInterval: i })}
                onChange={(value) =>
                  e.patchDraft({
                    intervals: d.intervals.map((v, j) =>
                      j === i ? [v[0], value] : v,
                    ),
                  })
                }
              />
              <button
                type="button"
                aria-label={`Remove interval ${i + 1}`}
                disabled={d.intervals.length === 1}
                onClick={() =>
                  e.patchDraft({
                    intervals: d.intervals.filter((_, j) => j !== i),
                    selectedInterval: 0,
                  })
                }
              >
                ×
              </button>
            </div>
          ))}
          <button
            type="button"
            disabled={d.intervals.length >= 128}
            onClick={() =>
              e.patchDraft({
                intervals: [
                  ...d.intervals,
                  [...d.intervals[d.selectedInterval]],
                ],
                selectedInterval: d.intervals.length,
              })
            }
          >
            Add interval
          </button>
          <label className="frame-label">Calculate over frames</label>
          <div className="exact-form">
            {["Calculation first", "Calculation last"].map((label, i) => (
              <label key={label}>
                {i === 0 ? "First" : "Last"}
                <input
                  type="number"
                  step="1"
                  min="0"
                  max={analysis.shape[0] - 1}
                  aria-label={label}
                  required
                  value={d.frames[i]}
                  onChange={(event) =>
                    e.patchDraft({
                      frames: d.frames.map((v, j) =>
                        j === i ? event.target.value : v,
                      ) as [string, string],
                    })
                  }
                />
              </label>
            ))}
          </div>
        </fieldset>
        <div className="row">
          <button className="primary" disabled={busy}>
            {d.signalId &&
            analysis.signals.find((s) => s.id === d.signalId)?.recipe
              ? "Update signal"
              : "Calculate signal"}
          </button>
          <button type="button" disabled={busy} onClick={e.requestClose}>
            Discard
          </button>
        </div>
      </form>
      {busy && (
        <div role="status" data-testid="job-status">
          {e.job?.status || "queued"} · {e.job?.done ?? 0}/{e.job?.total ?? "…"}
          <progress max={e.job?.total || 1} value={e.job?.done || 0} />
          <button disabled={!d.submittedJobId} onClick={() => void e.cancel()}>
            Cancel calculation
          </button>
        </div>
      )}
      {e.error && <p role="alert">{e.error}</p>}
      {e.pendingSwitch !== undefined && (
        <div role="alert">
          <p>Keep editing this signal or discard these changes?</p>
          <button onClick={e.keepEditing}>Keep editing</button>
          <button onClick={e.discardAndContinue}>Discard and continue</button>
        </div>
      )}
    </section>
  );
}
