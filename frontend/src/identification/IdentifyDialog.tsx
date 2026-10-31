import { PreciseNumberInput } from "../components/PreciseNumberInput";
import { formatNumber } from "../shared/numbers";
import { useEffect, useRef, useState } from "react";
import { post, type Analysis, type Panel, type Job } from "../api/client";
import type { components } from "../api/generated";
import type { Send } from "../explore/SignalDetails";
import { ToolPopover } from "../explore/ToolPopover";
import { PlotPanel } from "../plots/PlotPanel";
import { snapPeak } from "./snapPeak";
import {
  orderCandidates,
  formatAbundance,
  type CandidateOrder,
} from "./candidates";
type Result = components["schemas"]["CandidateResult"];
const idOf = (c: Result["candidates"][number]) =>
  `${c.isotope.symbol}-${c.isotope.mass_number}:${c.charge > 0 ? "+" : ""}${c.charge}`;
export function IdentifyDialog({
  analysis: a,
  spectrum,
  send,
  active,
  onDraft,
  refresh,
}: {
  analysis: Analysis;
  spectrum?: Panel;
  send: Send;
  active: boolean;
  onDraft: (
    candidateId: string,
    interval: [number, number],
    measuredMz: number,
  ) => void;
  refresh: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false),
    [mz, setMz] = useState("");
  const [tolerance, setTolerance] = useState("0.3"),
    [unit, setUnit] = useState<"Th" | "ppm">("Th");
  const [charges, setCharges] = useState([1]);
  const [spectrumLog, setSpectrumLog] = useState(true);
  const [order, setOrder] = useState<CandidateOrder>("abundance");
  const [includeUnlisted, setIncludeUnlisted] = useState(false);
  const [result, setResult] = useState<Result>(),
    [selected, setSelected] = useState("");
  const [signalId, setSignalId] = useState(a.image_signal_id);
  const [low, setLow] = useState(""),
    [high, setHigh] = useState("");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const serial = useRef(0);
  const invalidate = () => {
    serial.current++;
    setBusy(false);
    setResult(undefined);
    setSelected("");
    setError("");
  };
  const pick = (value: number) => {
    invalidate();
    setMz(String(value));
    setLow(String(Math.max(a.mass_limits[0], value - 0.1)));
    setHigh(String(Math.min(a.mass_limits[1], value + 0.1)));
  };
  useEffect(() => {
    if (!active) setOpen(false);
  }, [active]);
  useEffect(() => {
    invalidate();
    setOpen(false);
    setMz("");
    setSignalId(a.image_signal_id);
  }, [a.dataset.generation]);
  const close = () => {
    serial.current++;
    setBusy(false);
    setOpen(false);
  };
  const find = async (
    mass = mz,
    settings: {
      tolerance?: string;
      unit?: "Th" | "ppm";
      charges?: number[];
    } = {},
  ) => {
    const nextTolerance = settings.tolerance ?? tolerance;
    const token = ++serial.current;
    setBusy(true);
    setError("");
    setSelected("");
    setResult(undefined);
    try {
      if (!mass.trim() || !nextTolerance.trim())
        throw Error("Enter a positive mass and a nonnegative tolerance.");
      const value = await post<Result>(`/analyses/${a.id}/candidates`, {
        mz: Number(mass),
        tolerance: Number(nextTolerance),
        unit: settings.unit ?? unit,
        charges: settings.charges ?? charges,
      });
      if (serial.current === token) setResult(value);
    } catch (e) {
      if (serial.current === token) setError((e as Error).message);
    } finally {
      if (serial.current === token) setBusy(false);
    }
  };
  const candidates = orderCandidates(
    result?.candidates ?? [],
    order,
    includeUnlisted,
  );
  const candidate = candidates.find((c) => idOf(c) === selected);
  const annotation = a.signals.find((s) => s.id === signalId)?.assignment;
  const interval = (): [number, number] => {
    const bounds: [number, number] = [Number(low), Number(high)];
    if (
      !low.trim() ||
      !high.trim() ||
      !bounds.every(Number.isFinite) ||
      bounds[0] >= bounds[1] ||
      bounds[0] < a.mass_limits[0] ||
      bounds[1] > a.mass_limits[1]
    )
      throw Error(
        "Enter ordered window bounds within the acquisition mass axis.",
      );
    return bounds;
  };
  const act = async (action: "annotate" | "clear" | "draft" | "comparison") => {
    setBusy(true);
    setError("");
    try {
      if (action === "annotate" || action === "clear") {
        await send({
          type: "annotate_signal",
          signal_id: signalId,
          candidate_id: action === "clear" ? null : selected,
          measured_mz: action === "clear" ? undefined : Number(mz),
        });
      } else {
        const bounds = interval();
        if (action === "draft") {
          onDraft(selected, bounds, Number(mz));
          close();
        } else {
          await post<Job>(`/analyses/${a.id}/jobs`, {
            request_id: crypto.randomUUID(),
            expected_revision: a.revision,
            dataset_generation: a.dataset.generation,
            spec: {
              name: selected,
              intervals: [bounds],
              frames: [0, a.shape[0] - 1],
              candidate_id: selected,
              measured_mz: Number(mz),
            },
          });
          await refresh();
          close();
        }
      }
    } catch (e) {
      setError((e as Error).message);
      await refresh();
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <button
        onClick={() => {
          setOpen(true);
          if (!mz) pick((a.mass_limits[0] + a.mass_limits[1]) / 2);
        }}
      >
        Identify peak
      </button>
      {open && (
        <ToolPopover
          title="Atomic identification"
          width={850}
          placement="center"
          onClose={close}
          className="identification-dialog atomic-identification"
        >
          <p className="identification-intro">
            Click a peak to find atomic isotope candidates automatically, or
            enter an exact m/z and choose Find candidates.
          </p>
          <form
            noValidate
            className="identification-search"
            onSubmit={(e) => {
              e.preventDefault();
              void find();
            }}
          >
            <label>
              Measured m/z
              <PreciseNumberInput
                label="Measured m/z"
                value={mz}
                onChange={(value) => {
                  invalidate();
                  setMz(value);
                }}
              />
            </label>
            <label>
              Tolerance
              <PreciseNumberInput
                label="Tolerance"
                min="0"
                step="0.1"
                value={tolerance}
                onChange={(value) => {
                  invalidate();
                  setTolerance(value);
                  if (value.trim()) void find(mz, { tolerance: value });
                }}
              />
            </label>
            <label>
              Tolerance unit
              <select
                aria-label="Tolerance unit"
                value={unit}
                onChange={(e) => {
                  invalidate();
                  const value = e.target.value as "Th" | "ppm";
                  setUnit(value);
                  void find(mz, { unit: value });
                }}
              >
                <option value="Th">Absolute m/z difference</option>
                <option>ppm</option>
              </select>
            </label>
            <button type="submit" disabled={busy}>
              Find candidates
            </button>
          </form>
          <fieldset className="identification-charges">
            <legend>Charge and polarity</legend>
            <div className="row">
              {[1, 2, 3, -1, -2, -3].map((z) => (
                <label key={z}>
                  <input
                    type="checkbox"
                    checked={charges.includes(z)}
                    onChange={(e) => {
                      invalidate();
                      const values = e.target.checked
                        ? [...charges, z]
                        : charges.filter((c) => c !== z);
                      setCharges(values);
                      void find(mz, { charges: values });
                    }}
                  />
                  {z > 0 ? "+" : ""}
                  {z}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="identification-spectrum">
            <PlotPanel
              name="identification"
              title="Identification spectrum"
              help="Click to pick a peak and find candidates immediately. Picks within seven display pixels of a local maximum snap to it; enter exact m/z above at any time. Drag to zoom. Log y is the default; use the scale control for linear intensity."
              panel={spectrum}
              maximized={false}
              onMaximize={() => {}}
              onSelect={() => {}}
              selectionMode="zoom"
              spectrumLog={spectrumLog}
              onSpectrumLogChange={setSpectrumLog}
              markers={[
                Number(mz),
                ...(candidate ? [candidate.predicted_mz] : []),
              ].filter(Number.isFinite)}
              onClick={(x, _, scale) => {
                const mass = snapPeak(
                  x,
                  scale,
                  spectrum?.axes[0].values ?? [],
                  spectrum?.series?.[0]?.values ?? [],
                );
                pick(mass);
                void find(String(mass));
              }}
            />
          </div>
          {result && (
            <section
              className="identification-results"
              aria-label="Ion candidates"
            >
              <div className="identification-result-options">
                <label>
                  Candidate order
                  <select
                    aria-label="Candidate order"
                    value={order}
                    onChange={(e) => setOrder(e.target.value as CandidateOrder)}
                  >
                    <option value="abundance">Natural abundance</option>
                    <option value="mass">Closest m/z</option>
                  </select>
                </label>
                <label className="identification-include">
                  <input
                    type="checkbox"
                    checked={includeUnlisted}
                    onChange={(e) => {
                      setIncludeUnlisted(e.target.checked);
                      setSelected("");
                    }}
                  />
                  Include isotopes without natural abundance
                </label>
              </div>
              <p className="identification-result-summary">
                {candidates.length} candidate
                {candidates.length === 1 ? "" : "s"} within {tolerance} {unit}
                {result.candidates.length > candidates.length
                  ? ` · ${result.candidates.length - candidates.length} without natural abundance hidden`
                  : ""}
              </p>
              {!!candidates.length && (
                <div className="isotope-table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Ion</th>
                        <th>Predicted m/z</th>
                        <th>Δm/z / ppm</th>
                        <th>Natural abundance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {candidates.map((c) => (
                        <tr
                          key={idOf(c)}
                          className={
                            selected === idOf(c) ? "selected" : undefined
                          }
                        >
                          <td>
                            <label className="isotope-choice">
                              <input
                                type="radio"
                                name="atomic-candidate"
                                aria-label={idOf(c)}
                                checked={selected === idOf(c)}
                                onChange={() => {
                                  setSelected(idOf(c));
                                  setLow(
                                    String(
                                      Math.max(
                                        a.mass_limits[0],
                                        Number(mz) - 0.1,
                                      ),
                                    ),
                                  );
                                  setHigh(
                                    String(
                                      Math.min(
                                        a.mass_limits[1],
                                        Number(mz) + 0.1,
                                      ),
                                    ),
                                  );
                                }}
                              />
                              {idOf(c)}
                            </label>
                          </td>
                          <td title={`Exact m/z: ${c.predicted_mz}`}>
                            {formatNumber(c.predicted_mz)}
                          </td>
                          <td>
                            {c.error_Th.toPrecision(4)} /{" "}
                            {c.error_ppm.toPrecision(4)}
                          </td>
                          <td>{formatAbundance(c.isotope)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!result.candidates.length && (
                <p>No atomic candidates within this tolerance.</p>
              )}
              {!!result.candidates.length && !candidates.length && (
                <p>
                  No matches have a tabulated natural abundance. Include
                  isotopes without natural abundance to inspect the other
                  masses.
                </p>
              )}
              <details className="identification-provenance">
                <summary>About natural abundance and catalog sources</summary>
                <p>
                  Natural abundance orders matching isotopes within your mass
                  tolerance; it is not an identification probability or sample
                  composition. The catalog also contains isotope masses with no
                  tabulated CIAAW natural abundance, including radioactive and
                  synthetic isotopes. Those entries are available with the
                  inclusion option above.
                </p>
                <p>{result.catalog.convention}</p>
                <p>
                  Retrieved {result.catalog.retrieved} · SHA-256{" "}
                  {result.catalog.records_sha256}
                </p>
                <pre>{result.catalog.sources_json}</pre>
                {candidate && (
                  <p>
                    Mass uncertainty:{" "}
                    {candidate.isotope.mass_uncertainty_u == null
                      ? "Not tabulated"
                      : formatNumber(candidate.isotope.mass_uncertainty_u)}{" "}
                    u · Abundance uncertainty:{" "}
                    {candidate.isotope.abundance_uncertainty == null
                      ? "Not tabulated"
                      : formatNumber(candidate.isotope.abundance_uncertainty)}
                  </p>
                )}
              </details>
            </section>
          )}
          <div className="identification-actions">
            <fieldset>
              <legend>Assign an isotope to an existing signal</legend>
              <label>
                Signal to assign
                <select
                  aria-label="Signal to assign"
                  value={signalId}
                  onChange={(e) => setSignalId(e.target.value)}
                >
                  {a.signals.map((s) => (
                    <option value={s.id} key={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="row">
                <button
                  disabled={busy || !candidate}
                  onClick={() => void act("annotate")}
                >
                  Assign isotope to signal
                </button>
                <button
                  disabled={busy || !annotation}
                  onClick={() => void act("clear")}
                >
                  Clear isotope assignment
                </button>
              </div>
              {annotation && <p>Assigned {annotation.candidate_id}</p>}
              <p className="identification-action-note">
                Original file labels stay unchanged.
              </p>
            </fieldset>
            <fieldset>
              <legend>Create a signal from this peak</legend>
              <div className="identification-window">
                <label>
                  Lower m/z
                  <PreciseNumberInput
                    label="Lower m/z"
                    value={low}
                    onChange={setLow}
                  />
                </label>
                <label>
                  Upper m/z
                  <PreciseNumberInput
                    label="Upper m/z"
                    value={high}
                    onChange={setHigh}
                  />
                </label>
              </div>
              <div className="row">
                <button
                  disabled={busy || !candidate}
                  onClick={() => void act("draft")}
                >
                  Apply window
                </button>
                <button
                  disabled={busy || !candidate}
                  onClick={() => void act("comparison")}
                >
                  Add comparison
                </button>
              </div>
              <p className="identification-action-note">
                Apply opens a draft. Add comparison calculates all acquisition
                frames.
              </p>
            </fieldset>
          </div>
          {error && (
            <p role="alert" className="calibration-error">
              {error}
            </p>
          )}
          <div className="identification-footer">
            <button onClick={close}>Close</button>
          </div>
        </ToolPopover>
      )}
    </>
  );
}
