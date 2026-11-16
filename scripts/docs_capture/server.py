"""Disposable service for documentation captures; never expose it publicly."""

import shutil
import tempfile
from pathlib import Path

import h5py
import uvicorn
from generate_demo import DEMO, generate

from tofscope.api.app import create_app
from tofscope.config import Settings


def main():
    if not DEMO.exists():
        temporary = DEMO.with_suffix(".partial")
        try:
            generate(temporary)
            temporary.replace(DEMO)
        finally:
            temporary.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="tofscope-doc-capture-") as directory:
        root = Path(directory)
        data = root / "data"
        data.mkdir()
        shutil.copyfile(DEMO, data / DEMO.name)
        shutil.copyfile(DEMO, data / "mosfet-raw.h5")
        with h5py.File(data / "mosfet-raw.h5", "r+") as raw:
            del raw["PeakData/PeakData"]
        settings = Settings(
            data,
            runtime_dir=root / "runtime",
            output_root=root / "saved",
            mode="proxy",
            trusted_proxies=("127.0.0.1",),
            host="127.0.0.1",
            port=18765,
            public_origin="http://127.0.0.1:18765",
        )
        uvicorn.run(
            create_app(settings),
            host="127.0.0.1",
            port=18765,
            proxy_headers=False,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
