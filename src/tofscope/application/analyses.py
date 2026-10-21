from collections import OrderedDict
from dataclasses import dataclass, field, replace
from threading import RLock
from uuid import uuid4
from tofscope.storage.acquisitions import SourceChanged
from tofscope.application.models import (
    AnalysisSnapshot,
    DisplaySettings,
    SignalSnapshot,
    Peak,
)
from tofscope.application.commands import AllDepth
from tofscope.science.signals import SignalRecipe


class CapacityError(ValueError):
    pass


class Conflict(ValueError):
    def __init__(self, message, revision=None):
        super().__init__(message)
        self.revision = revision


@dataclass
class AnalysisEntry:
    snapshot: AnalysisSnapshot
    lock: RLock = field(default_factory=RLock)
    receipts: OrderedDict = field(default_factory=OrderedDict)
    tokens: dict = field(default_factory=dict)
    leases: dict = field(default_factory=dict)
    closed: bool = False


class AnalysisService:
    def __init__(self, repository, settings):
        self.repository = repository
        self.settings = settings
        self.entries = {}
        self.lock = RLock()
        self.signal_lock = RLock()
        self.on_close = []
        self.on_remove = []
        self.prepare = lambda s: None

    def list(self, owner):
        with self.lock:
            aids = [e.snapshot.id for e in self.entries.values() if not e.closed and e.snapshot.owner == owner]
        result = []
        for aid in aids:
            try:
                result.append(self.get(owner, aid))
            except KeyError:
                pass
        return result

    def entry(self, owner, aid):
        with self.lock:
            e = self.entries.get(aid)
        if e is None or e.closed or e.snapshot.owner != owner:
            raise KeyError("Analysis unavailable.")
        return e

    def get(self, owner, aid):
        e = self.entry(owner, aid)
        try:
            self.repository.assert_current(owner, e.snapshot.dataset)
        except (SourceChanged, OSError):
            self.mark_stale(e.snapshot.dataset)
        with e.lock:
            return e.snapshot

    def mark_stale(self, dataset):
        with self.lock:
            entries = list(self.entries.values())
        for entry in entries:
            with entry.lock:
                s = entry.snapshot
                if (
                    not entry.closed
                    and s.dataset.key == dataset.key
                    and s.dataset.generation == dataset.generation
                    and not s.stale
                ):
                    entry.snapshot = replace(s, stale=True, revision=s.revision + 1)
                    entry.tokens = {k: v + 1 for k, v in entry.tokens.items()}
                    self._release(entry)

    def initial(self, owner, dataset, aid=None, revision=0):
        with self.repository.metadata(owner, dataset, aid) as m:
            nz, ny, nx, _ = m.shape
            default = min(m.peaks, key=lambda p: abs(p["mass"] - 27))
            frames = (0, nz - 1)
            recipe = SignalRecipe(
                label=f"{default['label']} · {default['mass']:g} Th",
                source="stored",
                stored_index=default["index"],
                intervals=((default["low"], default["high"]),),
                frames=frames,
            )
            snapshot = AnalysisSnapshot(
                aid or str(uuid4()),
                owner,
                dataset,
                revision,
                (0, nx - 1, 0, ny - 1),
                AllDepth(),
                (SignalSnapshot(recipe.id, recipe.label, 0, recipe),),
                recipe.id,
                (recipe.id,),
                1,
                DisplaySettings(),
                m.shape,
                tuple(Peak(**p) for p in m.peaks),
                m.fov_um,
                (float(m.mass_axis.min()), float(m.mass_axis.max())),
                has_se=bool(m.image_names),
                opened_revision=revision,
            )

        from tofscope.storage.analysis_document import read_document, restore_snapshot, ROOT, MAX_DOCUMENT_BYTES
        from tofscope.storage.integration_store import saved_result_info, iter_saved_frames, metadata_size, ROOT as RESULT_ROOT
        from contextlib import nullcontext
        import hashlib
        import h5py
        with self.repository.access(owner, dataset) as path:
            # Plain acquisitions need no document allocation. Reject oversized metadata first.
            with h5py.File(path, 'r') as h:
                if ROOT not in h:
                    return snapshot
                try:
                    stored = h[f'{ROOT}/state_json']
                    if stored.ndim != 1 or stored.size > MAX_DOCUMENT_BYTES:
                        raise ValueError('Saved analysis metadata exceeds limits.')
                    estimated = stored.size * 16 + snapshot.shape[1] * snapshot.shape[2] * 8
                except (KeyError, TypeError, AttributeError) as exc:
                    raise ValueError('Saved analysis metadata is invalid.') from exc
            budget = self.repository.budget
            with budget.reserve(owner, snapshot.id, estimated) if budget else nullcontext():
                document = read_document(path, self.settings)
                if document is None:
                    return snapshot
                try:
                    with h5py.File(path, 'r') as handle:
                        result_metadata_bytes = sum(metadata_size(handle[f'{RESULT_ROOT}/{row.materialization_id}'])
                                                    for row in document.signals if row.materialization_id)
                except (KeyError, TypeError) as exc:
                    raise ValueError('Saved result is missing or invalid.') from exc
                with budget.reserve(owner, snapshot.id, result_metadata_bytes * 16) if budget else nullcontext():
                    for row in document.signals:
                        if row.materialization_id:
                            info = saved_result_info(path, row.materialization_id)
                            if tuple(info['spatial_shape']) != snapshot.shape[1:3] or tuple(info['derivation']['frames']) != row.recipe.frames or tuple(tuple(w) for w in info['derivation']['intervals']) != row.recipe.intervals:
                                raise ValueError('Saved result does not match the document.')
                            digest = hashlib.sha256()
                            for frame in iter_saved_frames(path, row.materialization_id, row.recipe.frames):
                                digest.update(frame.tobytes(order='C'))
                            with h5py.File(path, 'r') as h:
                                expected = h[f'ToFScope/Integrations/{row.materialization_id}'].attrs.get('sha256')
                            if digest.hexdigest() != expected:
                                raise ValueError('Saved result checksum is invalid.')
                    return restore_snapshot(document, snapshot)

    def admit_collection(self, snapshot, replacing=None):
        with self.lock:
            entries = [e.snapshot for e in self.entries.values() if not e.closed and e.snapshot.id != replacing]
            count = len(snapshot.signals)
            if (count > self.settings.signals_per_analysis or
                    count + sum(len(s.signals) for s in entries if s.owner == snapshot.owner) > self.settings.signals_per_user or
                    count + sum(len(s.signals) for s in entries) > self.settings.signals_global):
                raise CapacityError('Saved analysis exceeds signal limits.')

    def admit_signal(self, owner, analysis_count):
        # Called under signal_lock by every insertion, including pending jobs.
        with self.lock:
            entries = [e for e in self.entries.values() if not e.closed]
            user_count = sum(len(e.snapshot.signals) for e in entries if e.snapshot.owner == owner)
            global_count = sum(len(e.snapshot.signals) for e in entries)
        if (analysis_count >= self.settings.signals_per_analysis or
                user_count >= self.settings.signals_per_user or global_count >= self.settings.signals_global):
            raise CapacityError('Signal limit reached; remove an unused signal first.')

    def create_analysis(self, owner, dataset):
        s = self.initial(owner, dataset)
        with self.signal_lock, self.lock:
            if (
                len(self.entries) >= self.settings.analyses_global
                or sum(e.snapshot.owner == owner for e in self.entries.values())
                >= self.settings.analyses_per_user
            ):
                raise CapacityError("Open analysis limit reached; close an analysis.")
            self.admit_collection(s)
            self.prepare(s)
            self.entries[s.id] = AnalysisEntry(s)
            return s

    def replace(self, owner, aid, dataset, expected_revision):
        e = self.entry(owner, aid)
        with self.signal_lock, e.lock:
            if e.closed:
                raise KeyError("Analysis unavailable.")
            if e.snapshot.revision != expected_revision:
                raise Conflict("Analysis revision changed.", e.snapshot.revision)
            s = self.initial(
                owner, dataset, aid, e.snapshot.revision + 1
            )
            self.admit_collection(s, replacing=aid)
            self.prepare(s)
            self._release(e)
            e.snapshot = s
            e.tokens = {k: v + 1 for k, v in e.tokens.items()}
            return s

    def _release(self, e):
        for lease in e.leases.values():
            lease.release()
        e.leases.clear()

    def close(self, owner, aid, expected_revision=None):
        e = self.entry(owner, aid)
        with self.signal_lock, e.lock:
            if expected_revision is not None and e.snapshot.revision != expected_revision:
                raise Conflict("Analysis changed in another view; review it before closing.", e.snapshot.revision)
            e.closed = True
            self._release(e)
        for callback in self.on_close:
            callback(aid)
        with self.lock:
            self.entries.pop(aid, None)

    def close_all(self):
        for e in list(self.entries.values()):
            try:
                self.close(e.snapshot.owner, e.snapshot.id)
            except KeyError:
                pass
