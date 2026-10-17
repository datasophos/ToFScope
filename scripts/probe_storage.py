"""Probe cooperative locking and same-directory replacement on a POSIX mount.

Usage: uv run python scripts/probe_storage.py /configured/data/root
Only an owned temporary directory is touched. Run on the actual deployment
mount; this local-process check does not prove cross-host NFS locking.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataset_io import dataset_lock


def probe(root):
    root=Path(root).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='.tofscope-probe-',dir=root) as temporary:
        path=Path(temporary)/'test';path.write_bytes(b'original')
        script="from dataset_io import dataset_lock;from filelock import Timeout;import sys\ntry:\n with dataset_lock(sys.argv[1]).acquire(timeout=.1):sys.exit(1)\nexcept Timeout:sys.exit(0)"
        with dataset_lock(path):
            result=subprocess.run([sys.executable,'-c',script,str(path)],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=10)
            if result.returncode:raise RuntimeError('Cross-process lock exclusion failed: '+result.stderr)
            prepared=path.with_suffix('.tmp');prepared.write_bytes(b'replacement')
            with prepared.open('rb') as stream:os.fsync(stream.fileno())
            os.replace(prepared,path)
            descriptor=os.open(path.parent,os.O_RDONLY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
            if path.read_bytes()!=b'replacement':raise RuntimeError('Replacement verification failed.')
    return dict(cross_process_lock=True,same_directory_replace=True,fsync=True,cross_host_nfs='not tested')


if __name__=='__main__':print(json.dumps(probe(sys.argv[1]),indent=2))
