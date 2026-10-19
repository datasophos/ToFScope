"""Launch the immutable prototype in its own environment on disposable data."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from fixtures.acquisition import make_acquisition

p = argparse.ArgumentParser()
p.add_argument("--checkout", type=Path, required=True)
a = p.parse_args()
assert (
    subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=a.checkout, text=True
    ).strip()
    == "37ecacf24c32388cd7f84bc11fa509989cc44775"
)
with tempfile.TemporaryDirectory(prefix="tofscope-prototype-smoke-") as d:
    root = Path(d)
    make_acquisition(root / "a.h5")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ | {
        "TOFSCOPE_DATA_ROOT": d,
        "TOF_FILE": "a.h5",
        "TOFSCOPE_ALLOW_WRITES": "false",
        "TOFSCOPE_ALLOW_UNVERIFIED_NATIVE": "false",
    }
    log = (root / "server.log").open("w")
    process = subprocess.Popen(
        [
            str(a.checkout / ".venv/bin/python"),
            "-m",
            "marimo",
            "run",
            "app.py",
            "--headless",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=a.checkout,
        env=env,
        stdout=log,
        stderr=log,
    )
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                urllib.request.urlopen(url, timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.1)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1550, "height": 1100})
            page.goto(url)
            app = page.locator(".tof-app")
            app.wait_for(timeout=30000)
            expect(app.locator("[data-field=status]")).to_have_text(
                "Ready", timeout=30000
            )
            assert app.get_attribute("data-roi") == "[0,1,0,0]"
            browser.close()
        print(
            json.dumps(
                {
                    "reference_commit": "37ecacf",
                    "own_locked_environment": True,
                    "http_launch": True,
                    "widget_ready": True,
                    "fixture_loaded": True,
                    "writes_enabled": False,
                }
            )
        )
    finally:
        process.terminate()
        process.wait(timeout=15)
        log.close()
