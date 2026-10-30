import unittest
from tofscope.cli import asset_status
from tofscope.science.isotopes import load_catalog


class DistributionTests(unittest.TestCase):
    def test_bundled_assets_and_reference(self):
        self.assertEqual(asset_status()["version"], "0.1.0")
        self.assertTrue(load_catalog())
