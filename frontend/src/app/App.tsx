import { useEffect, useState } from "react";
import {
  authenticate,
  request,
  post,
  type Analysis,
  type Session,
  type Workspace,
} from "../api/client";
import { FilePicker } from "./FilePicker";
import { ExploreScreen } from "../explore/ExploreScreen";
export function App() {
  const [session, setSession] = useState<Session | null>(null),
    [workspace, setWorkspace] = useState<Workspace | null>(null),
    [analyses, setAnalyses] = useState<Analysis[]>([]),
    [active, setActive] = useState(""),
    [picker, setPicker] = useState(false),
    [replace, setReplace] = useState<Analysis | null>(null),
    [error, setError] = useState(""),
    [reconnect, setReconnect] = useState("");
  useEffect(() => {
    let alive = true;
    authenticate()
      .then(async (s) => {
        const w = await post<Workspace>("/workspaces");
        if (alive) {
          setSession(s);
          setWorkspace(w);
          if (s.initial_file) {
            const a = await post<Analysis>(`/workspaces/${w.id}/analyses`, {
              relative_path: s.initial_file,
            });
            if (alive) {
              setAnalyses([a]);
              setActive(a.id);
            }
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
              setWorkspace(null);
              setSession(null);
              setError("Identity changed. Reload to start a new workspace.");
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
      a = await post<Analysis>(`/workspaces/${workspace!.id}/analyses`, {
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
        <div>
          <span className="mark">◫</span>
          <strong>ToFScope</strong>
          <span className="badge">Explore pilot · read only</span>
        </div>
        <span>{session?.owner || "Local instrument workspace"}</span>
      </header>
      <div className="workspace-bar">
        <button
          disabled={!workspace}
          onClick={() => {
            setReplace(null);
            setPicker(true);
          }}
        >
          ＋ Open acquisition
        </button>
        <div className="tabs" role="tablist">
          {analyses.map((a, i) => (
            <div key={a.id} className={a.id === active ? "tab active" : "tab"}>
              <button
                role="tab"
                aria-selected={a.id === active}
                onClick={() => setActive(a.id)}
              >
                {i + 1} · {a.dataset.relative_path.split("/").pop()}
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
          <button onClick={() => location.reload()}>Reconnect service</button>
        </div>
      )}
      {!analyses.length && (
        <main className="welcome">
          <span className="eyebrow">A scientific workspace</span>
          <h1>Explore an acquisition.</h1>
          <p>
            Inspect stored signals, define exact mass windows and connect
            spatial selections to depth profiles.
          </p>
          <button disabled={!workspace} onClick={() => setPicker(true)}>
            Choose an HDF5 acquisition
          </button>
          <p className="muted">
            Each open file has independent selections. Workspaces are temporary
            and reset when the service restarts.
          </p>
          <details>
            <summary>Reconnect an existing analysis</summary>
            <input
              aria-label="Analysis ID"
              value={reconnect}
              onChange={(e) => setReconnect(e.target.value)}
            />
            <button
              onClick={() =>
                request<Analysis>(`/analyses/${reconnect}`)
                  .then((a) => {
                    setAnalyses([a]);
                    setActive(a.id);
                    return request<Workspace>(`/workspaces/${a.workspace_id}`);
                  })
                  .then(setWorkspace)
                  .catch((e) => setError(e.message))
              }
            >
              Reattach
            </button>
          </details>
        </main>
      )}
      {analyses.map((a) => (
        <div key={`${a.id}:${a.dataset.generation}`} hidden={a.id !== active}>
          <ExploreScreen
            initial={a}
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
