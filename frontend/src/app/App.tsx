import { useCallback, useEffect, useState } from "react";
import {
  authenticate,
  request,
  post,
  type Analysis,
  type Session,
} from "../api/client";
import { UnsavedChanges } from "./UnsavedChanges";
import { FilePicker } from "./FilePicker";
import { ExploreScreen } from "../explore/ExploreScreen";
import { HelpButton } from "../components/HelpButton";
import { help } from "../explore/help";
export function App() {
  const [session, setSession] = useState<Session | null>(null),
    [analyses, setAnalyses] = useState<Analysis[]>([]),
    [active, setActive] = useState(""),
    [picker, setPicker] = useState(false),
    [replace, setReplace] = useState<Analysis | null>(null),
    [error, setError] = useState("");
  const [statuses, setStatuses] = useState<
    Record<string, { analysis: Analysis; draft: boolean; busy: boolean }>
  >({});
  const [pendingAction, setPendingAction] = useState<{
    id: string;
    kind: "close" | "replace";
  } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [saveRequest, setSaveRequest] = useState<{
    id: string;
    serial: number;
  } | null>(null);
  const reportStatus = useCallback(
    (a: Analysis, draft: boolean, busy: boolean) => {
      setStatuses((old) => {
        const previous = old[a.id];
        if (
          previous?.analysis.revision === a.revision &&
          previous.analysis.saved_revision === a.saved_revision &&
          previous.analysis.dataset.generation === a.dataset.generation &&
          previous.draft === draft &&
          previous.busy === busy
        )
          return old;
        return { ...old, [a.id]: { analysis: a, draft, busy } };
      });
    },
    [],
  );
  const unsaved = analyses.some((a) => {
    const info = statuses[a.id];
    const latest = info?.analysis || a;
    return info?.draft || latest.saved_revision !== latest.revision;
  });
  useEffect(() => {
    if (!unsaved) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [unsaved]);
  useEffect(() => {
    let alive = true;
    authenticate()
      .then(async (s) => {
        const restored = await request<Analysis[]>("/analyses");
        if (!alive) return;
        setSession(s);
        setAnalyses(restored);
        const selected = sessionStorage.getItem(`tofscope-active:${s.owner}`);
        setActive(
          restored.some((a) => a.id === selected)
            ? selected!
            : restored[0]?.id || "",
        );
        if (s.initial_file && !restored.length) {
          const a = await post<Analysis>("/analyses", {
            relative_path: s.initial_file,
          });
          if (alive) {
            setAnalyses([a]);
            setActive(a.id);
          }
        }
      })
      .catch((e) => setError(e.message));
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    if (!session) return;
    const t = setInterval(
      () =>
        request<Session>("/auth/session")
          .then((s) => {
            if (s.owner !== session.owner) {
              setAnalyses([]);
              setSession(null);
              setError("Identity changed. Reload to open your files.");
            }
          })
          .catch(() => {
            setAnalyses([]);
            setSession(null);
            setError("Session ended. Reopen from the launcher.");
          }),
      15000,
    );
    return () => clearInterval(t);
  }, [session]);
  useEffect(() => {
    if (session && active)
      sessionStorage.setItem(`tofscope-active:${session.owner}`, active);
  }, [session, active]);
  const open = async (path: string, location: "acquisition" | "saved") => {
    let a: Analysis;
    if (replace) {
      a = await post<Analysis>(`/analyses/${replace.id}/replace`, {
        request_id: crypto.randomUUID(),
        expected_revision: replace.revision,
        dataset_generation: replace.dataset.generation,
        relative_path: path,
        location,
      });
      setAnalyses((old) => old.map((x) => (x.id === a.id ? a : x)));
      setStatuses((old) => {
        const next = { ...old };
        delete next[a.id];
        return next;
      });
      setReplace(null);
    } else {
      a = await post<Analysis>("/analyses", {
        relative_path: path,
        location,
      });
      setAnalyses((old) => [...old, a]);
    }
    setActive(a.id);
    setPicker(false);
  };
  const close = async (a: Analysis) => {
    try {
      await request(`/analyses/${a.id}`, { method: "DELETE" });
      setAnalyses((old) => old.filter((x) => x.id !== a.id));
      setStatuses((old) => {
        const next = { ...old };
        delete next[a.id];
        return next;
      });
      if (active === a.id)
        setActive(analyses.find((x) => x.id !== a.id)?.id || "");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const perform = async (
    action: { id: string; kind: "close" | "replace" },
    latest?: Analysis,
  ) => {
    const a =
      latest ||
      statuses[action.id]?.analysis ||
      analyses.find((a) => a.id === action.id);
    if (!a) return;
    setPendingAction(null);
    setConfirming(false);
    setSaveRequest(null);
    if (action.kind === "close") await close(a);
    else {
      setReplace(a);
      setPicker(true);
    }
  };
  const requestAction = (a: Analysis, kind: "close" | "replace") => {
    const info = statuses[a.id];
    const latest = info?.analysis || a;
    const action = { id: a.id, kind };
    if (info?.draft || latest.saved_revision !== latest.revision) {
      setPendingAction(action);
      setConfirming(true);
    } else void perform(action, latest);
  };
  const pendingStatus = pendingAction ? statuses[pendingAction.id] : undefined;
  const pendingBlocked = pendingStatus?.draft
    ? "Finish or discard the signal draft before saving."
    : pendingStatus?.busy
      ? "Finish or cancel calculations before saving."
      : "";
  return (
    <>
      <header className="masthead">
        <div className="brand">
          <svg className="mark" viewBox="0 0 36 36" aria-hidden="true">
            <path d="M3 5h23v5h-9v21h-5V10H3z" fill="currentColor" />
            <circle cx="30" cy="28" r="3" fill="#44bdac" />
          </svg>
          <div className="brand-name">
            <strong>ToFScope</strong>
            <small>FIB–SEM / TOF–SIMS</small>
          </div>
          <span className="badge">Explore · originals read only</span>
        </div>
        <span>{session?.owner || "Local instrument"}</span>
      </header>
      <div className="file-bar">
        <button
          disabled={!session}
          onClick={() => {
            setReplace(null);
            setPicker(true);
          }}
        >
          ＋ Open acquisition
        </button>
        <HelpButton label="Files and saved analyses" content={help.files} />
        <div className="tabs" role="tablist">
          {analyses.map((a, i) => (
            <div key={a.id} className={a.id === active ? "tab active" : "tab"}>
              <button
                role="tab"
                aria-selected={a.id === active}
                onClick={() => setActive(a.id)}
              >
                {i + 1} ·{" "}
                {a.dataset.name || a.dataset.relative_path.split("/").pop()}
              </button>
              <button
                aria-label={`Close analysis ${i + 1}`}
                onClick={() => requestAction(a, "close")}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>
      {error && (
        <div role="alert" className="error">
          {error}
          <button onClick={() => location.reload()}>Reload</button>
        </div>
      )}
      {!analyses.length && (
        <main className="welcome">
          <span className="eyebrow">Explore</span>
          <h1>Explore an acquisition.</h1>
          <p>
            Inspect stored signals, define exact mass windows and connect
            spatial selections to depth profiles.
          </p>
          <button disabled={!session} onClick={() => setPicker(true)}>
            Choose an HDF5 acquisition
          </button>
          <p className="muted">
            Each open file has independent selections. Save a copy to keep your
            analysis with the data.
          </p>
        </main>
      )}
      {analyses.map((a) => (
        <div key={`${a.id}:${a.dataset.generation}`} hidden={a.id !== active}>
          <ExploreScreen
            initial={a}
            active={a.id === active}
            onReplace={(current) => requestAction(current, "replace")}
            onStatus={reportStatus}
            saveRequest={saveRequest?.id === a.id ? saveRequest.serial : 0}
            onSaved={(latest) => {
              reportStatus(latest, statuses[latest.id]?.draft || false, false);
              if (
                pendingAction?.id === latest.id &&
                latest.saved_revision === latest.revision &&
                !statuses[latest.id]?.draft
              )
                void perform(pendingAction, latest);
            }}
            onSaveDismiss={() => {
              if (pendingAction?.id === a.id) {
                setPendingAction(null);
                setConfirming(false);
                setSaveRequest(null);
              }
            }}
          />
        </div>
      ))}
      {confirming && pendingAction && (
        <UnsavedChanges
          name={
            pendingStatus?.analysis.dataset.name ||
            analyses.find((a) => a.id === pendingAction.id)?.dataset.name ||
            "this file"
          }
          blocked={pendingBlocked}
          onSave={() => {
            setActive(pendingAction.id);
            setConfirming(false);
            setSaveRequest((old) => ({
              id: pendingAction.id,
              serial: (old?.serial || 0) + 1,
            }));
          }}
          onDiscard={() => void perform(pendingAction)}
          onCancel={() => {
            setPendingAction(null);
            setConfirming(false);
          }}
        />
      )}
      {picker && (
        <FilePicker
          onOpen={open}
          onClose={() => {
            setPicker(false);
            setReplace(null);
          }}
        />
      )}
    </>
  );
}
