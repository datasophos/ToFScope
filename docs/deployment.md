# Running the packaged Explore pilot

Install a tested wheel with `uv tool install ./dist/tofscope-0.2.0-py3-none-any.whl`
or `python -m pip install ...`. The sdist also contains release-built assets:
installing it needs Python build tooling, not Node. One Uvicorn API process serves
React, chart scripts, scientific data and downloads from one port. No CDN,
external account service or runtime Node is used in local mode.

Local desktop launch:

```sh
tofscope --data-root /path/to/acquisitions --output-root /path/to/saved-analyses
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

Open A/B/A as three independent file analyses. Refresh automatically recovers the
owner's live file tabs; there are no workspace containers or manual analysis-ID
reconnect controls. View heartbeats are 15 s, leases 45 s, disconnect grace 120 s
and idle expiry 15 min. Explicit close cancels pending work. Live analyses and
jobs remain ephemeral; **Save as…** persists committed work in a new HDF5 file.
Opening that file restores all stored/custom/hidden signals, exact custom
results, names/colors, ROI, frame/depth selections and display settings.

Configure persistent output with `--output-root`, `TOFSCOPE_OUTPUT_ROOT`, or
`output_root` in TOML. It defaults to the effective acquisition folder
(`data_root`), which defaults to the process current working directory.
Configure a separate writable output folder for read-only acquisition mounts.
The file picker displays both configured folders; Save as also displays the
complete save destination in a tooltip. In local mode, saved copies go directly
into the configured output folder and its file list shows that folder’s .h5 files.
When it equals the acquisition folder, both shortcuts show the same .h5 files.
Hosted proxy mode uses private owner hash subdirectories; its saved-file picker
and downloads enforce the authenticated owner. Runtime cleanup must not remove
saved files in either mode.
Copies are portable: download or move a completed copy into another installation's
acquisition root to open it there under fresh service identities. Embedded metadata
contains no credentials or original server paths.

Save creates an exclusive temporary sibling, streams the acquisition with an
8-MiB buffer, adds versioned analysis state and original-resolution custom values,
verifies checksums, and publishes by exclusive hard link. Existing destinations
and input files are never replaced. This requires same-filesystem hard-link
support; actual NFS/crash durability is unqualified. Cancel/error before publication
removes the temporary output. A successful save remains valid if a later browser
refresh or download fails. Private `.tmp-*` leftovers from a process crash are
never listed as completed files and may be removed while the service is stopped.

A saved copy includes the full acquisition. Allow input size plus derived volumes,
HDF5 overhead and concurrent saves; disk admission reserves capacity conservatively.
Saving is unavailable during calculations or uncommitted drafts. A revision/source
change before publication fails the save rather than persisting an ambiguous state.
The UI marks saved/unsaved state and asks before close/replacement. Browser close
can warn but cannot guarantee an asynchronous save during teardown.

Save does not start a browser download. **Download copy** is optional and notes that
large files may take a long time. Transfers use bounded buffers; disconnecting does
not delete the saved file. Browser transfer resume/range requests are not provided.

The default managed budget is 4 GiB server / 2 GiB user / 1 GiB analysis, with
8 analyses/user and 32/server. Queue limits are 4/analysis, 8/user, 32/server;
two workers run at most one job/user and round-robin users. Shared immutable
channel bytes count once physically; referencing analyses are charged logically.
Raw reconstruction has separately reserved scratch space and frame-boundary
cancellation. Python objects, HDF5's internal caches/ragged decoding, allocator
retention and browser/GPU memory add overhead outside the managed NumPy budget;
use OS/container RSS limits with headroom. These controls are admission limits,
not a guarantee that total process RSS equals managed bytes. Signal metadata has a configurable default quota of 129 per analysis. The response cap is 32 MiB.

Acquisition reads use canonical-path cooperative locks in a writable external
lock directory, waiting up to 30 s on executor threads. All service processes
must share that directory. One API process is supported; do not scale workers
behind a load balancer because live analysis state is in memory. Independent programs
that ignore these locks can still replace acquisitions: identity checks mark
all dependent analyses stale and require explicit reopen. Original-acquisition write endpoints remain unavailable, even when experimental
native-write policy flags are set. New saved copies use a separate output policy;
they do not enable vendor-native write-back.

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
artifact for rollback. Restarting discards unsaved analyses; saved HDF5 copies
restore committed state when reopened.

Actual NFS qualification remains required on the intended mount: mount it read
only, use the real service UID and external shared lock directory, run simultaneous
same-file and two-file reads, prove cross-process lock exclusion/timeouts, and
verify replacement is detected using a disposable copy. Record mount options,
latency/RSS, interrupted-client recovery and permission failures. Local POSIX and
container checks do not establish NFS behavior. Do not enable acquisition writes
without the separate commercial/native-save and NFS replacement qualification.


### Signal workspace UI

The signal tray, contextual editor and plot-local controls require the matching
Python backend and bundled frontend. Deploy them together and restart once; a
refresh alone cannot activate a backend contract change. Restart resets temporary
analyses and unsaved drafts. Export committed settings/profile data before a
planned restart. New analyses default to log image colors and relative profiles;
the spectrum defaults to logarithmic Y. These remain per-analysis display choices.

Record limits include pending and hidden signals: `signals_per_analysis=129`,
`signals_per_user=512`, `signals_global=2048`. Configure them through the existing
TOML/environment/CLI precedence; environment names use `TOFSCOPE_SIGNALS_*`.
Memory admission and job limits still apply independently. There is no legacy
comparison-limit option or old active/comparison API compatibility layer.

Container deployments need a writable persistent volume mounted at `/saved` for
`TOFSCOPE_OUTPUT_ROOT=/saved`, plus writable `/runtime`; keep `/data` read only.
The local container check uses temporary `/saved` storage for disposable tests.
Do not use that temporary volume configuration when persisted copies must survive
container replacement.
