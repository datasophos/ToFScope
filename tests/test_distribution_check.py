"""Checks for distribution smoke-test preflight validation."""

import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


class DistributionPreflightTests(unittest.TestCase):
    def test_rejects_artifacts_from_another_checkout_before_installing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            metadata = b"Metadata-Version: 2.1\nName: tofscope\nVersion: 999.0\n\n"
            with zipfile.ZipFile(
                artifacts / "tofscope-999.0-py3-none-any.whl", "w"
            ) as wheel:
                wheel.writestr("tofscope-999.0.dist-info/METADATA", metadata)
            with tarfile.open(artifacts / "tofscope-999.0.tar.gz", "w:gz") as source:
                entry = tarfile.TarInfo("tofscope-999.0/PKG-INFO")
                entry.size = len(metadata)
                source.addfile(entry, io.BytesIO(metadata))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/check_distribution.py",
                    "--artifacts",
                    str(artifacts),
                    "--output",
                    str(root / "results"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match", result.stderr)
            self.assertFalse((root / "results" / "distribution.json").exists())
