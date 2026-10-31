import h5py
import numpy as np

def make_acquisition(path):
    with h5py.File(path,'w') as f:
        f.attrs['TofDAQ Version']='1.0'
        f.attrs['NbrWrites']=4;f.attrs['NbrSegments']=1
        f.create_group('TimingData');f.create_group('AcquisitionLog')
        f.attrs['NbrWaveforms']=2
        f.attrs['Configuration File Contents']=b'Ch1Record=1\nCh2Record=1'
        fs=f.create_group('FullSpectra');fs.attrs['SampleInterval']=64.;fs.attrs['ClockPeriod']=1.
        fs.create_dataset('MassAxis',data=np.arange(6.));fs.create_dataset('SumSpectrum',data=np.array([1.,1.,1.,1.,2.,2.]))
        raw=fs.create_dataset('EventList',(4,1,2),dtype=h5py.vlen_dtype(np.dtype('uint32')))
        for z in range(4):
            raw[z,0,0]=np.array([1,2,2,3,4],dtype=np.uint32)*64
            raw[z,0,1]=np.array([1]*z+[3,5],dtype=np.uint32)*64
        peak=f.create_group('PeakData')
        peak.create_dataset('PeakData',data=np.stack([np.arange(6,dtype=np.float32).reshape(3,1,2),10+np.arange(6,dtype=np.float32).reshape(3,1,2)],axis=-1))
        dtype=np.dtype([('label','S64'),('mass','f4'),('lower integration limit','f4'),('upper integration limit','f4')])
        peak.create_dataset('PeakTable',data=np.array([(b'nominal 2',2.,1.,3.),(b'nominal 4',4.,3.,5.)],dtype=dtype))

        f.create_group("FIBParams").attrs["ViewField"]=.02
        f.create_dataset("FIBImages/Image0000/Data",data=[[2.,4.],[8.,10.]])
        f.create_dataset("FIBImages/Image0001/Data",data=[[6.,8.]])


def make_spatial_acquisition(path):
    """Small registered six-signal fixture with nonuniform physical-depth anchors."""
    make_acquisition(path)
    with h5py.File(path,'r+') as f:
        del f['PeakData/PeakData']
        values=np.arange(7*4*4,dtype=np.float32).reshape(7,4,4)
        channels=np.stack([values*(i+1) for i in range(6)],axis=-1)
        channels[0,0,0,0]=np.nan  # A genuine missing sample, never a zero.
        f.create_dataset('PeakData/PeakData',data=channels)
        dtype=f['PeakData/PeakTable'].dtype
        del f['PeakData/PeakTable']
        f.create_dataset('PeakData/PeakTable',data=np.array([(f'Ion {i}'.encode(),float(i+1),float(i),float(i+1)) for i in range(6)],dtype=dtype))
        f.attrs['NbrWrites']=8
