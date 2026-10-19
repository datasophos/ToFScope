from pathlib import Path
import tempfile
from fixtures.acquisition import make_acquisition
from tofscope.config import Settings
from tofscope.storage.acquisitions import AcquisitionRepository

def setup_case(case,**limits):
    temp=tempfile.TemporaryDirectory();case.addCleanup(temp.cleanup);root=Path(temp.name);make_acquisition(root/'a.h5');make_acquisition(root/'b.h5')
    case.settings=Settings(root,runtime_dir=root/'runtime',**limits);case.repo=AcquisitionRepository(case.settings);case.dataset=case.repo.open('a','a.h5')
