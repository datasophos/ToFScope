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
        # A real multi-chunk transfer makes the early-close download check meaningful.
        import h5py
        with h5py.File(acquisition / "a.h5", 'r+') as handle:
            payload = handle.create_dataset('SmokePayload', (16 * 1024**2,), dtype='uint8', chunks=(1024**2,))
            for start_index in range(0, payload.size, 1024**2):
                payload[start_index:start_index + 1024**2] = 0
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
        output_root = root / "saved"
        log = (root / "server.log").open("w")
        process = None
        allowed_urls = set()
        def start():
            nonlocal process, url
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                service_port = sock.getsockname()[1]
            url = f"http://127.0.0.1:{service_port}"
            allowed_urls.add(url + "/")
            process = subprocess.Popen([
                str(env / "bin/tofscope"), "serve", "--no-browser",
                "--data-root", str(acquisition), "--runtime-dir", str(runtime),
                "--output-root", str(output_root), "--port", str(service_port),
            ], cwd=root, env=environment, stdout=log, stderr=log)
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(url + "/readyz", timeout=.5) as response:
                        assert response.status == 200
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError((root / "server.log").read_text())
                    time.sleep(.1)
            return json.loads((runtime / "launch.json").read_text())
        def stop():
            if process is not None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
        try:
            credential = start()
            with sync_playwright() as pw:
                from playwright.sync_api import expect
                browser = pw.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1500, "height": 1000})
                page.set_default_timeout(15000)
                external, downloads = [], []
                page.on('download', lambda d: downloads.append(d.suggested_filename))
                def route(r):
                    if any(r.request.url.startswith(origin) for origin in allowed_urls) or r.request.url.startswith(("blob:", "data:")):
                        r.continue_()
                    else:
                        external.append(r.request.url); r.abort()
                page.route("**/*", route)
                page.goto(url + "/#bootstrap=" + credential["secret"])
                page.get_by_role("button", name="Open TOFexplorer (.h5) file").click()
                page.get_by_role("button", name="◫ a.h5").click()
                page.get_by_test_id("panel-ion").locator("canvas").first.wait_for()
                assert page.evaluate("location.hash") == ""
                page.get_by_role("button", name="Add signal", exact=True).click()
                page.get_by_role("button", name="Create from spectrum", exact=True).click()
                page.get_by_label("Signal name", exact=True).fill("Package signal")
                page.get_by_label("Mass lower 1", exact=True).fill("1")
                page.get_by_label("Mass upper 1", exact=True).fill("2")
                page.get_by_role("button", name="Calculate signal", exact=True).click()
                expect(page.get_by_role('region', name='Signal editor')).to_be_hidden()
                page.get_by_role("button", name="Manage signals", exact=True).click()
                row = page.get_by_test_id('signal-row').filter(has_text='Package signal')
                row.get_by_role('radio').click()
                expect(row.get_by_role('radio')).to_be_checked()
                first = page.get_by_test_id('signal-row').first
                first.get_by_role('checkbox').click()
                expect(first.get_by_role('checkbox')).not_to_be_checked()
                page.get_by_role("button", name="Close Manage signals", exact=True).click()
                page.get_by_role('button', name='Use linear y scale', exact=True).click()
                with page.expect_download() as before_download:
                    page.get_by_role('button', name='Profile CSV', exact=True).click()
                before_csv = Path(before_download.value.path()).read_bytes()
                downloads.clear()
                page.get_by_role('button', name='Save as…', exact=True).click()
                page.get_by_label('Saved filename', exact=True).fill('package_copy.h5')
                page.get_by_role('button', name='Save copy', exact=True).click()
                expect(page.get_by_text('Copy saved.', exact=True)).to_be_visible()
                assert not downloads, 'Save must not automatically download.'
                expect(page.get_by_text('Large files may take a long time to download.', exact=False)).to_be_visible()
                with page.expect_download() as saved_download:
                    page.get_by_role('link', name='Download copy', exact=True).click()
                saved_path = next(output_root.rglob('package_copy.h5'))
                assert Path(saved_download.value.path()).read_bytes() == saved_path.read_bytes()
                page.get_by_role('button', name='Close save dialog', exact=True).click()
                expect(page.get_by_test_id('save-state')).to_have_text('Saved')
                stop()
                (acquisition / 'a.h5').unlink()
                credential = start()
                page.goto(url + '/#bootstrap=' + credential['secret'])
                page.get_by_role('button', name='Open TOFexplorer (.h5) file').click()
                page.get_by_role('button', name='Saved files', exact=True).click()
                page.get_by_role('button', name='◫ package_copy.h5', exact=True).click()
                expect(page.get_by_test_id('panel-ion')).to_contain_text('Package signal')
                expect(page.get_by_test_id('panel-spectrum')).to_have_attribute('data-y-scale', 'linear')
                expect(page.get_by_test_id('save-state')).to_have_text('Saved')
                page.get_by_role('button', name='Manage signals', exact=True).click()
                expect(page.get_by_test_id('signal-row')).to_have_count(2)
                expect(page.get_by_test_id('signal-row').first.get_by_role('checkbox')).not_to_be_checked()
                page.get_by_role('button', name='Close Manage signals', exact=True).click()
                with page.expect_download() as after_download:
                    page.get_by_role('button', name='Profile CSV', exact=True).click()
                assert Path(after_download.value.path()).read_bytes() == before_csv
                with page.expect_download() as png:
                    page.get_by_role('button', name='Export Depth profile PNG', exact=True).click()
                assert Path(png.value.path()).stat().st_size > 0
                # Close a direct streamed response early; the completed saved copy remains.
                cookie = next(c for c in page.context.cookies() if c['name'] == 'tofscope_session')
                analyses = page.request.get(url + '/api/v1/analyses').json()
                identifier = analyses[0]['dataset']['relative_path']
                req = urllib.request.Request(url + f'/api/v1/saved-files/{identifier}/download', headers={'Cookie': 'tofscope_session=' + cookie['value']})
                with urllib.request.urlopen(req) as transfer:
                    assert transfer.read(1024)
                assert saved_path.is_file()
                assert len(page.request.get(url + '/api/v1/saved-files').json()) == 1
                page.screenshot(path=str(output / (artifact.name + '.png')), full_page=True)
                assert not external, external
                browser.close()
            return dict(artifact=artifact.name, installed_without_node=True,
                runtime_dependencies_clean=True, offline_browser=True,
                plots_integration_export=True, saved_copy_restart_source_removed=True,
                exact_restored_csv=True, optional_download=True,
                interrupted_download_preserves_saved_file=True)
        finally:
            stop(); log.close()


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
