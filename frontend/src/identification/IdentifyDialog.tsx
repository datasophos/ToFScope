import { useEffect, useRef, useState } from "react";
import { post, type Analysis, type Panel, type Job } from "../api/client";
import type { components } from "../api/generated";
import type { Send } from "../explore/SignalDetails";
import { ToolPopover } from "../explore/ToolPopover";
import { PlotPanel } from "../plots/PlotPanel";
import { snapPeak } from "./snapPeak";
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
  onDraft: (name: string, interval: [number, number]) => void;
  refresh: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false),
    [mz, setMz] = useState("");
  const [tolerance, setTolerance] = useState("0.1"),
    [unit, setUnit] = useState<"Th" | "ppm">("Th");
  const [charges, setCharges] = useState([1]);
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
    setOpen(false);
  };
  const find = async () => {
    const token = ++serial.current;
    setBusy(true);
    setError("");
    setSelected("");
    setResult(undefined);
    try {
      if (!mz.trim() || !tolerance.trim())
        throw Error("Enter a positive mass and a nonnegative tolerance.");
      const value = await post<Result>(`/analyses/${a.id}/candidates`, {
        mz: Number(mz),
        tolerance: Number(tolerance),
        unit,
        charges,
      });
      if (serial.current === token) setResult(value);
    } catch (e) {
      if (serial.current === token) setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const candidate = result?.candidates.find((c) => idOf(c) === selected);
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
          onDraft(selected, bounds);
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
          className="identification-dialog"
        >
          <p>
            Atomic isotope ions, charges ±1 to ±3. Candidates are suggestions.
            Original file labels remain available.
          </p>
          <div className="row">
            <label>
              Measured m/z
              <input
                type="number"
                step="any"
                value={mz}
                onChange={(e) => {
                  invalidate();
                  setMz(e.target.value);
                }}
              />
            </label>
            <label>
              Tolerance
              <input
                type="number"
                min="0"
                step="any"
                value={tolerance}
                onChange={(e) => {
                  invalidate();
                  setTolerance(e.target.value);
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
                  setUnit(e.target.value as "Th" | "ppm");
                }}
              >
                <option>Th</option>
                <option>ppm</option>
              </select>
            </label>
            <button disabled={busy} onClick={() => void find()}>
              Find candidates
            </button>
          </div>
          <fieldset>
            <legend>Charge and polarity</legend>
            <div className="row">
              {[1, 2, 3, -1, -2, -3].map((z) => (
                <label key={z}>
                  <input
                    type="checkbox"
                    checked={charges.includes(z)}
                    onChange={(e) => {
                      invalidate();
                      setCharges(
                        e.target.checked
                          ? [...charges, z]
                          : charges.filter((c) => c !== z),
                      );
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
              help="Click within seven display pixels of a local maximum to snap; enter exact m/z above at any time. Drag to zoom."
              panel={spectrum}
              maximized={false}
              onMaximize={() => {}}
              onSelect={() => {}}
              selectionMode="zoom"
              markers={[
                Number(mz),
                ...(candidate ? [candidate.predicted_mz] : []),
              ].filter(Number.isFinite)}
              onClick={(x, _, scale) =>
                pick(
                  snapPeak(
                    x,
                    scale,
                    spectrum?.axes[0].values ?? [],
                    spectrum?.series?.[0]?.values ?? [],
                  ),
                )
              }
            />
          </div>
          {result && (
            <>
              <div className="isotope-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Ion</th>
                      <th>Predicted m/z</th>
                      <th>Error Th / ppm</th>
                      <th>Reference abundance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.candidates.map((c) => (
                      <tr key={idOf(c)}>
                        <td>
                          <label>
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
                        <td>{c.predicted_mz.toPrecision(10)}</td>
                        <td>
                          {c.error_Th.toPrecision(4)} /{" "}
                          {c.error_ppm.toPrecision(4)}
                        </td>
                        <td>
                          {c.isotope.abundance_low == null
                            ? "Unknown"
                            : `${c.isotope.abundance_low}–${c.isotope.abundance_high}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!result.candidates.length && (
                <p>No atomic candidates within this tolerance.</p>
              )}
              <details>
                <summary>Catalog provenance and mass convention</summary>
                <p>{result.catalog.convention}</p>
                <p>
                  Retrieved {result.catalog.retrieved} · SHA-256{" "}
                  {result.catalog.records_sha256}
                </p>
                <pre>{result.catalog.sources_json}</pre>
                {candidate && (
                  <p>
                    Mass uncertainty:{" "}
                    {candidate.isotope.mass_uncertainty_u ?? "Unknown"} u ·
                    Abundance uncertainty:{" "}
                    {candidate.isotope.abundance_uncertainty ?? "Unknown"}
                  </p>
                )}
              </details>
            </>
          )}
          <div className="row">
            <label>
              Signal to annotate
              <select
                aria-label="Signal to annotate"
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
            <button
              disabled={busy || !candidate}
              onClick={() => void act("annotate")}
            >
              Annotate signal
            </button>
            <button
              disabled={busy || !annotation}
              onClick={() => void act("clear")}
            >
              Clear annotation
            </button>
          </div>
          {annotation && <p>Assigned {annotation.candidate_id}</p>}
          <div className="row">
            <label>
              Window lower Th
              <input
                type="number"
                step="any"
                value={low}
                onChange={(e) => setLow(e.target.value)}
              />
            </label>
            <label>
              Window upper Th
              <input
                type="number"
                step="any"
                value={high}
                onChange={(e) => setHigh(e.target.value)}
              />
            </label>
          </div>
          <p>
            Apply window opens a draft for review. Add comparison calculates a
            new named signal across all acquisition frames.
          </p>
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
            <button onClick={close}>Close</button>
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
