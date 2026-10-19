"""Real acquisition scientific qualification. All HDF5 handles use mode r."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import resource
import time
import h5py
import numpy as np
from rsciio.tofwerk import file_reader,compute_peak_data_from_eventlist
from rsciio.utils.file import get_file_handle
from tofscope.science.integration import integrate_event_windows
from tofscope.storage.explorer import integration_parameters

def main():
    p=argparse.ArgumentParser();p.add_argument('--file',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();before=a.file.stat();result={}
    with h5py.File(a.file,'r') as f:
        table=f['PeakData/PeakTable'][:];i=int(np.argmin(abs(table['mass']-27)));r=table[i];m=float(r['mass']);masses=np.sort(np.unique(table['mass']));j=list(masses).index(r['mass']);lo=(float(masses[j-1])+m)/2 if j else m-.1;hi=(m+float(masses[j+1]))/2 if j+1<len(masses) else m+.1
        expected=f['PeakData/PeakData'][:4,:,:,i:i+1];axis=f['FullSpectra/MassAxis'][:];ratio,norm=integration_parameters(f);events=f['FullSpectra/EventList'][:4];bounds=[(float(r['lower integration limit']),float(r['upper integration limit']))]
        t=time.perf_counter();raw=np.stack([integrate_event_windows(v,axis,ratio,norm,bounds) for v in events]);result['raw_ms']=(time.perf_counter()-t)*1000
        other=compute_peak_data_from_eventlist(events,axis,len(axis),ratio,norm,[{'mass':m,'lower_integration_limit':bounds[0][0],'upper_integration_limit':bounds[0][1]}],dtype=np.float32,show_progressbar=False)[...,0]
        result['raw_framework_exact']=bool(np.array_equal(raw,other));result['vendor_reconstruction_max_abs']=float(np.max(abs(raw-expected[...,0])));result['vendor_reconstruction_sum_difference']=float(raw.sum(dtype=np.float64)-expected.sum(dtype=np.float64))
        result['shape']=f['PeakData/PeakData'].shape;result['raw_shape']=f['FullSpectra/EventList'].shape;result['channel']=i;result['mass']=m;result['normalization']=norm
        t=time.perf_counter();volume=f['PeakData/PeakData'][:,:,:,i];profile=volume.mean(axis=(1,2),dtype=np.float64);front=volume.sum(axis=1,dtype=np.float64);result['full_channel_ms']=(time.perf_counter()-t)*1000;result['channel_bytes']=volume.nbytes;result['profile_sum']=float(profile.sum());result['front_shape']=front.shape
    def subset(lazy):
        t=time.perf_counter();s=file_reader(a.file,signal='nominal_peak_data',lazy=lazy,depth_range=(0,4),mz_range=(lo,hi),chunks=(1,128,128,1),show_progressbar=False)[0];data=s['data'];h=get_file_handle(data) if lazy else None
        try:array=data.compute() if lazy else data;equal=np.array_equal(array,expected)
        finally:
            if h is not None:h.close()
        return dict(lazy=lazy,exact=equal,ms=(time.perf_counter()-t)*1000,shape=array.shape)
    result['subset']=[subset(False),subset(True)]
    with ThreadPoolExecutor(2) as pool:result['concurrent_subsets']=list(pool.map(subset,[True,True]))
    result['peak_rss']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;after=a.file.stat();result['source_stat_unchanged']=(before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino)
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'acquisition.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
