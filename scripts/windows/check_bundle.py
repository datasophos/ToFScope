"""Exercise launcher control against the frozen CLI child on Windows."""

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from tofscope.windows_launcher import ServiceController


def main():
    executable = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="tofscope launcher check ") as directory:
        state = Path(directory)
        service = ServiceController(state)
        try:
            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "executable", str(executable)
            ):
                service.start(state)
            process = service.process
            deadline = time.monotonic() + 60
            while not service.ready():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(service.log_path.read_text())
                time.sleep(0.1)
            service.stop()
            if process.returncode != 0:
                raise RuntimeError("Frozen service did not stop cleanly")
            if service.runtime_dir.exists():
                raise RuntimeError("Private service runtime was not cleaned up")
        finally:
            service.stop()
    print("Frozen launcher child started and stopped cleanly.")


if __name__ == "__main__":
    main()
