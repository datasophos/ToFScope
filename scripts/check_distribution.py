"""Independently install wheel/sdist and exercise the packaged service without Node."""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from fixtures.acquisition import make_acquisition
from playwright.sync_api import sync_playwright


def smoke(artifact, output):
    with tempfile.TemporaryDirectory(prefix="tofscope-install-") as directory:
        root = Path(directory)
        env = root / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(env)], check=True)
        subprocess.run(
            [
                shutil.which("uv"),
                "pip",
                "install",
                "--python",
                str(env / "bin/python"),
                str(artifact),
            ],
            check=True,
            capture_output=True,
        )
        acquisition = root / "data"
        acquisition.mkdir()
        make_acquisition(acquisition / "a.h5")
        runtime = root / "runtime"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        environment = os.environ.copy()
        environment["PATH"] = str(env / "bin") + ":/usr/bin:/bin"
        environment.pop("PYTHONPATH", None)
        subprocess.run(
            [
                str(env / "bin/python"),
                "-c",
                "import importlib.util,shutil;assert shutil.which('node') is None;assert importlib.util.find_spec('marimo') is None;assert importlib.util.find_spec('anywidget') is None;assert importlib.util.find_spec('rsciio') is None",
            ],
            cwd=root,
            env=environment,
            check=True,
        )
        log = (root / "server.log").open("w")
        process = subprocess.Popen(
            [
                str(env / "bin/tofscope"),
                "serve",
                "--no-browser",
                "--data-root",
                str(acquisition),
                "--runtime-dir",
                str(runtime),
                "--port",
                str(port),
            ],
            cwd=root,
            env=environment,
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(
                        url + "/readyz", timeout=0.5
                    ) as response:
                        assert response.status == 200
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError((root / "server.log").read_text())
                    time.sleep(0.1)
            credential = json.loads((runtime / "launch.json").read_text())
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1500, "height": 1000})
                page.set_default_timeout(10000)
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
                page.goto(url + "/#bootstrap=" + credential["secret"])
                page.get_by_role("button", name="Choose an HDF5 acquisition").click()
                page.get_by_role("button", name="◫ a.h5").click()
                page.get_by_test_id("panel-ion").locator("canvas").first.wait_for()
                assert page.evaluate("location.hash") == ""
                page.get_by_role("button", name="Create from spectrum", exact=True).click()
                page.get_by_label("Signal name", exact=True).fill("Package signal")
                page.get_by_label("Mass lower 1", exact=True).fill("1")
                page.get_by_label("Mass upper 1", exact=True).fill("2")
                page.get_by_role(
                    "button", name="Calculate signal", exact=True
                ).click()
                from playwright.sync_api import expect
                editor = page.get_by_role('region', name='Signal editor')
                expect(editor).to_be_hidden(timeout=15000)
                row = page.get_by_test_id('signal-row').filter(has_text='Package signal')
                row.get_by_role('radio').click()
                expect(row.get_by_role('radio')).to_be_checked()
                expect(page.get_by_test_id('panel-ion')).to_contain_text('Package signal')
                first = page.get_by_test_id('signal-row').first
                first.get_by_role('checkbox').click()
                expect(first.get_by_role('checkbox')).not_to_be_checked()
                first.get_by_role('checkbox').click()
                expect(first.get_by_role('checkbox')).to_be_checked()
                with page.expect_download() as download:
                    page.get_by_role('button', name='Settings JSON', exact=True).click()
                settings = json.loads(Path(download.value.path()).read_text())
                assert settings['schema_version'] == 4
                assert len(settings['signals']) == 2
                for button in ('Profile CSV', 'Export Depth profile PNG'):
                    with page.expect_download() as exported:
                        page.get_by_role('button', name=button, exact=True).click()
                    assert Path(exported.value.path()).stat().st_size > 0
                page.screenshot(
                    path=str(output / (artifact.name + ".png")), full_page=True
                )
                assert not external, external
                browser.close()
            return {
                "artifact": artifact.name,
                "installed_without_node": True,
                "runtime_dependencies_clean": True,
                "offline_browser": True,
                "plots_integration_export": True,
            }
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            log.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--artifacts", type=Path, default=ROOT / "dist")
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    artifacts = [*a.artifacts.glob("*.whl"), *a.artifacts.glob("*.tar.gz")]
    if len(artifacts) != 2:
        raise ValueError("Expect one wheel and one sdist.")
    results = [smoke(path.resolve(), a.output) for path in artifacts]
    (a.output / "distribution.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results))


if __name__ == "__main__":
    main()
