/** Ignore camera props queued before a user gesture until that gesture ends. */
export function cameraInteraction<T>(apply: (camera: T) => void) {
  let active = false;
  return {
    start: () => {
      active = true;
    },
    end: () => {
      active = false;
    },
    update: (camera: T) => {
      if (!active) apply(camera);
    },
  };
}
