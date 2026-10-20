import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { folderName, useFolderLocations } from "./FolderLocations";
import { request } from "../api/client";

type Entry = { name: string; path: string; kind: string; size: number };
type Page = {
  path: string;
  entries: Entry[];
  total: number;
  next_offset: number | null;
};
type Location = "acquisition" | "saved";

function FileIcon({ folder = false }: { folder?: boolean }) {
  return (
    <svg
      className="file-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      {folder ? (
        <path d="M3 6h7l2 2h9v12H3z" />
      ) : (
        <>
          <path d="M5 3h9l5 5v13H5zM14 3v6h5" />
          <path d="M8 14h8M8 17h6" />
        </>
      )}
    </svg>
  );
}

function fileSize(bytes: number) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function FilePicker({
  onOpen,
  onClose,
}: {
  onOpen: (path: string, location: Location) => Promise<void>;
  onClose: () => void;
}) {
  const { folders, error: folderError } = useFolderLocations();
  const [location, setLocation] = useState<Location>("acquisition");
  const [dir, setDir] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const files = useRef<HTMLTableElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    search.current?.focus();
    return () => {
      if (previous?.isConnected) previous.focus();
    };
  }, []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    setPage(null);
    setSelected(null);
    request<Page>(
      `/files?location=${location}&directory=${encodeURIComponent(dir)}&query=${encodeURIComponent(query)}&offset=${offset}`,
    )
      .then((value) => {
        if (alive) setPage(value);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [dir, query, offset, location]);

  const navigate = (path: string, nextLocation = location) => {
    setDir(path);
    setLocation(nextLocation);
    setQuery("");
    setOffset(0);
    setSelected(null);
  };
  const openEntry = async (entry: Entry) => {
    if (busy || loading) return;
    if (entry.kind === "directory") {
      navigate(entry.path);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onOpen(entry.path, location);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const chosen = page?.entries.find((entry) => entry.path === selected);
  const rootPath =
    location === "saved" ? folders?.saved_copies : folders?.acquisitions;
  const currentPath =
    location === "saved"
      ? folders?.save_destination
      : [rootPath, dir].filter(Boolean).join("/");
  const segments = dir.split("/").filter(Boolean);

  const handleKeys = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape" && !busy) {
      event.preventDefault();
      onClose();
    }
    if (event.key === "Tab") {
      const nodes = dialog.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]):not([tabindex="-1"]), input:not([disabled])',
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
    }
  };
  const fileKeys = (event: KeyboardEvent<HTMLTableElement>) => {
    const entries = page?.entries || [];
    if (busy || !entries.length) return;
    if (event.key === "Enter" && chosen) {
      event.preventDefault();
      void openEntry(chosen);
      return;
    }
    const index = entries.findIndex((entry) => entry.path === selected);
    const next =
      event.key === "ArrowDown"
        ? Math.min(index + 1, entries.length - 1)
        : event.key === "ArrowUp"
          ? Math.max(0, index - 1)
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? entries.length - 1
              : null;
    if (next === null) return;
    event.preventDefault();
    setSelected(entries[next].path);
    const button =
      files.current?.querySelectorAll<HTMLButtonElement>("button[data-file]")[
        next
      ];
    button?.focus({ preventScroll: true });
    button?.scrollIntoView({ block: "nearest" });
  };

  return (
    <div className="scrim">
      <section
        ref={dialog}
        className="dialog file-explorer"
        role="dialog"
        aria-modal="true"
        aria-label="Open TOFexplorer file"
        onKeyDown={handleKeys}
      >
        <header className="file-explorer-header">
          <h2>Open TOFexplorer file</h2>
          <button aria-label="Close picker" disabled={busy} onClick={onClose}>
            ×
          </button>
        </header>
        <div className="file-explorer-body">
          <aside className="file-sidebar" aria-label="Locations">
            {(
              [
                [
                  "acquisition",
                  "Acquisitions",
                  folders?.acquisitions,
                  "folder-acquisitions",
                ],
                [
                  "saved",
                  "Saved files",
                  folders?.saved_copies,
                  "folder-saved-copies",
                ],
              ] as const
            ).map(([value, label, path, testId]) => (
              <button
                key={value}
                aria-label={label}
                aria-pressed={location === value}
                disabled={busy}
                onClick={() => navigate("", value)}
              >
                <FileIcon folder />
                <span>
                  <strong>{label}</strong>
                  <small data-testid={testId} title={path}>
                    {path ? folderName(path) : "…"}
                  </small>
                </span>
              </button>
            ))}
          </aside>
          <div className="file-explorer-main">
            <div className="file-explorer-toolbar">
              <button
                className="file-up"
                aria-label="Parent folder"
                title="Parent folder"
                disabled={busy || location === "saved" || !dir}
                onClick={() => navigate(segments.slice(0, -1).join("/"))}
              >
                ↑
              </button>
              <nav
                className="file-breadcrumbs"
                aria-label="Folder path"
                title={currentPath}
              >
                <button
                  disabled={busy}
                  aria-current={!dir ? "location" : undefined}
                  title={
                    location === "saved" ? folders?.save_destination : rootPath
                  }
                  onClick={() => navigate("")}
                >
                  {rootPath
                    ? folderName(rootPath)
                    : location === "saved"
                      ? "Saved files"
                      : "Acquisitions"}
                </button>
                {segments.map((part, index) => (
                  <span key={index}>
                    <span className="breadcrumb-separator" aria-hidden="true">
                      ›
                    </span>
                    <button
                      disabled={busy}
                      aria-current={
                        index === segments.length - 1 ? "location" : undefined
                      }
                      title={`${rootPath}/${segments.slice(0, index + 1).join("/")}`}
                      onClick={() =>
                        navigate(segments.slice(0, index + 1).join("/"))
                      }
                    >
                      {part}
                    </button>
                  </span>
                ))}
              </nav>
              <input
                ref={search}
                aria-label="Search files"
                placeholder="Search this folder"
                value={query}
                disabled={busy}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setOffset(0);
                }}
              />
            </div>
            {(error || folderError) && (
              <p role="alert" className="file-error">
                {error || folderError}
              </p>
            )}
            <div className="file-list" aria-busy={loading || busy}>
              <table ref={files} aria-label="Files" onKeyDown={fileKeys}>
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Size</th>
                  </tr>
                </thead>
                <tbody>
                  {page?.entries.map((entry, index) => (
                    <tr
                      key={entry.path}
                      aria-selected={selected === entry.path}
                      onClick={(event) => {
                        if (!busy) {
                          setSelected(entry.path);
                          event.currentTarget
                            .querySelector("button")
                            ?.focus({ preventScroll: true });
                        }
                      }}
                    >
                      <td>
                        <button
                          data-file
                          tabIndex={
                            selected === entry.path ||
                            (!selected && index === 0)
                              ? 0
                              : -1
                          }
                          aria-label={`${entry.kind === "directory" ? "▸" : "◫"} ${entry.name}`}
                          title={entry.name}
                          disabled={busy}
                          onFocus={() => setSelected(entry.path)}
                          onClick={() => setSelected(entry.path)}
                          onDoubleClick={() => void openEntry(entry)}
                        >
                          <FileIcon folder={entry.kind === "directory"} />
                          <span>{entry.name}</span>
                        </button>
                      </td>
                      <td>
                        {entry.kind === "file" ? fileSize(entry.size) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(loading || busy) && (
                <div className="file-list-message" role="status">
                  <span className="plot-spinner" aria-hidden="true" />
                  {busy
                    ? `Opening ${chosen?.name || "file"}…`
                    : "Loading files…"}
                </div>
              )}
              {!loading && !busy && page?.total === 0 && (
                <p className="file-list-message">
                  {query
                    ? "No matching files."
                    : location === "saved"
                      ? "No saved files in this location."
                      : "No .h5 files in this folder."}
                </p>
              )}
            </div>
            <div className="file-list-status">
              <span>
                {page
                  ? page.total > 100
                    ? `${offset + 1}–${offset + page.entries.length} of ${page.total} items`
                    : `${page.total} items`
                  : ""}
              </span>
              {!!page && page.total > 100 && (
                <div>
                  <button
                    aria-label="Previous page"
                    disabled={!offset || loading || busy}
                    onClick={() => setOffset(Math.max(0, offset - 100))}
                  >
                    ‹
                  </button>
                  <button
                    aria-label="Next page"
                    disabled={page.next_offset === null || loading || busy}
                    onClick={() => setOffset(page.next_offset!)}
                  >
                    ›
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
        <footer className="file-explorer-footer">
          <span title={chosen?.name}>
            {chosen?.name || "TOFexplorer files (.h5)"}
          </span>
          <button disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            disabled={!chosen || loading || busy}
            onClick={() => {
              if (chosen) void openEntry(chosen);
            }}
          >
            Open
          </button>
        </footer>
      </section>
    </div>
  );
}
