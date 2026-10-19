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
