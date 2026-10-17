"""Prepare a disposable native-copy artifact for commercial validation.

The supplied acquisition is only read. The output must be a new path.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import h5py
import numpy as np
from explorer import DEFAULT_FILE,inspect_file
from signals import SignalRecipe,read_signal
from vendor_export import export_native_copy


def digest(path):
    result=hashlib.sha256()
    with open(path,'rb') as stream:
        for chunk in iter(lambda:stream.read(8*2**20),b''):result.update(chunk)
    return result.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',default=str(DEFAULT_FILE));parser.add_argument('--output',default='/private/tmp/tofscope-native-validation.h5')
    args=parser.parse_args();source=Path(args.source);output=Path(args.output)
    if output.exists():raise FileExistsError(output)
    started=time.monotonic();before=digest(source);meta=inspect_file(source)
    recipe=SignalRecipe(intervals=((26.8,27.2),),frames=(0,meta['shape'][0]-1),label='ToFScope_Al_26p8_27p2')
    values=read_signal(source,recipe,lambda done,total:print(f'Integrating {done}/{total}',flush=True) if done%100==0 or done==total else None)
    export_native_copy(source,output,[recipe],volumes=[values],progress=lambda label,done,total:print(f'{label}: {done}/{total}',flush=True))
    with h5py.File(source,'r') as original,h5py.File(output,'r') as saved:
        old=original['PeakData/PeakData'];new=saved['PeakData/PeakData']
        if old.chunks and old.chunks[-1]==1:
            for selection in old.iter_chunks():
                offset=tuple(part.start for part in selection)
                if old.id.get_chunk_info_by_coord(offset).size==0:continue
                assert old.id.read_direct_chunk(offset)==new.id.read_direct_chunk(offset)
        else:
            for z in range(old.shape[0]):np.testing.assert_array_equal(old[z],new[z,:,:,:old.shape[-1]])
        np.testing.assert_array_equal(new[:,:,:,-1],values)
    from rsciio.tofwerk import file_reader
    signals=file_reader(output,signal='additional_peak_data',lazy=True,show_progressbar=False)
    signal=signals[0];mass_axis=np.asarray(signal['axes'][-1]['axis']);index=int(np.argmin(abs(mass_axis-27)))
    np.testing.assert_array_equal(signal['data'][...,index].compute(),values)
    assert digest(source)==before,'Source acquisition changed'
    report=dict(source=str(source),output=str(output),source_sha256=before,recipe=recipe.to_dict(),
                official_reader='RosettaSciIO9959c5679',reader_round_trip=True,source_unchanged=True,seconds=round(time.monotonic()-started,2),commercial_validation='pending')
    report_path=output.with_suffix('.json');report_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
