import { useEffect, useState } from "react";
import { request } from "../api/client";
type Page = {
  path: string;
  entries: { name: string; path: string; kind: string; size: number }[];
  total: number;
  next_offset: number | null;
};
export function FilePicker({
  onOpen,
  onClose,
}: {
  onOpen: (path: string) => Promise<void>;
  onClose: () => void;
}) {
  const [dir, setDir] = useState(""),
    [query, setQuery] = useState(""),
    [offset, setOffset] = useState(0),
    [page, setPage] = useState<Page | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    request<Page>(
      `/files?directory=${encodeURIComponent(dir)}&query=${encodeURIComponent(query)}&offset=${offset}`,
    )
      .then((p) => {
        if (alive) setPage(p);
      })
      .catch((e) => setError(e.message));
    return () => {
      alive = false;
    };
  }, [dir, query, offset]);
  return (
    <div className="scrim">
      <section className="dialog" role="dialog" aria-label="Open acquisition">
        <header>
          <h2>Open acquisition</h2>
          <button onClick={onClose}>Close picker</button>
        </header>
        <p>
          Files remain on this server. Opening creates an independent analysis.
        </p>
        <div className="row">
          <button
            onClick={() => {
              setDir(dir.split("/").slice(0, -1).join("/"));
              setOffset(0);
            }}
          >
            Parent folder
          </button>
          <code>{dir || "Data root"}</code>
          <input
            aria-label="Search files"
            placeholder="Search this folder"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        {error && <p role="alert">{error}</p>}
        <ul className="files">
          {page?.entries.map((e) => (
            <li key={e.path}>
              <button
                disabled={busy}
                onClick={async () => {
                  if (e.kind === "directory") {
                    setDir(e.path);
                    setQuery("");
                    setOffset(0);
                  } else {
                    setBusy(true);
                    try {
                      await onOpen(e.path);
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }
                }}
              >
                {e.kind === "directory" ? "▸ " : "◫ "}
                {e.name}
              </button>
              <small>
                {e.kind === "file"
                  ? `${(e.size / 1024 ** 2).toFixed(1)} MB`
                  : ""}
              </small>
            </li>
          ))}
        </ul>
        {page?.total === 0 && <p>No acquisitions in this folder.</p>}
        <div className="row">
          <button
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 100))}
          >
            Previous page
          </button>
          <span>{page?.total || 0} entries</span>
          <button
            disabled={page?.next_offset == null}
            onClick={() => setOffset(page!.next_offset!)}
          >
            Next page
          </button>
        </div>
      </section>
    </div>
  );
}
