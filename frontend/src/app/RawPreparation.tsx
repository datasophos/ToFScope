import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { post, request, type Job } from "../api/client";
import type { components } from "../api/generated";
import { folderName, useFolderLocations } from "./FolderLocations";

export type PreparationPreview = components["schemas"]["PreparationPreview"];
export type RawSelection = {
  name: string;
  path: string;
  location: "acquisition" | "saved";
  preview: PreparationPreview;
};

export function RawPreparation({
  selection,
  onCancel,
  onPrepared,
}: {
  selection: RawSelection;
  onCancel: () => void;
  onPrepared: (path: string) => Promise<void>;
}) {
  const { folders } = useFolderLocations();
  const [name, setName] = useState(selection.preview.suggested_filename);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dialog = useRef<HTMLElement>(null);
  const active =
    busy ||
    (!!job &&
      !["succeeded", "failed", "cancelled", "obsolete"].includes(job.status));
  useEffect(() => {
    dialog.current?.querySelector<HTMLInputElement>("input")?.focus();
  }, []);
  useEffect(() => {
    if (
      !job ||
      ["succeeded", "failed", "cancelled", "obsolete"].includes(job.status)
    )
      return;
    let alive = true;
    const timer = setTimeout(() => {
      request<Job>(`/jobs/${job.id}`)
        .then(async (next) => {
          if (!alive) return;
          setJob(next);
          if (next.status === "succeeded" && next.saved_file) {
            setBusy(true);
            try {
              await onPrepared(next.saved_file.id);
            } catch (e) {
              setError(
                `Copy prepared as ${next.saved_file.name}. ${(e as Error).message}`,
              );
            } finally {
              setBusy(false);
            }
          } else if (next.status === "cancelled") {
            setError("Preparation cancelled. The raw file is unchanged.");
          } else if (["failed", "obsolete"].includes(next.status)) {
            setError(
              next.safe_error ||
                "The source changed. Return to the file list and try again.",
            );
          }
        })
        .catch((e) => {
          if (alive) {
            setError(e.message);
            setJob({ ...job });
          }
        });
    }, 300);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [job]);
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      setJob(
        await post<Job>("/acquisitions/prepare", {
          relative_path: selection.path,
          location: selection.location,
          generation: selection.preview.generation,
          filename: name,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const keys = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape" && !active) {
      event.preventDefault();
      onCancel();
    }
    if (event.key !== "Tab") return;
    const nodes = dialog.current?.querySelectorAll<HTMLElement>(
      "button:not([disabled]), input:not([disabled])",
    );
    if (!nodes?.length) return;
    const first = nodes[0],
      last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  const [frames, y, x, channels] = selection.preview.shape;
  return (
    <div className="scrim">
      <section
        className="dialog raw-preparation"
        role="dialog"
        aria-modal="true"
        aria-label="Prepare raw acquisition"
        ref={dialog}
        onKeyDown={keys}
      >
        <h2>Prepare raw acquisition?</h2>
        <p>
          <strong>{selection.name}</strong> has raw events but no integrated ion
          maps. ToFScope will integrate its {channels} peak windows across{" "}
          {frames.toLocaleString()} completed frames ({x} × {y} pixels) and open
          a new copy. This can take several minutes.
        </p>
        <p>
          The original file will remain unchanged. At least{" "}
          {(selection.preview.required_bytes / 1024 ** 3).toFixed(2)} GB of free
          space is required to start. Final size depends on compression;
          preparation stops safely if space runs low.
        </p>
        <label className="preparation-filename">
          Prepared filename
          <input
            aria-label="Prepared filename"
            value={name}
            disabled={active || job?.status === "succeeded"}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <p>
          Save in{" "}
          <strong title={folders?.save_destination}>
            {folders?.save_destination
              ? folderName(folders.save_destination)
              : "Saved files"}
          </strong>
        </p>
        {job && (
          <div role="status" aria-live="polite">
            <p>
              {job.stage || job.status}
              {job.total > 0
                ? ` · ${job.done.toLocaleString()}/${job.total.toLocaleString()}`
                : ""}
            </p>
            <progress
              aria-label="Preparation progress"
              max={job.total || 1}
              value={job.done}
            />
          </div>
        )}
        {error && <p role="alert">{error}</p>}
        <div className="row preparation-actions">
          {active ? (
            <button
              disabled={!job || busy}
              onClick={async () => {
                try {
                  setJob(await post<Job>(`/jobs/${job!.id}/cancel`));
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Cancel preparation
            </button>
          ) : (
            <>
              <button onClick={onCancel}>Back to files</button>
              {job?.status === "succeeded" && job.saved_file ? (
                <button
                  className="primary"
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await onPrepared(job.saved_file!.id);
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Open prepared copy
                </button>
              ) : (
                <button
                  className="primary"
                  disabled={!name.trim()}
                  onClick={() => void start()}
                >
                  Prepare and open
                </button>
              )}
            </>
          )}
        </div>
      </section>
    </div>
  );
}
