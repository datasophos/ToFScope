"""Read-only runner comparison; workers reopen handles, no ndarray IPC."""
import argparse
from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
import json
from pathlib import Path
import time
import resource
import h5py
import numpy as np

def operation(path):
    start=time.perf_counter()
    with h5py.File(path,'r') as f:
        d=f['PeakData/PeakData'];s=d[:min(4,len(d)),:,:,0];value=float(s.sum(dtype=np.float64))
    return dict(ms=(time.perf_counter()-start)*1000,sum=value,peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--file',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();results={}
    for executor in [ThreadPoolExecutor,ProcessPoolExecutor]:
        t=time.perf_counter()
        with executor(2) as pool:values=list(pool.map(operation,[a.file,a.file]))
        results[executor.__name__]=dict(total_ms=(time.perf_counter()-t)*1000,workers=values)
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'runner.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
