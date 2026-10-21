import unittest
from service_fixture import setup_case
from tofscope.config import Settings


class ConfigTests(unittest.TestCase):
    def test_signal_quotas(self):
        setup_case(self)
        self.assertEqual((self.settings.signals_per_analysis, self.settings.signals_per_user, self.settings.signals_global), (129, 512, 2048))
        for field in ('signals_per_analysis', 'signals_per_user', 'signals_global'):
            with self.assertRaises(ValueError):
                Settings(self.settings.data_root, **{field: 0})

    def test_folder_defaults_follow_working_directory_and_effective_data_root(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from tofscope.config import load_settings
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch('pathlib.Path.cwd', return_value=root):
                settings = load_settings(env={}, cli={'runtime_dir': root / 'runtime'})
                self.assertEqual(settings.data_root, root)
                self.assertEqual(settings.output_root, root)
                self.assertEqual(Settings(runtime_dir=root / 'runtime').data_root, root)
            source = root / 'acquisitions'; source.mkdir()
            settings = load_settings(env={'TOFSCOPE_DATA_ROOT': str(source)}, cli={'runtime_dir': root / 'runtime'})
            self.assertEqual(settings.output_root, source)
            output = root / 'copies'
            settings = load_settings(env={'TOFSCOPE_DATA_ROOT': str(source), 'TOFSCOPE_OUTPUT_ROOT': str(output)}, cli={'runtime_dir': root / 'runtime'})
            self.assertEqual(settings.output_root, output)
