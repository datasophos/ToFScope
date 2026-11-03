import { expect, test, vi } from "vitest";
import { startRotation } from "./rotationAnimation";

test("rotation uses elapsed time, limits suspended frames, and cancels", () => {
  let callback: FrameRequestCallback = () => {};
  const request = vi.fn((cb: FrameRequestCallback) => {
    callback = cb;
    return 7;
  });
  const cancel = vi.fn();
  const rotate = vi.fn();
  const stop = startRotation(rotate, request, cancel);
  callback(100);
  callback(200);
  expect(rotate).toHaveBeenCalledWith(3);
  callback(1200);
  expect(rotate).toHaveBeenLastCalledWith(3);
  stop();
  expect(cancel).toHaveBeenCalledWith(7);
});
