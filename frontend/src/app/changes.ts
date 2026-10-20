import type { Analysis } from "../api/client";

export function hasChanges(analysis: Analysis): boolean {
  return (
    analysis.revision !==
    (analysis.saved_revision ?? analysis.opened_revision ?? 0)
  );
}
