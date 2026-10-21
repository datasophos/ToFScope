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
  return (
    <>
      <button onClick={() => setOpen(true)}>Isotope measurements</button>
      {open && (
        <ToolPopover
          title="Isotope measurements"
          width={900}
          placement="center"
          onClose={() => setOpen(false)}
          className="identification-dialog"
        >
          <p>
            Choose signals, then Measure. Sums use original intensities within
            the current ROI and viewing frames, restricted to common signal
            coverage. Fractions describe the selected signal set, not
            quantitative composition.
          </p>
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
          <div className="row">
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
            <button onClick={() => setOpen(false)}>Close</button>
          </div>
          {job && <p role="status">Measurement {job.status}</p>}
          {result && (
            <div data-testid="isotope-results">
              {result.out_of_date && (
                <p className="error">
                  Out of date — inputs changed. Measure again to update;
                  captured results remain below.
                </p>
              )}
              <p>
                Captured ROI {result.roi.join(", ")} · requested frames{" "}
                {result.frames.join("–")}
              </p>
              <div className="isotope-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Signal / assignment</th>
                      <th>Original intensity sum</th>
                      <th>Observed fraction</th>
                      <th>Reference abundance</th>
                      <th>Actual frames / status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((r) => (
                      <tr key={r.signal_id}>
                        <td>
                          {r.name}
                          <br />
                          {r.assignment?.candidate_id ?? "Unassigned"}
                        </td>
                        <td>
                          {r.measurement.summed_intensity ?? "Unavailable"}
                        </td>
                        <td>
                          {r.measurement.observed_fraction?.toPrecision(6) ??
                            "Unavailable"}
                        </td>
                        <td>
                          {r.assignment?.isotope.abundance_low == null
                            ? "Unknown"
                            : `${r.assignment.isotope.abundance_low}–${r.assignment.isotope.abundance_high}`}
                        </td>
                        <td>
                          {r.measurement.actual_frames?.join("–") ?? "None"} ·{" "}
                          {r.measurement.status}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <details>
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
