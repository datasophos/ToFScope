import { useEffect, useRef, useState } from "react";
import { FolderLocations } from "../app/FolderLocations";
import { post, request, type Analysis, type Job } from "../api/client";

export function SaveCopy({
  analysis,
  blocked,
  active,
  saveRequest = 0,
  onSaved,
  onDismiss,
}: {
  analysis: Analysis;
  blocked: string;
  active: boolean;
  saveRequest?: number;
  onSaved: (latest: Analysis) => void;
  onDismiss: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(
    () =>
      (analysis.dataset.name || "acquisition.h5").replace(/\.(h5|hdf5)$/i, "") +
      "_analysis.h5",
  );
  const [job, setJob] = useState<Job | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const savedCallback = useRef(onSaved);
  savedCallback.current = onSaved;
  const running = !!job && ["queued", "running"].includes(job.status);
  useEffect(() => {
    if (saveRequest) setOpen(true);
  }, [saveRequest]);
  useEffect(() => {
    if (!job?.id) return;
    let alive = true,
      polling = false;
    const poll = async () => {
      if (polling) return;
      polling = true;
      try {
        const next = await request<Job>(`/jobs/${job.id}`);
        if (!alive) return;
        setJob(next);
        if (!["queued", "running"].includes(next.status)) {
          clearInterval(timer);
          if (next.status === "succeeded") {
            const latest = await request<Analysis>(`/analyses/${analysis.id}`);
            if (alive) savedCallback.current(latest);
          } else
            setError(
              next.safe_error ||
                (next.status === "cancelled"
                  ? "Save cancelled. Your analysis is unchanged."
                  : "Save did not complete. Save the current analysis again."),
            );
        }
      } catch (e) {
        if (alive) setError((e as Error).message);
      } finally {
        polling = false;
      }
    };
    const timer = setInterval(() => void poll(), 250);
    void poll();
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [job?.id, analysis.id]);
  const close = () => {
    setOpen(false);
    onDismiss();
  };
  return (
    <>
      <button
        disabled={!!blocked}
        title={blocked || "Save a self-contained HDF5 copy"}
        onClick={() => {
          setError("");
          if (job?.saved_revision !== analysis.revision) setJob(null);
          setOpen(true);
        }}
      >
        Save as…
      </button>
      {open && active && (
        <div className="scrim">
          <section
            className="dialog save-copy"
            role="dialog"
            aria-label="Save a copy"
          >
            <header>
              <h2>Save a copy</h2>
              <button aria-label="Close save dialog" onClick={close}>
                ×
              </button>
            </header>
            <p>
              The new HDF5 file includes your committed signals, results and
              analysis settings. The original stays unchanged.
            </p>
            <FolderLocations
              save
              filename={
                job?.status === "succeeded"
                  ? job.saved_file?.name || name
                  : name
              }
            />
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                if (blocked || running || submitting) return;
                setSubmitting(true);
                setJob(null);
                setError("");
                try {
                  const result = await post<Job>(
                    `/analyses/${analysis.id}/saves`,
                    {
                      request_id: crypto.randomUUID(),
                      expected_revision: analysis.revision,
                      dataset_generation: analysis.dataset.generation,
                      filename: name,
                    },
                  );
                  setJob(result);
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setSubmitting(false);
                }
              }}
            >
              <label>
                Saved filename
                <input
                  aria-label="Saved filename"
                  value={name}
                  maxLength={240}
                  required
                  disabled={running || submitting}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <button
                disabled={!!blocked || running || submitting || !name.trim()}
              >
                Save copy
              </button>
            </form>
            {blocked && <p>{blocked}</p>}
            {error && <p role="alert">{error}</p>}
            {running && (
              <div role="status">
                <p>{job.stage || job.status}</p>
                <progress value={job.done} max={job.total || 1} />
                <button
                  onClick={() =>
                    void post<Job>(`/jobs/${job.id}/cancel`)
                      .then(setJob)
                      .catch((e) => setError(e.message))
                  }
                >
                  Cancel save
                </button>
              </div>
            )}
            {job?.status === "succeeded" && job.saved_file && (
              <div>
                <p role="status">Copy saved.</p>
                <p>{job.saved_file.name}</p>
                <p className="muted">
                  Large files may take a long time to download. Downloading is
                  optional; the saved copy stays on the server.
                </p>
                <a
                  className="download-copy"
                  href={`/api/v1/saved-files/${job.saved_file.id}/download`}
                  download={job.saved_file.name}
                >
                  Download copy
                </a>
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}
