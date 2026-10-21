from dataclasses import dataclass
from threading import RLock
import time
from uuid import uuid4


@dataclass(frozen=True)
class ViewLease:
    id: str
    analysis_id: str
    expires_at: float


class LifecycleService:
    def __init__(self, workspaces, jobs, settings, clock=time.monotonic):
        self.analyses = workspaces
        self.jobs = jobs
        self.settings = settings
        self.clock = clock
        self.views = {}
        self.last_seen = {}
        self.lock = RLock()
        workspaces.on_close.append(self.closed)

    def attach(self, owner, analysis_id):
        self.analyses.get(owner, analysis_id)
        with self.lock:
            now = self.clock()
            lease = ViewLease(
                str(uuid4()), analysis_id, now + self.settings.lease_seconds
            )
            self.views[lease.id] = (owner, lease)
            self.last_seen[analysis_id] = now
            return lease

    def heartbeat(self, owner, vid):
        with self.lock:
            o, lease = self.views.get(vid, (None, None))
            if o != owner:
                raise KeyError("View unavailable.")
            self.analyses.get(owner, lease.analysis_id)
            now = self.clock()
            lease = ViewLease(vid, lease.analysis_id, now + self.settings.lease_seconds)
            self.views[vid] = (owner, lease)
            self.last_seen[lease.analysis_id] = now
            return lease

    def detach(self, owner, vid):
        with self.lock:
            o, lease = self.views.get(vid, (None, None))
            if o != owner:
                raise KeyError("View unavailable.")
            self.last_seen[lease.analysis_id] = self.clock()
            del self.views[vid]

    def closed(self, aid):
        with self.lock:
            self.views = {
                v: pair for v, pair in self.views.items() if pair[1].analysis_id != aid
            }
            self.last_seen.pop(aid, None)

    def sweep(self):
        now = self.clock()
        with self.lock:
            live = {v.analysis_id for _, v in self.views.values() if v.expires_at > now}
            for e in list(self.analyses.entries.values()):
                s = e.snapshot
                if s.id in live:
                    self.last_seen[s.id] = now
                    continue
                absence = now - self.last_seen.setdefault(s.id, now)
                if absence >= self.settings.reconnect_seconds:
                    self.jobs.close_analysis(s.id)
                if absence >= self.settings.idle_seconds:
                    try:
                        self.analyses.close(s.owner, s.id)
                    except KeyError:
                        pass
            self.views = {k: v for k, v in self.views.items() if v[1].expires_at > now}
