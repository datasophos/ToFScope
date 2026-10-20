import { useEffect, useState } from "react";
import { request } from "../api/client";
import type { components } from "../api/generated";

type Locations = components["schemas"]["FolderLocations"];

export function folderName(path: string) {
  return path.split(/[\\/]/).filter(Boolean).at(-1) || path;
}

export function useFolderLocations() {
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
  return { folders, error };
}

export function FolderLocations({ filename = "" }: { filename?: string }) {
  const { folders, error } = useFolderLocations();
  if (error) return <p role="alert">{error}</p>;
  if (!folders) return <p role="status">Loading folders…</p>;
  const destination = `${folders.save_destination}/${filename}`;
  return (
    <dl className="folder-paths">
      <dt>Saved copies folder</dt>
      <dd data-testid="folder-saved-copies" title={folders.saved_copies}>
        {folderName(folders.saved_copies)}
      </dd>
      <dt>Save destination</dt>
      <dd data-testid="save-destination" title={destination}>
        {folderName(destination)}
      </dd>
    </dl>
  );
}
