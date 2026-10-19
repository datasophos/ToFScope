"""Validate prebuilt assets for both source-checkout and sdist installations."""
from setuptools import setup
from setuptools.command.build_py import build_py
from pathlib import Path
import hashlib
import json
import runpy
class CheckedBuild(build_py):
    def run(self):
        root=Path(__file__).parent;static=root/'src/tofscope/static';manifest=static/'manifest.json'
        if not manifest.exists():raise RuntimeError('Missing bundled frontend. Run scripts/build_frontend.py before building artifacts.')
        m=json.loads(manifest.read_text())
        for name,digest in m['assets'].items():
            if hashlib.sha256((static/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Bundled asset integrity mismatch.')
        if (root/'frontend/src').exists():
            # This source check is omitted in an sdist, which contains only verified assets.
            module=runpy.run_path(str(root/'scripts/build_frontend.py'))
            if module['source_hash']()!=m['source_sha256']:raise RuntimeError('Stale frontend assets. Run scripts/build_frontend.py.')
        super().run()
setup(cmdclass={'build_py':CheckedBuild})
