from dataclasses import replace
from tofscope.science.depth_calibration import DepthAnchor, validate_anchors
from tofscope.application.commands import CommandEnvelope, AllDepth
from tofscope.application.models import DisplaySettings, SignalSnapshot
from tofscope.application.signals import get_signal, normalize_view, usable_frames, valid_name
from tofscope.application.analyses import Conflict, CapacityError
from tofscope.science.signals import SignalRecipe


class ExploreService:
    def __init__(self, workspaces, repository):
        self.analyses = workspaces
        self.repository = repository

    def stored(self, s, index, frames=None):
        if not 0 <= index < len(s.peaks):
            raise ValueError("Unknown stored channel.")
        coverage = tuple(frames) if frames is not None else s.loaded_frames
        if not 0 <= coverage[0] <= coverage[1] < s.shape[0]:
            raise ValueError("Coverage outside acquisition.")
        p = s.peaks[index]
        return SignalRecipe(
            label=f"{p.label} · {p.mass:g} Th",
            source="stored",
            stored_index=index,
            intervals=((p.low, p.high),),
            frames=coverage,
        )

    def validate_envelope(self, e, envelope, fingerprint, check_source=True):
        s = e.snapshot
        if e.closed:
            raise KeyError("Analysis unavailable.")
        if envelope.request_id in e.receipts:
            old, result = e.receipts[envelope.request_id]
            if old != fingerprint:
                raise Conflict("Request ID reused with different content.", s.revision)
            return result
        if envelope.expected_revision != s.revision:
            raise Conflict("Analysis revision changed.", s.revision)
        if envelope.dataset_generation != s.dataset.generation:
            raise Conflict("Acquisition generation changed.", s.revision)
        if check_source:
            self.repository.assert_current(s.owner, s.dataset)
        return None

    def receipt(self, e, request_id, fingerprint, result):
        e.receipts[request_id] = (fingerprint, result)
        while len(e.receipts) > 256:
            e.receipts.popitem(last=False)

    def apply(self, owner, analysis_id, envelope):
        if not isinstance(envelope, CommandEnvelope):
            envelope = CommandEnvelope(**envelope)
        fingerprint = envelope.model_dump_json()
        e = self.analyses.entry(owner, analysis_id)
        with self.analyses.signal_lock, e.lock:
            previous = self.validate_envelope(e, envelope, fingerprint)
            if previous is not None:
                return previous
            s = e.snapshot
            c = envelope.command
            kind = c.type
            patch = {}
            if kind == 'add_stored_signal':
                recipe = self.stored(s, c.index, c.frames)
                old = next((r for r in s.signals if r.recipe is not None and
                            r.recipe.source == 'stored' and r.recipe.stored_index == c.index and
                            r.recipe.frames == recipe.frames), None)
                if old and not c.duplicate:
                    patch['profile_signal_ids'] = tuple(dict.fromkeys((*s.profile_signal_ids, old.id)))
                else:
                    self.analyses.admit_signal(owner, len(s.signals))
                    signal = SignalSnapshot(recipe.id, recipe.label, s.next_style_index, recipe)
                    patch = dict(signals=(*s.signals, signal), next_style_index=s.next_style_index+1,
                                 profile_signal_ids=(*s.profile_signal_ids, signal.id))
            elif kind in ('rename_signal', 'select_image_signal', 'set_profile_visible', 'remove_signal', 'set_stored_coverage'):
                signal = get_signal(s, c.signal_id)
                if kind == 'rename_signal':
                    updated = replace(signal, name=valid_name(c.name), name_revision=signal.name_revision+1)
                    patch['signals'] = tuple(updated if r.id == signal.id else r for r in s.signals)
                elif kind == 'select_image_signal':
                    if not usable_frames(s, signal):
                        raise ValueError('Signal has no ready coverage in the analysis range.')
                    patch['image_signal_id'] = signal.id
                elif kind == 'set_profile_visible':
                    if signal.id == s.image_signal_id and not c.visible:
                        raise ValueError('The image signal is included in its depth profile.')
                    if signal.recipe is None:
                        raise ValueError('Signal calculation is not ready.')
                    patch['profile_signal_ids'] = tuple(dict.fromkeys((*s.profile_signal_ids, signal.id))) if c.visible else tuple(x for x in s.profile_signal_ids if x != signal.id)
                elif kind == 'remove_signal':
                    patch['signals'] = tuple(r for r in s.signals if r.id != signal.id)
                    patch['profile_signal_ids'] = tuple(x for x in s.profile_signal_ids if x != signal.id)
                    if signal.id == s.image_signal_id:
                        eligible = [r for r in patch['signals'] if usable_frames(s, r)]
                        if not eligible:
                            raise ValueError('Add another ready image signal before removing this one.')
                        patch['image_signal_id'] = eligible[0].id
                else:
                    if signal.recipe is None or signal.recipe.source != 'stored':
                        raise ValueError('Only stored channel coverage can be changed without calculation.')
                    first, last = c.frames
                    if not 0 <= first <= last < s.shape[0]:
                        raise ValueError('Coverage outside acquisition.')
                    updated = replace(signal, recipe=replace(signal.recipe, frames=tuple(c.frames)), recipe_version=signal.recipe_version+1)
                    patch['signals'] = tuple(updated if r.id == signal.id else r for r in s.signals)
            elif kind == 'set_roi':
                x0, x1, y0, y1 = c.roi
                if not 0 <= x0 <= x1 < s.shape[2] or not 0 <= y0 <= y1 < s.shape[1]:
                    raise ValueError('ROI outside pixel domain.')
                patch['roi'] = tuple(c.roi)
            elif kind == 'set_depth':
                d = c.depth
                first, last = s.loaded_frames
                if d.mode == 'frame' and not first <= d.index <= last:
                    raise ValueError('Frame outside analysis range.')
                if d.mode == 'window' and not first <= d.first <= d.last <= last:
                    raise ValueError('Window outside analysis range.')
                patch['depth'] = d
            elif kind == 'set_analysis_frames':
                first, last = c.frames
                if not 0 <= first <= last < s.shape[0]:
                    raise ValueError('Analysis range outside acquisition.')
                patch = dict(loaded_frames=tuple(c.frames), depth=AllDepth())
            elif kind == 'set_depth_anchors':
                anchors = validate_anchors(tuple(DepthAnchor(x.frame, x.depth_nm) for x in c.anchors), s.shape[0])
                patch['depth_anchors'] = anchors
                if len(anchors) < 2:
                    patch['depth_coordinates'] = 'frame'
            elif kind == 'set_depth_display':
                if c.coordinates == 'depth' and len(s.depth_anchors) < 2:
                    raise ValueError('Add a positive-depth anchor first.')
                patch.update(depth_unit=c.unit, depth_coordinates=c.coordinates)
            elif kind == 'set_display':
                patch['display'] = DisplaySettings(c.log, c.relative, c.image, s.display.spectrum_log if c.spectrum_log is None else c.spectrum_log, s.display.colormap if c.colormap is None else c.colormap)
            result = normalize_view(replace(s, revision=s.revision+1, **patch))
            if kind == 'remove_signal':
                e.tokens.pop(signal.id, None)
            # Hidden and removed signals retain metadata without pinned volume leases.
            visible = set(result.profile_signal_ids) | {result.image_signal_id}
            for sid in list(e.leases):
                if sid not in visible or kind == 'set_stored_coverage' and sid == signal.id:
                    e.leases.pop(sid).release()
            e.snapshot = result
            if kind == "remove_signal":
                for callback in self.analyses.on_remove:
                    callback(analysis_id, signal.id)
            self.receipt(e, envelope.request_id, fingerprint, result)
            return result
