import { expect, test, vi } from "vitest";
import { animationQuality } from "./animationQuality";

test("animation requests adaptive rendering once and restores detail when stopped or disposed", () => {
  const interactor = {
    requestAnimation: vi.fn((_requester: object) => {}),
    cancelAnimation: vi.fn((_requester: object) => {}),
  };
  const quality = animationQuality(interactor);
  quality.set(true);
  quality.set(true);
  expect(interactor.requestAnimation).toHaveBeenCalledTimes(1);
  quality.set(false);
  expect(interactor.cancelAnimation).toHaveBeenCalledTimes(1);
  expect(interactor.cancelAnimation.mock.calls[0][0]).toBe(
    interactor.requestAnimation.mock.calls[0][0],
  );
  quality.set(true);
  quality.dispose();
  expect(interactor.cancelAnimation).toHaveBeenCalledTimes(2);
});

test("stopping during an export does not restart animation afterwards", async () => {
  const interactor = {
    requestAnimation: vi.fn((_requester: object) => {}),
    cancelAnimation: vi.fn((_requester: object) => {}),
  };
  const quality = animationQuality(interactor);
  quality.set(true);
  let finish!: () => void;
  const exportDone = quality.withFullQuality(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );
  quality.set(false);
  finish();
  await exportDone;
  expect(interactor.requestAnimation).toHaveBeenCalledTimes(1);
  expect(interactor.cancelAnimation).toHaveBeenCalledTimes(1);
});
