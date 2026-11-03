import { expect, test, vi } from "vitest";
import { cameraInteraction } from "./cameraInteraction";

test("queued camera updates cannot overwrite an active gesture", () => {
  const apply = vi.fn((_camera: string) => {});
  const gesture = cameraInteraction(apply);
  gesture.update("before");
  gesture.start();
  gesture.update("stale animation frame");
  expect(apply).toHaveBeenCalledTimes(1);
  gesture.end();
  gesture.update("gesture result");
  expect(apply.mock.calls.map(([value]) => value)).toEqual([
    "before",
    "gesture result",
  ]);
});
