import { formatNumber } from "../shared/numbers";
import { formatAbundance } from "./candidates";
import { useEffect, useState } from "react";
import {
  download,
  post,
  request,
  type Analysis,
  type Job,
} from "../api/client";
import type { components } from "../api/generated";
import { ToolPopover } from "../explore/ToolPopover";
type Result = components["schemas"]["MeasurementResult"];
const terminal = (job: Job) =>
  ["succeeded", "failed", "cancelled", "obsolete"].includes(job.status);
export function IsotopeMeasurements({
  analysis: a,
  active,
  refresh,
}: {
  analysis: Analysis;
  active: boolean;
  refresh: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false),
    [ids, setIds] = useState<string[]>([]);
  const [result, setResult] = useState<Result | null>(null),
    [job, setJob] = useState<Job>();
  const [error, setError] = useState(""),
    [submitting, setSubmitting] = useState(false);
  useEffect(() => {
    if (!active) setOpen(false);
  }, [active]);
  useEffect(() => {
    setOpen(false);
    setIds([]);
    setResult(null);
    setJob(undefined);
    setError("");
  }, [a.dataset.generation]);
  useEffect(() => {
    if (!open) return;
    let live = true;
    request<Result | null>(`/analyses/${a.id}/measurements`)
      .then((r) => {
        if (live) setResult(r);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [open, a.revision]);
  useEffect(() => {
    if (!open || !a.isotope_job_id) return;
    let live = true,
      polling = false;
    const poll = async () => {
      if (polling) return;
      polling = true;
      try {
        const value = await request<Job>(`/jobs/${a.isotope_job_id}`);
        if (!live) return;
        setJob(value);
        if (terminal(value)) {
          if (value.safe_error) setError(value.safe_error);
          await refresh();
        }
      } catch (e) {
        if (live) setError((e as Error).message);
      } finally {
        polling = false;
      }
    };
    void poll();
    const timer = setInterval(() => {
      if (!job || !terminal(job)) void poll();
    }, 300);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [open, a.isotope_job_id, job?.status, refresh]);
  const busy =
    submitting ||
    (!!a.isotope_job_id &&
      (!job || job.id !== a.isotope_job_id || !terminal(job)));
  const measure = async () => {
    setSubmitting(true);
    setError("");
    try {
      const value = await post<Job>(`/analyses/${a.id}/measurements`, {
        request_id: crypto.randomUUID(),
        expected_revision: a.revision,
        dataset_generation: a.dataset.generation,
        signal_ids: ids.filter((id) => a.signals.some((s) => s.id === id)),
      });
      setJob(value);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
      await refresh();
    } finally {
      setSubmitting(false);
    }
  };
  const csv = async () => {
    try {
      const response = await fetch(`/api/v1/analyses/${a.id}/isotopes.csv`, {
        credentials: "same-origin",
      });
      if (!response.ok) throw Error((await response.json()).message);
      const url = URL.createObjectURL(await response.blob()),
        link = document.createElement("a");
      link.href = url;
      link.download = "tofscope-isotopes.csv";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const totalIsZero =
    !!result?.rows.length &&
    result.rows.every((row) => row.measurement.summed_intensity === 0);
  const framesLabel = (frames: number[]) =>
    frames[0] === frames[1]
      ? `Frame ${frames[0]}`
      : `Frames ${frames[0]}–${frames[1]}`;
  return (
    <>
      <button onClick={() => setOpen(true)}>Isotope measurements</button>
      {open && (
        <ToolPopover
          title="Isotope measurements"
          width={900}
          placement="center"
          onClose={() => setOpen(false)}
          className="identification-dialog isotope-measurements"
        >
          <p className="measurement-intro">
            Compare signal intensities within the current region and viewing
            frames.
          </p>
          <div className="measurement-selection">
            <fieldset>
              <legend>Signals to measure</legend>
              {a.signals
                .filter((s) => s.recipe)
                .map((s) => (
                  <label key={s.id}>
                    <input
                      type="checkbox"
                      checked={ids.includes(s.id)}
                      onChange={(e) =>
                        setIds(
                          e.target.checked
                            ? [...ids, s.id]
                            : ids.filter((id) => id !== s.id),
                        )
                      }
                    />
                    {s.name}
                    {s.assignment && ` · ${s.assignment.candidate_id}`}
                  </label>
                ))}
            </fieldset>
            <div className="measurement-run row">
              <button
                disabled={
                  busy || !ids.some((id) => a.signals.some((s) => s.id === id))
                }
                onClick={() => void measure()}
              >
                Measure
              </button>
              {busy && (
                <button
                  onClick={() =>
                    a.isotope_job_id &&
                    void post(`/jobs/${a.isotope_job_id}/cancel`).catch((e) =>
                      setError(e.message),
                    )
                  }
                >
                  Cancel measurement
                </button>
              )}
              {job && (
                <span role="status" className="measurement-status">
                  {job.status === "succeeded"
                    ? "Calculation complete"
                    : `Measurement ${job.status}`}
                </span>
              )}
            </div>
          </div>
          {result && (
            <div data-testid="isotope-results">
              {result.out_of_date && (
                <p className="error">
                  Out of date — inputs changed. Measure again to update;
                  captured results remain below.
                </p>
              )}
              <h3>Results</h3>
              <div className="measurement-context">
                <div>
                  <strong>
                    Region: {result.roi[1] - result.roi[0] + 1} ×{" "}
                    {result.roi[3] - result.roi[2] + 1} pixels
                  </strong>
                  <span>
                    Columns {result.roi[0]}–{result.roi[1]}; rows{" "}
                    {result.roi[2]}–{result.roi[3]}
                  </span>
                </div>
                <div>
                  <strong>{framesLabel(result.frames)}</strong>
                  <span>
                    {result.frames[1] - result.frames[0] + 1} requested
                    acquisition{" "}
                    {result.frames[0] === result.frames[1] ? "frame" : "frames"}
                  </span>
                </div>
              </div>
              {result.rows.length === 1 && (
                <p className="measurement-note">
                  Only one signal was measured. Its share is 100% when intensity
                  is nonzero. Select two or more signals to compare their
                  shares.
                </p>
              )}
              <div className="isotope-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Signal / assignment</th>
                      <th>Summed intensity</th>
                      <th>Share of selected signals</th>
                      <th>Reference abundance</th>
                      <th>Measured frames / status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((r) => (
                      <tr key={r.signal_id}>
                        <td>
                          {r.name}
                          <br />
                          <span className="measurement-secondary">
                            {r.assignment?.candidate_id ??
                              "No isotope assigned"}
                          </span>
                        </td>
                        <td
                          title={
                            r.measurement.summed_intensity == null
                              ? undefined
                              : String(r.measurement.summed_intensity)
                          }
                        >
                          {formatNumber(r.measurement.summed_intensity)}
                          {r.measurement.summed_intensity === 0 && (
                            <span className="measurement-secondary">
                              No signal detected in this region/frame range
                            </span>
                          )}
                        </td>
                        <td>
                          {r.measurement.observed_fraction != null
                            ? `${formatNumber(100 * r.measurement.observed_fraction)}%`
                            : totalIsZero
                              ? "Unavailable — total intensity is zero"
                              : !r.measurement.actual_frames
                                ? "Unavailable — no common frame coverage"
                                : r.measurement.status ===
                                      "Overlapping mass windows" ||
                                    r.measurement.status ===
                                      "Ambiguous selected set"
                                  ? "Unavailable — overlapping mass windows"
                                  : "Unavailable"}
                        </td>
                        <td>
                          {r.assignment ? (
                            formatAbundance(r.assignment.isotope)
                          ) : (
                            <span className="measurement-secondary">
                              Assign an isotope to see its reference abundance
                            </span>
                          )}
                        </td>
                        <td>
                          {r.measurement.actual_frames
                            ? framesLabel(r.measurement.actual_frames)
                            : "No frames"}
                          <span className="measurement-secondary">
                            {r.measurement.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <details className="measurement-provenance">
                <summary>Measurement provenance</summary>
                <p>Dataset generation {result.dataset_generation}</p>
                <p>
                  Catalog retrieved {result.catalog.retrieved} · SHA-256{" "}
                  {result.catalog.records_sha256}
                </p>
                <pre>{result.catalog.sources_json}</pre>
              </details>
            </div>
          )}
          <details className="measurement-help">
            <summary>How these measurements work</summary>
            <p>
              Intensities are summed at original resolution within each signal's
              mass window, using the captured region and frames covered by every
              selected signal.
            </p>
            <p>
              A signal's share is its intensity divided by the total for the
              selected signals. These shares are not quantitative composition or
              natural isotope abundances. Overlapping mass windows cannot be
              compared this way.
            </p>
            <p>
              A signal name is only a label. Use Identify peak → Assign isotope
              to signal to attach an isotope identification and show its
              reference abundance.
            </p>
          </details>
          <div className="measurement-footer">
            <div className="row">
              <button
                onClick={() =>
                  void download(a.id, "json").catch((e) => setError(e.message))
                }
              >
                Settings JSON
              </button>
              <button disabled={!result} onClick={() => void csv()}>
                Isotope CSV
              </button>
            </div>
            <button onClick={() => setOpen(false)}>Close</button>
          </div>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </ToolPopover>
      )}
    </>
  );
}
