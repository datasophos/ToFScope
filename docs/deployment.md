# Running the packaged Explore pilot

Install a tested wheel with `uv tool install ./dist/tofscope-0.2.0-py3-none-any.whl`
or `python -m pip install ...`. The sdist also contains release-built assets:
installing it needs Python build tooling, not Node. One Uvicorn API process serves
React, chart scripts, scientific data and downloads from one port. No CDN,
external account service or runtime Node is used in local mode.

Local desktop launch:

```sh
tofscope --data-root /path/to/acquisitions
```

The default address is `http://127.0.0.1:8765`. An empty configured root opens the
file-picker empty state. Without a data root, the app uses an empty directory in
its writable runtime directory. There is no adjacent-example fallback. Set
`TOF_FILE` to a root-relative or confined absolute path for initial open.

Browser-free local service:

```sh
tofscope serve --no-browser --data-root /path/to/acquisitions --runtime-dir /path/to/private/runtime
tofscope open --runtime-dir /path/to/private/runtime
```

The second command opens the existing local service from the same machine. A
launcher secret goes through a URL fragment (removed before the first API
request), is exchanged once for an HttpOnly SameSite cookie, and is never logged.
The private runtime `launch.json` supports `open`; keep the runtime user-owned.
Subsequent opens in the same browser use its authenticated cookie. A new browser
without that cookie needs a fresh service launch. The local cookie expires after
24 hours. JSON API clients can read that mode-0600 file, POST its secret to
`/api/v1/auth/bootstrap` with the service Origin, retain the response cookie and
send the returned CSRF token in `X-CSRF-Token` on mutations. Never place this
secret in command logs or share it as a user account credential.

Configuration precedence is CLI > `TOFSCOPE_*` environment > `[tofscope]` TOML >
defaults. Use `--config tofscope.example.toml`. `tofscope doctor` checks package
asset hashes and configured root/runtime/locks and reports limits/version without
credentials. `/healthz` is a cheap liveness check; `/readyz` checks asset presence.
The versioned OpenAPI document is `/api/v1/openapi.json`; CDN-backed Swagger UI
is disabled.

For a group deployment, terminate HTTPS/authentication at a trusted reverse proxy,
set `TOFSCOPE_MODE=proxy`, `TOFSCOPE_TRUSTED_PROXIES` to the exact peer IPs,
`TOFSCOPE_PUBLIC_ORIGIN=https://your-host`, and an identity header that the proxy
**overwrites after authenticating**. Bind to a private interface reachable only
by that proxy. Forward Host and Origin unchanged. Uvicorn does not trust forwarded
client IPs. Requests from other peers, missing identity, foreign IDs and foreign
origins are rejected. The configured research-group data root grants authenticated
group members read access; repository authorization is a separate injectable
policy. This pilot does not manage accounts or enable shared mutable editing.

Each browser tab starts a new workspace. Opening A/B/A creates three independent
analyses. Explicit reattach accepts an owned analysis ID; attached views share
canonical revisions, while focus/zoom/drafts stay local. View heartbeats are 15 s,
leases 45 s, disconnect grace 120 s and idle expiry 15 min. Explicit close cancels
work immediately; it does not rely on browser unload delivery. Workspace metadata,
active arrays and jobs are ephemeral: restarting loses them. Export settings
before restart or source replacement; recipe re-import is not implemented.

The default managed budget is 4 GiB server / 2 GiB user / 1 GiB analysis, with
8 analyses/user and 32/server. Queue limits are 4/analysis, 8/user, 32/server;
two workers run at most one job/user and round-robin users. Shared immutable
channel bytes count once physically; referencing analyses are charged logically.
Raw reconstruction has separately reserved scratch space and frame-boundary
cancellation. Python objects, HDF5's internal caches/ragged decoding, allocator
retention and browser/GPU memory add overhead outside the managed NumPy budget;
use OS/container RSS limits with headroom. These controls are admission limits,
not a guarantee that total process RSS equals managed bytes. Comparison metadata
has a configurable default quota of 128 per analysis. The response cap is 32 MiB.

Acquisition reads use canonical-path cooperative locks in a writable external
lock directory, waiting up to 30 s on executor threads. All service processes
must share that directory. One API process is supported; do not scale workers
behind a load balancer because workspace state is in memory. Independent programs
that ignore these locks can still replace acquisitions: identity checks mark
all dependent analyses stale and require explicit reopen. No write endpoint
exists, even when either experimental write policy flag is set. Preserved native
write validators are for future features and disposable-copy tests only.

Optional local container verification:

```sh
uv build
uv run python scripts/check_container.py
```

The Dockerfile installs the built wheel, runs UID 10001 and exposes port 8765.
Use `/data:ro`, a writable `/runtime` owned by that UID, one mapped port, and the
proxy settings above. The check uses a disposable acquisition, read-only rootfs,
read-only data bind and writable private tmpfs. It never mounts the real data
root writable. Pin the wheel/container digest when upgrading; preserve the prior
artifact for rollback. Restarting either version discards ephemeral workspaces.

Actual NFS qualification remains required on the intended mount: mount it read
only, use the real service UID and external shared lock directory, run simultaneous
same-file and two-file reads, prove cross-process lock exclusion/timeouts, and
verify replacement is detected using a disposable copy. Record mount options,
latency/RSS, interrupted-client recovery and permission failures. Local POSIX and
container checks do not establish NFS behavior. Do not enable acquisition writes
without the separate commercial/native-save and NFS replacement qualification.
