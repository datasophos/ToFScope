import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class WindowsStartupTests(unittest.TestCase):
    def test_startup_without_posix_user_id(self):
        with tempfile.TemporaryDirectory() as directory:
            script = """
import os
import tempfile
from pathlib import Path
import h5py, numpy, filelock, fastapi, uvicorn, psutil
tempfile.tempdir = {directory!r}
if hasattr(os, 'getuid'):
    del os.getuid
import tofscope.cli
from tofscope.config import Settings
from tofscope.storage.dataset_io import LOCK_DIR
settings = Settings(data_root=Path({directory!r}))
assert settings.lock_dir == LOCK_DIR.get().resolve()
assert settings.lock_dir.is_dir()
""".format(directory=directory)
            result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


class SafeDownloadTests(unittest.TestCase):
    def test_binary_file_opens_without_following_links(self):
        from tofscope.storage.safe_open import open_saved_file

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.h5"
            payload = b"\x00\r\n\x1a\xff"
            path.write_bytes(payload)
            with open_saved_file(path) as stream:
                self.assertEqual(stream.read(), payload)
            link = path.with_name("link.h5")
            try:
                link.symlink_to(path)
            except OSError:
                self.skipTest("creating symbolic links requires privileges")
            with self.assertRaises(OSError):
                open_saved_file(link)
