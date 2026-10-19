"""All user-controlled dataset paths obey a single server-owned root."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from server_config import ServerSettings, load_server_settings, resolve_data_path
from explorer import DEFAULT_FILE
from workspace import ExplorerWorkspace
from test_signal_recipes import make_acquisition


class ServerConfigTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.base=Path(temp.name);self.root=self.base/'data';self.root.mkdir()
        self.file=self.root/'a.h5';make_acquisition(self.file)
        self.settings=ServerSettings(self.root)

    def test_default_and_explicit_startup(self):
        demo=load_server_settings({})
        expected_root=DEFAULT_FILE.parent if DEFAULT_FILE.parent.is_dir() else Path(__file__).resolve().parents[1]/'data'
        self.assertEqual(demo.data_root,expected_root.resolve())
        self.assertFalse(demo.allow_writes)
        self.assertEqual(demo.initial_file,DEFAULT_FILE.resolve() if DEFAULT_FILE.exists() else None)
        settings=load_server_settings({'TOFSCOPE_DATA_ROOT':str(self.root)})
        self.assertIsNone(settings.initial_file)
        settings=load_server_settings({'TOFSCOPE_DATA_ROOT':str(self.root),'TOF_FILE':str(self.file),'TOFSCOPE_ALLOW_WRITES':'true'})
        self.assertEqual(settings.initial_file,self.file.resolve());self.assertTrue(settings.allow_writes)
        for value in ['yes','1','maybe','']:
            with self.assertRaises(ValueError):load_server_settings({'TOFSCOPE_DATA_ROOT':str(self.root),'TOFSCOPE_ALLOW_WRITES':value})
        for env in [{'TOFSCOPE_DATA_ROOT':str(self.base/'missing')}, {'TOFSCOPE_DATA_ROOT':str(self.root),'TOF_FILE':str(self.base/'outside.h5')}]:
            with self.assertRaises(ValueError):load_server_settings(env)

    def test_paths_symlinks_and_sibling_prefix(self):
        sibling=self.base/'data-other';sibling.mkdir();(sibling/'outside.h5').touch()
        (self.root/'escape').symlink_to(sibling,target_is_directory=True)
        (self.root/'escaped.h5').symlink_to(sibling/'outside.h5')
        (self.root/'inside.h5').symlink_to(self.file)
        self.assertEqual(resolve_data_path(self.settings,'inside.h5',require_file=True),self.file.resolve())
        for path in ['../data-other/outside.h5',str(self.file),'escape/outside.h5','escaped.h5','a.h5/../a.h5','./../data-other']:
            with self.subTest(path=path),self.assertRaises(ValueError):resolve_data_path(self.settings,path)
        with self.assertRaises(ValueError):resolve_data_path(self.settings,'',require_file=True)
        with self.assertRaises(ValueError):resolve_data_path(self.settings,'missing.h5',require_file=True)

    def test_startup_without_adjacent_example_directory(self):
        with patch('server_config.DEFAULT_FILE',self.base/'missing-examples'/'example.h5'):
            settings=load_server_settings({})
        self.assertTrue(settings.data_root.is_dir())
        self.assertIsNone(settings.initial_file)
        self.assertFalse(settings.allow_writes)

    def test_controller_rejects_forged_open_and_preserves_dataset(self):
        with patch('workspace.get_plotlyjs',return_value=''),patch.object(ExplorerWorkspace,'figures',return_value={}):
            w=ExplorerWorkspace(self.file,settings=self.settings);w.send=Mock()
        before=w.volume
        self.assertEqual(w.state()['path'],'a.h5')
        for path in ['../outside.h5',str(self.file),'missing.h5']:
            w.handle_message(None,dict(event='open',payload={'path':path}),None)
            self.assertIn('error',w.send.call_args.args[0]);self.assertIs(w.volume,before)
        w.export('json')
        self.assertNotIn(str(self.root),w.send.call_args.args[0]['download']['text'])
