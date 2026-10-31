"""Rebuild and reload the local Great Docs site when its sources change."""

from __future__ import annotations

import argparse
import functools
import http.server
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "great-docs" / "_site"
REVISION_PATH = "/__docs_preview_revision"


def source_snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Record source file metadata without watching generated site output."""
    candidates = [
        root / "great-docs.yml",
        root / "pyproject.toml",
        root / "uv.lock",
        root / "README.md",
        root / "LICENSE",
        root / "scripts" / "prepare_docs.py",
    ]
    docs = root / "docs"
    if docs.is_dir():
        candidates.extend(path for path in docs.rglob("*") if path.is_file())
    snapshot = {}
    for path in candidates:
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        snapshot[str(path.relative_to(root))] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


class PreviewState:
    def __init__(self) -> None:
        self._revision = 0
        self._lock = threading.Lock()

    def current(self) -> int:
        with self._lock:
            return self._revision

    def advance(self) -> None:
        with self._lock:
            self._revision += 1


def make_server(site: Path, state: PreviewState, port: int) -> http.server.ThreadingHTTPServer:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def do_GET(self) -> None:
            if urlsplit(self.path).path == REVISION_PATH:
                data = str(state.current()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

            path = Path(self.translate_path(self.path))
            if path.is_dir():
                path = path / "index.html"
            if path.suffix == ".html" and path.is_file():
                # Capture the revision before reading: a concurrent rebuild then
                # causes this response to reload instead of staying stale.
                revision = state.current()
                data = path.read_bytes()
                script = (
                    "<script>(()=>{let revision=" + str(revision) + ";"
                    "setInterval(async()=>{try{const r=await fetch('"
                    + REVISION_PATH
                    + "',{cache:'no-store'});"
                    "if(r.ok && Number(await r.text())!==revision) location.reload();"
                    "}catch(e){}},1000);})();</script>"
                ).encode()
                data = data.replace(b"</body>", script + b"</body>", 1)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            super().do_GET()

        def log_message(self, format: str, *args: object) -> None:
            if urlsplit(self.path).path != REVISION_PATH:
                super().log_message(format, *args)

    handler = functools.partial(Handler, directory=str(site))
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)


def build() -> bool:
    print("\nBuilding documentation...", flush=True)
    result = subprocess.run(
        ["uv", "run", "--frozen", "--only-group", "docs", "great-docs", "build"],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        print("Build failed; waiting for another source change.", flush=True)
        return False
    print("Build complete.", flush=True)
    return True


def watch(state: PreviewState, snapshot: dict[str, tuple[int, int]]) -> None:
    while True:
        time.sleep(1)
        current = source_snapshot(ROOT)
        if current == snapshot:
            continue
        # Wait for editors that save in several steps to settle.
        time.sleep(0.5)
        snapshot = source_snapshot(ROOT)
        if build():
            state.advance()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3000, help="Preview port (default: 3000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    args = parser.parse_args()
    state = PreviewState()
    try:
        server = make_server(SITE, state, args.port)
    except OSError as exc:
        parser.exit(1, f"Cannot start preview on port {args.port}: {exc}\n")
    try:
        snapshot = source_snapshot(ROOT)
        if not build():
            parser.exit(1, "Initial documentation build failed.\n")
        threading.Thread(target=watch, args=(state, snapshot), daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"\nPreview: {url} (Ctrl-C to stop)", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPreview stopped.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
