type Interactor = {
  requestAnimation: (requester: object) => void;
  cancelAnimation: (requester: object) => void;
};

export function animationQuality(interactor: Interactor) {
  const requester = {};
  let requested = false;
  let active = false;
  let suspended = 0;
  const sync = () => {
    const enabled = requested && suspended === 0;
    if (active === enabled) return;
    active = enabled;
    if (enabled) interactor.requestAnimation(requester);
    else interactor.cancelAnimation(requester);
  };
  const set = (enabled: boolean) => {
    requested = enabled;
    sync();
  };
  const withFullQuality = async <T>(capture: () => Promise<T>): Promise<T> => {
    suspended++;
    sync();
    try {
      return await capture();
    } finally {
      suspended--;
      sync();
    }
  };
  return { set, dispose: () => set(false), withFullQuality };
}
