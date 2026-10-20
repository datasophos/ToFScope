from collections import OrderedDict
from dataclasses import dataclass, field, replace
from threading import RLock
from typing import Protocol
from uuid import uuid4
from tofscope.storage.acquisitions import SourceChanged
from tofscope.application.models import (
    WorkspaceSnapshot,
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


class WorkspaceStore(Protocol):
    def list(self, owner: str) -> list[WorkspaceSnapshot]: ...
    def get(self, owner: str, workspace_id: str) -> WorkspaceSnapshot: ...
    def put(self, snapshot: WorkspaceSnapshot) -> None: ...
    def delete(self, owner: str, workspace_id: str) -> None: ...


class MemoryWorkspaceStore:
    def __init__(self):
        self.items = {}

    def list(self, owner):
        return [x for x in self.items.values() if x.owner == owner]

    def get(self, owner, workspace_id):
        w = self.items.get(workspace_id)
        if w is None or w.owner != owner:
            raise KeyError("Workspace unavailable.")
        return w

    def put(self, snapshot):
        self.items[snapshot.id] = snapshot

    def delete(self, owner, workspace_id):
        self.get(owner, workspace_id)
        del self.items[workspace_id]


@dataclass
class AnalysisEntry:
    snapshot: AnalysisSnapshot
    lock: RLock = field(default_factory=RLock)
    receipts: OrderedDict = field(default_factory=OrderedDict)
    tokens: dict = field(default_factory=dict)
    leases: dict = field(default_factory=dict)
    closed: bool = False


class WorkspaceService:
    def __init__(self, repository, settings, store=None):
        self.repository = repository
        self.settings = settings
        self.store = store or MemoryWorkspaceStore()
        self.entries = {}
        self.lock = RLock()
        self.signal_lock = RLock()
        self.on_close = []
        self.prepare = lambda s: None

    def create(self, owner):
        with self.lock:
            if len(self.store.list(owner)) >= self.settings.analyses_per_user:
                raise CapacityError("Close an unused workspace first.")
            w = WorkspaceSnapshot(str(uuid4()), owner)
            self.store.put(w)
            return w

    def list(self, owner):
        with self.lock:
            return self.store.list(owner)

    def workspace(self, owner, wid):
        with self.lock:
            return self.store.get(owner, wid)

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

    def initial(self, owner, wid, dataset, aid=None, revision=0):
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
            return AnalysisSnapshot(
                aid or str(uuid4()),
                owner,
                wid,
                dataset,
                revision,
                frames,
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
            )

    def admit_signal(self, owner, analysis_count):
        # Called under signal_lock by every insertion, including pending jobs.
        with self.lock:
            entries = [e for e in self.entries.values() if not e.closed]
            user_count = sum(len(e.snapshot.signals) for e in entries if e.snapshot.owner == owner)
            global_count = sum(len(e.snapshot.signals) for e in entries)
        if (analysis_count >= self.settings.signals_per_analysis or
                user_count >= self.settings.signals_per_user or global_count >= self.settings.signals_global):
            raise CapacityError('Signal limit reached; remove an unused signal first.')

    def create_analysis(self, owner, workspace_id, dataset):
        s = self.initial(owner, workspace_id, dataset)
        with self.signal_lock, self.lock:
            w = self.store.get(owner, workspace_id)
            if (
                len(self.entries) >= self.settings.analyses_global
                or sum(e.snapshot.owner == owner for e in self.entries.values())
                >= self.settings.analyses_per_user
            ):
                raise CapacityError("Open analysis limit reached; close an analysis.")
            self.admit_signal(owner, 0)
            self.prepare(s)
            self.entries[s.id] = AnalysisEntry(s)
            self.store.put(replace(w, analysis_ids=w.analysis_ids + (s.id,)))
            return s

    def replace(self, owner, aid, dataset, expected_revision):
        e = self.entry(owner, aid)
        with self.signal_lock, e.lock:
            if e.closed:
                raise KeyError("Analysis unavailable.")
            if e.snapshot.revision != expected_revision:
                raise Conflict("Analysis revision changed.", e.snapshot.revision)
            s = self.initial(
                owner, e.snapshot.workspace_id, dataset, aid, e.snapshot.revision + 1
            )
            self.prepare(s)
            self._release(e)
            e.snapshot = s
            e.tokens = {k: v + 1 for k, v in e.tokens.items()}
            return s

    def _release(self, e):
        for lease in e.leases.values():
            lease.release()
        e.leases.clear()

    def close(self, owner, aid):
        e = self.entry(owner, aid)
        with self.signal_lock, e.lock:
            e.closed = True
            self._release(e)
        for callback in self.on_close:
            callback(aid)
        with self.lock:
            self.entries.pop(aid, None)
            w = self.store.get(owner, e.snapshot.workspace_id)
            self.store.put(
                replace(w, analysis_ids=tuple(x for x in w.analysis_ids if x != aid))
            )

    def delete_workspace(self, owner, wid):
        for aid in self.workspace(owner, wid).analysis_ids:
            self.close(owner, aid)
        with self.lock:
            self.store.delete(owner, wid)

    def close_all(self):
        for e in list(self.entries.values()):
            try:
                self.close(e.snapshot.owner, e.snapshot.id)
            except KeyError:
                pass
