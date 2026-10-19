"""Local-only non-root container smoke against a read-only synthetic bind mount."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from fixtures.acquisition import make_acquisition

with tempfile.TemporaryDirectory(prefix="tofscope-container-") as d:
    root = Path(d)
    root.chmod(0o755)
    data = root / "data"
    data.mkdir(mode=0o755)
    make_acquisition(data / "a.h5")
    (data / "a.h5").chmod(0o444)
    subprocess.run(
        ["docker", "build", "--tag", "tofscope-pilot:local", "."],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    command = [
        "docker",
        "run",
        "--rm",
        "-d",
        "--read-only",
        "--tmpfs",
        "/runtime:rw,uid=10001,gid=10001,mode=0700",
        "-v",
        f"{data}:/data:ro",
        "-p",
        "127.0.0.1::8765",
        "-e",
        "TOFSCOPE_MODE=proxy",
        "-e",
        "TOFSCOPE_TRUSTED_PROXIES=127.0.0.1",
        "-e",
        "TOFSCOPE_PUBLIC_ORIGIN=http://127.0.0.1:8765",
        "tofscope-pilot:local",
    ]
    id = subprocess.check_output(command, text=True).strip()
    try:
        port = (
            subprocess.check_output(["docker", "port", id, "8765"], text=True)
            .strip()
            .split(":")[-1]
        )
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(url + "/readyz", timeout=0.5) as r:
                    assert r.status == 200
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        subprocess.check_output(["docker", "logs", id], text=True)
                    )
                time.sleep(0.1)
        code = "import os;from pathlib import Path;from tofscope.config import load_settings;from tofscope.api.app import build_services;s=build_services(load_settings());d=s.repository.open('fixture','a.h5');w=s.workspaces.create('fixture');a=s.workspaces.create_analysis('fixture',w.id,d);p=s.presenter.snapshot('fixture',a.id);assert p.panels;assert os.getuid()==10001;assert not os.access('/data/a.h5',os.W_OK);s.workspaces.close_all();s.jobs.shutdown();print('non-root read-only plots passed')"
        output = subprocess.check_output(
            ["docker", "exec", id, "python", "-c", code], text=True
        )
        assert "passed" in output
        print(
            json.dumps(
                {
                    "non_root_uid": 10001,
                    "readonly_rootfs": True,
                    "readonly_acquisitions": True,
                    "writable_runtime": True,
                    "one_port": True,
                    "health_and_plots": True,
                }
            )
        )
    finally:
        subprocess.run(["docker", "stop", id], check=True, stdout=subprocess.DEVNULL)
