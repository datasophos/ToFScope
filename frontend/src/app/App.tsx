import { useCallback, useEffect, useState } from "react";
import {
  authenticate,
  request,
  post,
  type Analysis,
  type Session,
} from "../api/client";
import { UnsavedChanges } from "./UnsavedChanges";
import { hasChanges } from "./changes";
import { FilePicker } from "./FilePicker";
import type { RawSelection, PreparationPreview } from "./RawPreparation";
import { ExploreScreen } from "../explore/ExploreScreen";
export function App() {
  const [version, setVersion] = useState("");
  const [session, setSession] = useState<Session | null>(null),
    [analyses, setAnalyses] = useState<Analysis[]>([]),
    [active, setActive] = useState(""),
    [picker, setPicker] = useState(false),
    [error, setError] = useState("");
  const [statuses, setStatuses] = useState<
    Record<string, { analysis: Analysis; draft: boolean; busy: boolean }>
  >({});
  const [pendingAction, setPendingAction] = useState<{
    id: string;
  } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [startupRaw, setStartupRaw] = useState<RawSelection | null>(null);
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
    return info?.draft || hasChanges(latest);
  });
  useEffect(() => {
    const controller = new AbortController();
    fetch("/healthz", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Version unavailable");
        return response.json() as Promise<{ version?: unknown }>;
      })
      .then((info) => {
        if (typeof info.version === "string" && info.version)
          setVersion(info.version);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);
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
          const preview = await post<PreparationPreview>(
            "/acquisitions/inspect",
            {
              relative_path: s.initial_file,
            },
          );
          if (!alive) return;
          if (preview.requires_preparation) {
            setStartupRaw({
              path: s.initial_file,
              name: s.initial_file.split("/").pop()!,
              location: "acquisition",
              preview,
            });
            setPicker(true);
            return;
          }
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
    const a = await post<Analysis>("/analyses", {
      relative_path: path,
      location,
    });
    setAnalyses((old) => [...old, a]);
    setActive(a.id);
    setPicker(false);
    setStartupRaw(null);
  };
  const close = async (a: Analysis) => {
    try {
      await request(`/analyses/${a.id}?expected_revision=${a.revision}`, {
        method: "DELETE",
      });
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
  const perform = async (action: { id: string }, latest?: Analysis) => {
    const a =
      latest ||
      statuses[action.id]?.analysis ||
      analyses.find((a) => a.id === action.id);
    if (!a) return;
    setPendingAction(null);
    setConfirming(false);
    setSaveRequest(null);
    await close(a);
  };
  const requestClose = (a: Analysis) => {
    const info = statuses[a.id];
    const latest = info?.analysis || a;
    const action = { id: a.id };
    if (info?.draft || hasChanges(latest)) {
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
        </div>
        <nav className="file-bar" aria-label="Files and open analyses">
          <button
            className="open-file-button"
            aria-label="Open TOFexplorer file"
            title="Open TOFexplorer file"
            disabled={!session}
            onClick={() => {
              setPicker(true);
            }}
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M3 8V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v2" />
              <path d="M3 8h17a1 1 0 0 1 1 1.3l-2.5 10a1 1 0 0 1-1 .7H5a2 2 0 0 1-2-2V8Z" />
            </svg>
          </button>
          <div className="tabs" role="tablist" aria-label="Open analyses">
            {analyses.map((a, i) => (
              <div
                key={a.id}
                className={a.id === active ? "tab active" : "tab"}
              >
                <button
                  role="tab"
                  title={
                    a.dataset.name || a.dataset.relative_path.split("/").pop()
                  }
                  aria-selected={a.id === active}
                  onClick={() => setActive(a.id)}
                >
                  {i + 1} ·{" "}
                  {a.dataset.name || a.dataset.relative_path.split("/").pop()}
                </button>
                <button
                  aria-label={`Close analysis ${i + 1}`}
                  onClick={() => requestClose(a)}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <a
            className="documentation-link"
            aria-label="Documentation"
            title="Open documentation"
            href="https://datasophos.github.io/ToFScope/"
            target="_blank"
            rel="noopener noreferrer"
          >
            <svg
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 6.5C9.5 4.5 6.5 4.5 3 5.5v13c3.5-1 6.5-1 9 1m0-13c2.5-2 5.5-2 9-1v13c-3.5-1-6.5-1-9 1m0-13v13" />
            </svg>
          </a>
          <a
            className="documentation-link"
            href="https://github.com/datasophos/ToFScope"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub repository"
            title="Open GitHub repository"
          >
            <svg
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M12 .9a11.1 11.1 0 0 0-3.51 21.63c.55.1.76-.24.76-.53v-2.06c-3.09.67-3.74-1.31-3.74-1.31-.5-1.28-1.23-1.62-1.23-1.62-1.01-.69.08-.68.08-.68 1.12.08 1.71 1.15 1.71 1.15.99 1.7 2.6 1.21 3.23.92.1-.72.39-1.21.71-1.49-2.47-.28-5.07-1.24-5.07-5.5 0-1.22.43-2.21 1.15-2.99-.12-.28-.5-1.41.11-2.95 0 0 .94-.3 3.05 1.14a10.6 10.6 0 0 1 5.56 0c2.11-1.44 3.04-1.14 3.04-1.14.61 1.54.23 2.67.11 2.95.72.78 1.15 1.77 1.15 2.99 0 4.27-2.6 5.21-5.08 5.49.4.35.75 1.02.75 2.06v3.04c0 .29.2.64.76.53A11.1 11.1 0 0 0 12 .9Z" />
            </svg>
          </a>
        </nav>
      </header>
      {error && (
        <div role="alert" className="error">
          {error}
          <button onClick={() => location.reload()}>Reload</button>
        </div>
      )}
      {!analyses.length && (
        <main className="welcome">
          <h1>ToFScope Data Explorer</h1>
          <p>
            View ion maps, secondary electron images and mass spectra from
            TOFWERK TOFexplorer files. Compare stored signals, integrate custom
            mass ranges and calculate depth profiles for selected image regions.
          </p>
          <button disabled={!session} onClick={() => setPicker(true)}>
            Open TOFexplorer (.h5) file
          </button>
        </main>
      )}
      {analyses.map((a) => (
        <div key={`${a.id}:${a.dataset.generation}`} hidden={a.id !== active}>
          <ExploreScreen
            initial={a}
            active={a.id === active}
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
      <footer className="app-credit">
        <a
          className="datasophos-credit"
          href="https://datasophos.co"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Made by Datasophos"
        >
          <span>Made by</span>
          <img
            src="/assets/datasophos-wordmark.png"
            alt="Datasophos"
            width="98"
            height="28"
          />
        </a>
        <a
          href="https://datasophos.github.io/ToFScope/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Documentation
        </a>
        <a
          href="https://github.com/datasophos/ToFScope/issues"
          target="_blank"
          rel="noopener noreferrer"
        >
          Report an issue
        </a>
        {version && (
          <a
            href={`https://github.com/datasophos/ToFScope/releases/tag/v${encodeURIComponent(version)}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            ToFScope {version}
          </a>
        )}
      </footer>
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
          initialRawSelection={startupRaw}
          onOpen={open}
          onClose={() => {
            setPicker(false);
            setStartupRaw(null);
          }}
        />
      )}
    </>
  );
}
