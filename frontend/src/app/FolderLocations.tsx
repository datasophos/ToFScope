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

export function FolderLocations({
  filename = "",
  directory = "",
  location = "saved",
}: {
  filename?: string;
  directory?: string;
  location?: "acquisition" | "saved";
}) {
  const { folders, error } = useFolderLocations();
  if (error) return <p role="alert">{error}</p>;
  if (!folders) return <p role="status">Loading folders…</p>;
  const root =
    location === "saved" ? folders.save_destination : folders.acquisitions;
  const folder = [root, directory].filter(Boolean).join("/");
  const destination = `${folder}/${filename}`;
  return (
    <dl className="folder-paths">
      <dt>Save folder</dt>
      <dd
        data-testid="folder-saved-copies"
        title={
          directory || location !== "saved" ? folder : folders.saved_copies
        }
      >
        {folderName(
          !directory && location === "saved" ? folders.saved_copies : folder,
        )}
      </dd>
      <dt>Save destination</dt>
      <dd data-testid="save-destination" title={destination}>
        {destination}
      </dd>
    </dl>
  );
}
