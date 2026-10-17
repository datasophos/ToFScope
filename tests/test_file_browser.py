"""Shallow listings are scoped, paginated and never inspect acquisition arrays."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from server_config import ServerSettings
from file_browser import list_data_files
from workspace import ExplorerWorkspace


class FileBrowserTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.base=Path(temp.name).resolve();self.root=self.base/'data';self.root.mkdir()
        self.settings=ServerSettings(self.root)

    def test_filter_sort_page_and_hidden_files(self):
        for name in ['z.h5','B.HDF5','a.h5','ignore.txt','.hidden.h5','a.h5.bak','backup.h5~','a.tmp.h5','a.lock.h5']:(self.root/name).touch()
        (self.root/'folder').mkdir();(self.root/'empty').mkdir()
        (self.root/'outside').symlink_to(self.base)
        page=list_data_files(self.settings,limit=2)
        self.assertEqual([e['name'] for e in page.entries],['empty','folder']);self.assertEqual(page.total,5);self.assertEqual(page.next_offset,2)
        page=list_data_files(self.settings,offset=2,limit=2)
        self.assertEqual([e['name'] for e in page.entries],['a.h5','B.HDF5'])
        self.assertEqual(list_data_files(self.settings,query='B.').entries[0]['path'],'B.HDF5')
        self.assertEqual(list_data_files(self.settings,'empty').total,0)
        self.assertEqual(list_data_files(self.settings,offset=99).entries,[])
        for kwargs in [dict(limit=0),dict(limit=201),dict(offset=-1),dict(limit=1.5),dict(offset=True)]:
            with self.assertRaises(ValueError):list_data_files(self.settings,**kwargs)
        with self.assertRaises(ValueError):list_data_files(self.settings,'outside')

    def test_thousands_never_open_hdf5(self):
        for i in range(5000):(self.root/f'{i:04}.h5').touch()
        with patch('h5py.File',side_effect=AssertionError('eager HDF5 read')):
            page=list_data_files(self.settings,offset=4000,limit=200)
        self.assertEqual(page.total,5000);self.assertEqual(len(page.entries),200);self.assertEqual(page.next_offset,4200)

    def test_permissions_and_disappearing_entries(self):
        with patch('file_browser.os.scandir',side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError):list_data_files(self.settings)
        gone=Mock();gone.name='gone.h5';gone.stat.side_effect=FileNotFoundError('gone')
        with patch('file_browser.os.scandir') as scan:
            scan.return_value.__enter__.return_value=[gone]
            self.assertEqual(list_data_files(self.settings).entries,[])

    def test_unloaded_and_failed_open_preserve_state(self):
        with patch('workspace.get_plotlyjs',return_value=''):
            w=ExplorerWorkspace(settings=self.settings);w.send=Mock()
        self.assertFalse(w.state()['loaded']);self.assertEqual(w.initial['figures'],{})
        for event,payload in [('files_list',dict(path='',request_id=8)),('files_list',dict(path='../',request_id=9)),('open',dict(path='missing.h5')),('frame',dict(frame=1)),('export',dict(format='json'))]:
            w.handle_message(None,dict(event=event,payload=payload),None)
            response=w.send.call_args.args[0]
            if event=='files_list':self.assertEqual(response['files']['request_id'],payload['request_id'])
            else:self.assertIn('error',response)
            self.assertFalse(w.state()['loaded'])

    def test_invalid_peak_metadata_does_not_replace_loaded_state(self):
        from test_signal_recipes import make_acquisition
        import h5py
        good=self.root/'good.h5';bad=self.root/'bad.h5'
        make_acquisition(good);make_acquisition(bad)
        with h5py.File(bad,'r+') as f:
            row=f['PeakData/PeakTable'][0];row['lower integration limit']=4;row['upper integration limit']=2
            f['PeakData/PeakTable'][0]=row
        with patch('workspace.get_plotlyjs',return_value=''),patch.object(ExplorerWorkspace,'figures',return_value={}):
            w=ExplorerWorkspace(good,settings=self.settings);w.send=Mock()
        before=w.volume;meta=w.meta;recipe=w.active_recipe
        w.handle_message(None,dict(event='open',payload=dict(path='bad.h5')),None)
        self.assertIn('error',w.send.call_args.args[0]);self.assertIs(w.volume,before)
        self.assertIs(w.meta,meta);self.assertIs(w.active_recipe,recipe)
