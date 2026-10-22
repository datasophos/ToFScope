export type SignalDraft = {
  isotope?: { candidateId: string; measuredMz: number };
  signalId?: string;
  recipeVersion?: number;
  nameRevision?: number;
  name: string;
  intervals: [string, string][];
  selectedInterval: number;
  frames: [string, string];
  baseline: string;
  submittedJobId?: string;
};
export type EditorState = {
  draft: SignalDraft | null;
  pendingSwitch?: SignalDraft | null;
};
const fingerprint = (d: SignalDraft) =>
  JSON.stringify([d.name, d.intervals, d.frames]);
export function createDraft(
  name: string,
  intervals: number[][],
  frames: number[],
  signalId?: string,
  base?: { recipeVersion: number; nameRevision: number },
): SignalDraft {
  const draft: SignalDraft = {
    signalId,
    ...base,
    name,
    intervals: intervals.map(([a, b]) => [String(a), String(b)]),
    frames: [String(frames[0]), String(frames[1])],
    selectedInterval: 0,
    baseline: "",
  };
  draft.baseline = fingerprint(draft);
  return draft;
}
export const dirty = (d: SignalDraft) => fingerprint(d) !== d.baseline;
export function openDraft(
  state: EditorState,
  draft: SignalDraft | null,
): EditorState {
  if (state.draft?.submittedJobId) return state;
  return state.draft && dirty(state.draft)
    ? { ...state, pendingSwitch: draft }
    : { draft };
}
export function patchDraft(
  state: EditorState,
  patch: Partial<SignalDraft>,
): EditorState {
  return !state.draft || state.draft.submittedJobId
    ? state
    : { ...state, draft: { ...state.draft, ...patch } };
}
export function finishDraft(
  state: EditorState,
  id: string,
  status: string,
): EditorState {
  if (state.draft?.submittedJobId !== id) return state;
  return status === "succeeded"
    ? { draft: null }
    : { ...state, draft: { ...state.draft, submittedJobId: undefined } };
}
