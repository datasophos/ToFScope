"""Capture exact, unscaled read-only reference values; never alter an acquisition."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    from tofscope.storage.explorer import inspect_file, stored_peak, roi_from_bounds
except ImportError:
    from explorer import inspect_file, stored_peak, roi_from_bounds

def main():
    p=argparse.ArgumentParser();p.add_argument('--file',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    times=[]
    for _ in range(20):
        t=time.perf_counter();m=inspect_file(a.file);v=stored_peak(a.file,0);profile=v.mean(axis=(1,2));front=v.sum(axis=1,dtype=np.float64);times.append((time.perf_counter()-t)*1000)
    np.savez(a.output/'canonical.npz',profile=profile,front=front,top=v.sum(axis=0,dtype=np.float64),spectrum=m['spectrum'],mass_axis=m['masses'])
    result=dict(shape=m['shape'],file_sha256=hashlib.sha256(a.file.read_bytes()).hexdigest(),python=sys.version,p50_ms=float(np.percentile(times,50)),p95_ms=float(np.percentile(times,95)),maxrss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,payload_bytes=(a.output/'canonical.npz').stat().st_size,roi_example=roi_from_bounds([2,6,8,4],(1301,128,128),20))
    (a.output/'manifest.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
