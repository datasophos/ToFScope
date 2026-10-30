# Deploying ToFScope

These instructions describe different ways to deploy ToFScope either locally, on a server, or in a Docker container.

For simplified instructions on how to use ToFScope locally on macOS, see the [macOS ToFScope guide](macos-tofscope.md).

## Local desktop

Clone the ToFScope repository and install ToFScope from the checkout:

```sh
git clone https://github.com/datasophos/ToFScope.git
cd ToFScope
uv tool install .
```

The repository includes built frontend assets, so installation does not require Node or javascript tooling. One Uvicorn API process
serves React, chart scripts, scientific data and downloads from one port. No CDN,
external account service or runtime Node is used in local mode.

Start the desktop launcher:

```sh
tofscope --data-root /path/to/acquisitions --output-root /path/to/saved-analyses
```

The default address is `http://127.0.0.1:8765`. An empty configured root opens the
file-picker empty state. The acquisition folder defaults to the current working directory; the saved
copies folder defaults to the acquisition folder unless `--output-root` is set.
You can use the `TOF_FILE` environment variable (must be relative to `data-root` to have the application open a specifc file on first launch.

### Local service without automatic browser launch

Use this mode when you want to start the service without opening a browser immediately,
for example when starting it from a script or using an API client. You can open its
local interface later from another terminal while the service is running:

```sh
tofscope serve --no-browser --data-root /path/to/acquisitions --runtime-dir /path/to/private/runtime
tofscope open --runtime-dir /path/to/private/runtime
```

The second command opens the running service on the same computer. The local web
server is protected by a randomly generated launch secret so other people cannot simply open it. Regardless, you should keep the runtime folder
private and do not share the launch address. If you switch browsers or access expires
after 24 hours, restart the service to open it again.

## Self-hosted service

*Self-hosted, multi-user deployment is under development and will be documented
further when it is ready.*

## Configuration and storage

Command-line options take precedence over `TOFSCOPE_*` environment variables,
then `[tofscope]` settings in a TOML file. See `tofscope.example.toml` for options.
Run `tofscope doctor` to check configuration and packaged assets; the `/healthz` and
`/readyz` endpoints provide service health checks.

**Save as…** writes a new HDF5 copy containing the acquisition and committed analysis;
the original file is not changed. Set `--output-root` to a writable folder, especially
when acquisitions are read-only. Saved copies will require at least as much space as the original
and the output filesystem must support hard links. Save your work before restarting:
unsaved analyses and jobs are lost. See the [user guide](user-guide.md) for working
with files and analyses.

ToFScope supports one API process; analysis state is held in memory. Its managed
memory limits do not include all Python, HDF5, or browser memory, so allow extra
headroom. Acquisition reads use a writable lock directory; processes accessing the
same files through ToFScope must share it.

## Docker container

> **Untested:** This container deployment workflow has not been verified end to end.
> Self-hosted authentication and proxy configuration are still under development.

The container serves ToFScope behind an authenticating reverse proxy. Build the image
from a clone of the repository (this requires Docker and `uv`):

```sh
git clone https://github.com/datasophos/ToFScope.git
cd ToFScope
uv build
docker build -t tofscope .
```

Start it with the acquisition folder mounted read-only and a persistent volume for
saved analyses. Replace the acquisition path, public URL, and proxy address with
values for your setup:

```sh
docker volume create tofscope-saved
docker run -d --name tofscope \
  -p 127.0.0.1:8765:8765 \
  --mount type=bind,src=/path/to/acquisitions,dst=/data,readonly \
  --mount type=volume,src=tofscope-saved,dst=/saved \
  -e TOFSCOPE_TRUSTED_PROXIES="<proxy-peer-ip>" \
  -e TOFSCOPE_PUBLIC_ORIGIN=https://tofscope.example.org \
  tofscope
```

Replace `<proxy-peer-ip>` with the proxy's IP address **as seen by the container**;
it may differ from the proxy's host address. Configure the proxy to provide HTTPS,
authenticate users, and overwrite `X-ToFScope-User` with the authenticated username.
Forward the original `Host` and `Origin` headers. Open the configured public URL in
a browser. ToFScope grants authenticated users access to the mounted acquisition
folder; it does not manage accounts.

Use `docker logs tofscope` to inspect startup errors and `docker stop tofscope` to
stop the service. The named volume preserves saved analyses when the container is
removed. Restarting discards unsaved work.

## NFS-backed acquisitions

NFS deployments have not been validated. Before using an NFS mount, test it with
representative data and workloads, including concurrent reads and file replacement.
Keep acquisition files read-only and use a shared lock directory.
