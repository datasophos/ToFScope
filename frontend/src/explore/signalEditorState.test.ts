import { expect, test } from "vitest";
import {
  createDraft,
  openDraft,
  patchDraft,
  finishDraft,
  dirty,
  type EditorState,
} from "./signalEditorState";
test("drafts preserve exact input and require an explicit dirty switch", () => {
  const first = createDraft("Ti", [[47.808572918, 48.22032918]], [0, 1300]);
  let state: EditorState = { draft: first, pendingSwitch: undefined };
  state = patchDraft(state, {
    intervals: [["47.808572918123", "48.22032918123"]],
  });
  expect(dirty(state.draft!)).toBe(true);
  const other = createDraft("Pt", [[193.8, 194.2]], [0, 1300]);
  const switched = openDraft(state, other);
  expect(switched.draft!.intervals[0][0]).toBe("47.808572918123");
  expect(switched.pendingSwitch!.name).toBe("Pt");
});
test("submitted drafts are frozen and only their matching success closes them", () => {
  const draft = {
    ...createDraft("Ti", [[1, 2]], [0, 2]),
    submittedJobId: "one",
  };
  const state: EditorState = { draft, pendingSwitch: undefined };
  expect(patchDraft(state, { name: "changed" }).draft!.name).toBe("Ti");
  expect(finishDraft(state, "old", "succeeded").draft).toEqual(draft);
  expect(
    finishDraft(state, "one", "failed").draft!.submittedJobId,
  ).toBeUndefined();
  expect(finishDraft(state, "one", "succeeded").draft).toBeNull();
});
