import { useEffect, useState } from "react";
import {
  authenticate,
  request,
  post,
  type Analysis,
  type Session,
} from "../api/client";
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
  const open = async (path: string) => {
    let a: Analysis;
    if (replace) {
      a = await post<Analysis>(`/analyses/${replace.id}/replace`, {
        request_id: crypto.randomUUID(),
        expected_revision: replace.revision,
        dataset_generation: replace.dataset.generation,
        relative_path: path,
      });
      setAnalyses((old) => old.map((x) => (x.id === a.id ? a : x)));
      setReplace(null);
    } else {
      a = await post<Analysis>("/analyses", {
        relative_path: path,
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
      if (active === a.id)
        setActive(analyses.find((x) => x.id !== a.id)?.id || "");
    } catch (e) {
      setError((e as Error).message);
    }
  };
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
                onClick={() => void close(a)}
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
            onReplace={(current) => {
              setReplace(current);
              setPicker(true);
            }}
          />
        </div>
      ))}
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
