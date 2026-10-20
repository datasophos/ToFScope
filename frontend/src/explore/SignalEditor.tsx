import type { Analysis } from "../api/client";
import type { SignalEditorController } from "./useSignalEditor";
import { HelpHeading } from "../components/HelpButton";
import { help } from "./help";
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
          <label>
            Signal name
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
              <input
                type="number"
                step="any"
                required
                aria-label={`Mass lower ${i + 1}`}
                value={a}
                onFocus={() => e.patchDraft({ selectedInterval: i })}
                onChange={(event) =>
                  e.patchDraft({
                    intervals: d.intervals.map((v, j) =>
                      j === i ? [event.target.value, v[1]] : v,
                    ),
                  })
                }
              />
              <span>–</span>
              <input
                type="number"
                step="any"
                required
                aria-label={`Mass upper ${i + 1}`}
                value={b}
                onFocus={() => e.patchDraft({ selectedInterval: i })}
                onChange={(event) =>
                  e.patchDraft({
                    intervals: d.intervals.map((v, j) =>
                      j === i ? [v[0], event.target.value] : v,
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
