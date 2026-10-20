"""One Python service/port, loopback by default; Node is build-time only."""

import argparse
from dataclasses import asdict
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
import uvicorn
from tofscope import __version__
from tofscope.api.app import create_app
from tofscope.config import load_settings


def asset_status():
    root = files("tofscope").joinpath("static")
    manifest = root.joinpath("manifest.json")
    if not manifest.is_file():
        raise ValueError(
            "Frontend assets are missing. Run scripts/build_frontend.py before packaging."
        )
    value = json.loads(manifest.read_text())
    for name, digest in value["assets"].items():
        if hashlib.sha256(root.joinpath(name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frontend assets failed integrity verification.")
    return value


def open_after_ready(url, secret, stop):
    deadline = time.monotonic() + 30
    while not stop.is_set() and time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/readyz", timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(url + "/#bootstrap=" + secret)
                    return
        except OSError:
            pass
        stop.wait(0.1)


def run_service(settings, browser=False):
    asset_status()
    secret = secrets.token_urlsafe(32)
    url = settings.public_origin or f"http://{settings.host}:{settings.port}"
    # Bind first so occupied ports fail before browser startup or credentials change.
    sock = socket.socket(
        socket.AF_INET6 if ":" in settings.host else socket.AF_INET, socket.SOCK_STREAM
    )
    try:
        sock.bind((settings.host, settings.port))
        sock.listen(128)
    except OSError:
        sock.close()
        raise ValueError("Port is unavailable; select another --port.") from None
    secret_file = settings.runtime_dir / "launch.json"
    stop = threading.Event()
    if settings.mode == "local":
        descriptor = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as out:
            json.dump({"url": url, "secret": secret}, out)
    if browser and settings.mode == "local":
        threading.Thread(
            target=open_after_ready, args=(url, secret, stop), daemon=True
        ).start()
    try:
        print(f"ToFScope Explore {__version__}: {url} (original acquisitions read only)", flush=True)
        uvicorn.Server(
            uvicorn.Config(
                create_app(settings, bootstrap_secret=secret),
                host=settings.host,
                port=settings.port,
                workers=1,
                limit_concurrency=64,
                proxy_headers=False,
                access_log=False,
            )
        ).run(sockets=[sock])
    finally:
        stop.set()
        sock.close()
        if settings.mode == "local":
            secret_file.unlink(missing_ok=True)


def main(argv=None):
    p = argparse.ArgumentParser(description="ToFScope Explore; original acquisitions are read only")
    p.add_argument(
        "command", nargs="?", choices=["serve", "doctor", "open"], default="serve"
    )
    p.add_argument("--config", type=Path)
    p.add_argument("--data-root", type=Path)
    p.add_argument("--runtime-dir", type=Path)
    p.add_argument("--lock-dir", type=Path)
    p.add_argument("--output-root", type=Path)
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--mode", choices=["local", "proxy"])
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--version", action="version", version=__version__)
    a = p.parse_args(argv)
    try:
        settings = load_settings(
            a.config,
            cli={
                k: getattr(a, k)
                for k in (
                    "data_root",
                    "runtime_dir",
                    "lock_dir",
                    "output_root",
                    "host",
                    "port",
                    "mode",
                )
            },
        )
        if a.command == "doctor":
            assets = asset_status()
            public = asdict(settings)
            public.update(
                version=__version__,
                asset_version=assets["version"],
                scope="Explore-only",
                writes_available=False,
                save_copies_available=True,
                notes="Managed array budget excludes Python/HDF5/browser allocator overhead; one API process.",
            )
            print(json.dumps(public, default=str, indent=2))
            return 0
        if a.command == "open":
            credential = json.loads((settings.runtime_dir / "launch.json").read_text())
            webbrowser.open(credential["url"] + "/#bootstrap=" + credential["secret"])
            return 0
        # An explicit service command is browser-free; the default launch opens a browser.
        explicit_serve = bool(
            (argv if argv is not None else sys.argv[1:])
            and (argv if argv is not None else sys.argv[1:])[0] == "serve"
        )
        run_service(settings, browser=not a.no_browser and not explicit_serve)
        return 0
    except (ValueError, OSError) as exc:
        print(f"ToFScope: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
