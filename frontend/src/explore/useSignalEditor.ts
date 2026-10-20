import { useEffect, useRef, useState } from "react";
import {
  post,
  request,
  type Analysis,
  type Job,
  type JobInput,
} from "../api/client";
import {
  createDraft,
  openDraft,
  patchDraft,
  finishDraft,
  type EditorState,
  type SignalDraft,
} from "./signalEditorState";
const terminal = (status: string) =>
  ["succeeded", "failed", "cancelled", "obsolete"].includes(status);
export function useSignalEditor(
  analysis: Analysis,
  refresh: () => Promise<void>,
) {
  const [state, setState] = useState<EditorState>({ draft: null });
  const [jobs, setJobs] = useState<Record<string, Job>>({});
  const jobsRef = useRef(jobs);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [lastCreatedId, setLastCreatedId] = useState<string>();
  const ids = analysis.signals
    .map((s) => s.job_id)
    .filter((id): id is string => Boolean(id))
    .join(",");
  useEffect(() => {
    let alive = true,
      polling = false;
    const poll = async () => {
      if (polling) return;
      polling = true;
      try {
        for (const id of ids.split(",").filter(Boolean)) {
          if (jobsRef.current[id] && terminal(jobsRef.current[id].status))
            continue;
          const job = await request<Job>(`/jobs/${id}`);
          if (!alive) return;
          jobsRef.current = { ...jobsRef.current, [id]: job };
          setJobs(jobsRef.current);
          if (terminal(job.status)) {
            setState((s) => finishDraft(s, id, job.status));
            if (job.status === "succeeded") setLastCreatedId(job.signal_id);
            if (job.safe_error) setError(job.safe_error);
            await refresh();
          }
        }
      } catch (e) {
        if (alive) setError((e as Error).message);
      } finally {
        polling = false;
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), 250);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [ids, refresh]);
  const open = (draft: SignalDraft | null) => {
    setError("");
    setState((s) => openDraft(s, draft));
  };
  const seed = (id: string, copy: boolean) => {
    const row = analysis.signals.find((s) => s.id === id);
    if (!row?.recipe) return;
    open(
      createDraft(
        copy ? `${row.name.slice(0, 120)} copy` : row.name,
        row.recipe.intervals,
        row.recipe.frames,
        copy ? undefined : id,
      ),
    );
  };
  const submit = async () => {
    const d = state.draft;
    if (!d || d.submittedJobId || submitting) return;
    setError("");
    setSubmitting(true);
    try {
      const row = analysis.signals.find((s) => s.id === d.signalId);
      const body: JobInput = {
        request_id: crypto.randomUUID(),
        expected_revision: analysis.revision,
        dataset_generation: analysis.dataset.generation,
        spec: {
          name: d.name,
          intervals: d.intervals.map(([a, b]) => [Number(a), Number(b)]),
          frames: [Number(d.frames[0]), Number(d.frames[1])],
          signal_id: d.signalId,
          expected_recipe_version: row?.recipe_version,
        },
      };
      if (
        !d.name.trim() ||
        d.intervals.some((w) =>
          w.some((v) => !v.trim() || !Number.isFinite(Number(v))),
        ) ||
        d.frames.some((v) => !v.trim() || !Number.isInteger(Number(v)))
      )
        throw Error(
          "Enter a name, finite mass bounds and integer frame limits.",
        );
      let job: Job;
      try {
        job = await post(`/analyses/${analysis.id}/jobs`, body);
      } catch (e) {
        if (!(e instanceof TypeError)) throw e;
        job = await post(`/analyses/${analysis.id}/jobs`, body);
      }
      setState((s) =>
        s.draft === d
          ? {
              ...s,
              draft: { ...d, signalId: job.signal_id, submittedJobId: job.id },
            }
          : s,
      );
      await refresh();
    } catch (e) {
      setError((e as Error).message);
      await refresh();
    } finally {
      setSubmitting(false);
    }
  };
  const job = state.draft?.submittedJobId
    ? jobs[state.draft.submittedJobId]
    : undefined;
  return {
    ...state,
    jobs,
    job,
    error,
    submitting,
    lastCreatedId,
    openNew: () =>
      open(
        createDraft(
          `Signal ${analysis.next_style_index + 1}`,
          analysis.signals.find((s) => s.id === analysis.image_signal_id)
            ?.recipe?.intervals ?? [analysis.mass_limits],
          analysis.loaded_frames,
        ),
      ),
    openEdit: (id: string) => seed(id, false),
    openCopy: (id: string) => seed(id, true),
    patchDraft: (patch: Partial<SignalDraft>) =>
      setState((s) => patchDraft(s, patch)),
    requestClose: () => open(null),
    keepEditing: () => setState((s) => ({ ...s, pendingSwitch: undefined })),
    discardAndContinue: () =>
      setState((s) => ({ draft: s.pendingSwitch ?? null })),
    submit,
    cancel: async (id?: string) => {
      const jid = id || state.draft?.submittedJobId;
      if (jid) await post(`/jobs/${jid}/cancel`);
    },
    dismissError: () => setError(""),
  };
}
export type SignalEditorController = ReturnType<typeof useSignalEditor>;
