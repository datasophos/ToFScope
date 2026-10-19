"""Signal identity and view invariants, independent of readers and renderers."""
from dataclasses import replace
from tofscope.application.commands import AllDepth, SingleFrame, DepthWindow


def valid_name(value):
    value = value.strip()
    if not 1 <= len(value) <= 128:
        raise ValueError('Signal name must contain 1–128 characters.')
    return value


def get_signal(snapshot, signal_id):
    for signal in snapshot.signals:
        if signal.id == signal_id:
            return signal
    raise ValueError('Signal unavailable.')


def image_signal(snapshot):
    return get_signal(snapshot, snapshot.image_signal_id)


def visible_signals(snapshot):
    ids = set(snapshot.profile_signal_ids) | {snapshot.image_signal_id}
    return tuple(sorted((s for s in snapshot.signals if s.id in ids and s.recipe is not None),
                        key=lambda s: (s.id != snapshot.image_signal_id, s.style_index)))


def usable_frames(snapshot, signal):
    if signal.recipe is None:
        return None
    low = max(snapshot.loaded_frames[0], signal.recipe.frames[0])
    high = min(snapshot.loaded_frames[1], signal.recipe.frames[1])
    return (low, high) if low <= high else None


def image_frames(snapshot):
    bounds = usable_frames(snapshot, image_signal(snapshot))
    if bounds is None:
        raise ValueError('Image signal has no coverage in the analysis range.')
    depth = snapshot.depth
    if depth.mode == 'all':
        return bounds
    requested = (depth.index, depth.index) if depth.mode == 'frame' else (depth.first, depth.last)
    low, high = max(bounds[0], requested[0]), min(bounds[1], requested[1])
    return (low, high) if low <= high else (bounds[0], bounds[0])


def normalize_view(snapshot):
    if usable_frames(snapshot, image_signal(snapshot)) is None:
        candidates = [s for s in snapshot.signals if usable_frames(snapshot, s)]
        if not candidates:
            raise ValueError('At least one ready signal must cover the analysis range.')
        snapshot = replace(snapshot, image_signal_id=candidates[0].id)
    low, high = image_frames(snapshot)
    depth = snapshot.depth
    if depth.mode == 'frame':
        depth = SingleFrame(mode='frame', index=low)
    elif depth.mode == 'window':
        depth = DepthWindow(mode='window', first=low, last=high)
    ids = tuple(dict.fromkeys((*snapshot.profile_signal_ids, snapshot.image_signal_id)))
    return replace(snapshot, depth=depth, profile_signal_ids=ids)
