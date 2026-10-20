"""Disposable loopback-only fixture service. Never use its proxy policy in production."""

from pathlib import Path
import sys
import tempfile
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from fixtures.acquisition import make_acquisition
from tofscope.config import Settings
from tofscope.api.app import create_app

with tempfile.TemporaryDirectory(prefix="tofscope-e2e-") as d:
    root = Path(d)
    make_acquisition(root / "a.h5")
    make_acquisition(root / "b.h5")
    settings = Settings(
        root,
        runtime_dir=root / "runtime",
        output_root=root / "saved",
        mode="proxy",
        trusted_proxies=("127.0.0.1",),
        host="127.0.0.1",
        port=18764,
        public_origin="http://127.0.0.1:18763",
    )
    uvicorn.run(
        create_app(settings),
        host="127.0.0.1",
        port=18764,
        proxy_headers=False,
        log_level="warning",
    )
