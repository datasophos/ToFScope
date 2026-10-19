"""Read-only browser qualification of a packaged/source application on one file."""

import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        log = (a.output / "server.log").open("w")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "tofscope.cli",
                "serve",
                "--no-browser",
                "--data-root",
                str(a.file.parent),
                "--runtime-dir",
                d,
                "--port",
                str(port),
            ],
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(url + "/readyz", timeout=0.5).close()
                    break
                except OSError:
                    time.sleep(0.1)
            secret = json.loads((Path(d) / "launch.json").read_text())["secret"]
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1660, "height": 1100})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                external = []

                def route(r):
                    if r.request.url.startswith(url) or r.request.url.startswith(
                        ("blob:", "data:")
                    ):
                        r.continue_()
                    else:
                        external.append(r.request.url)
                        r.abort()

                page.route("**/*", route)
                page.goto(url + "/#bootstrap=" + secret)
                page.get_by_role("button", name="Choose an HDF5 acquisition").click()
                page.get_by_label("Search files").fill(a.file.name)
                t = time.perf_counter()
                page.get_by_role("button", name="◫ " + a.file.name, exact=True).click()
                page.get_by_test_id("panel-front").locator("canvas").first.wait_for(
                    timeout=30000
                )
                page.get_by_test_id("panel-spectrum").locator("canvas").first.wait_for(
                    timeout=30000
                )
                load_ms = (time.perf_counter() - t) * 1000
                timings = []
                for _ in range(12):
                    version = page.get_by_test_id("panel-ion").get_attribute(
                        "data-content-version"
                    )
                    t = time.perf_counter()
                    page.get_by_role("button", name="Next frame", exact=True).click()
                    page.wait_for_function(
                        "old=>document.querySelector('[data-testid=panel-ion]').dataset.contentVersion!==old",
                        arg=version,
                    )
                    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                    timings.append((time.perf_counter() - t) * 1000)
                page.screenshot(path=str(a.output / "real-explore.png"), full_page=True)
                assert not errors, errors
                assert not external, external
                result = {
                    "initial_four_panels_ms": load_ms,
                    "frame_update_p50_ms": sorted(timings)[6],
                    "frame_update_p95_ms": sorted(timings)[10],
                    "offline": True,
                    "browser_errors": errors,
                }
                (a.output / "browser.json").write_text(json.dumps(result, indent=2))
                print(json.dumps(result))
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=15)
            log.close()


if __name__ == "__main__":
    main()
