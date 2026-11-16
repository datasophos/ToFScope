import { useEffect, useState } from "react";
import { post, request, type Analysis, type Job } from "../api/client";
import type { SpectrumResult } from "./subvolumeSpectrum";

export function useSubvolumeSpectrum(analysis: Analysis) {
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<SpectrumResult | null>(null);
  const [showSelected, setShowSelected] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const busy =
    submitting || (!!job && ["queued", "running"].includes(job.status));

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    let alive = true;
    const timer = setTimeout(async () => {
      try {
        const next = await request<Job>(`/jobs/${job.id}`);
        if (!alive) return;
        if (next.status === "succeeded") {
          const spectrum = await request<SpectrumResult | null>(
            `/analyses/${analysis.id}/spectrum`,
          );
          if (!alive) return;
          if (spectrum?.job_id === next.id) {
            setResult(spectrum);
            setShowSelected(true);
          } else
            setError(
              "Spectrum result is no longer available. Calculate it again.",
            );
        } else if (next.status === "failed" || next.status === "obsolete") {
          setError(
            next.safe_error || "Spectrum calculation is no longer current.",
          );
        }
        setJob(next);
      } catch (e) {
        if (alive) {
          setError((e as Error).message);
          setJob(null);
        }
      }
    }, 300);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [job, analysis.id]);

  useEffect(() => {
    setResult(null);
    setShowSelected(false);
    setJob(null);
    setError("");
  }, [analysis.dataset.generation]);

  const calculate = async () => {
    setSubmitting(true);
    setError("");
    try {
      const next = await post<Job>(`/analyses/${analysis.id}/spectrum`, {
        request_id: crypto.randomUUID(),
        expected_revision: analysis.revision,
        dataset_generation: analysis.dataset.generation,
      });
      setJob(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };
  const cancel = async () => {
    if (!job) return;
    try {
      setJob(await post<Job>(`/jobs/${job.id}/cancel`));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return {
    job,
    result,
    showSelected,
    setShowSelected,
    error,
    busy,
    calculate,
    cancel,
  };
}
