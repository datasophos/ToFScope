import { useEffect, useState } from "react";
import { request } from "../api/client";
import type { components } from "../api/generated";

type Locations = components["schemas"]["FolderLocations"];

export function FolderLocations({
  save = false,
  filename = "",
}: {
  save?: boolean;
  filename?: string;
}) {
  const [folders, setFolders] = useState<Locations | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    request<Locations>("/locations")
      .then((value) => {
        if (alive) setFolders(value);
      })
      .catch(() => {
        if (alive) setError("Folder locations are unavailable.");
      });
    return () => {
      alive = false;
    };
  }, []);
  if (error) return <p role="alert">{error}</p>;
  if (!folders) return <p role="status">Loading folders…</p>;
  return (
    <dl className="folder-paths">
      {!save && (
        <>
          <dt>Acquisition folder</dt>
          <dd data-testid="folder-acquisitions">
            <code>{folders.acquisitions}</code>
          </dd>
        </>
      )}
      <dt>Saved copies folder</dt>
      <dd data-testid="folder-saved-copies">
        <code>{folders.saved_copies}</code>
      </dd>
      {save && (
        <>
          <dt>Save destination</dt>
          <dd data-testid="save-destination">
            <code>
              {folders.save_destination}/{filename}
            </code>
          </dd>
        </>
      )}
    </dl>
  );
}
