"""Numerical checks for custom mass-window reconstruction."""
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
import h5py
import numpy as np

from tofscope.storage.explorer import integrate_events, preview_grid, roi_from_bounds, sum_depth_window, se_mean


class IntegrationTests(unittest.TestCase):
    def test_parallel_se_mean_preserves_native_pixels_and_missing_coverage(self):
        from tofscope.science.se_preview import prepare_se_mean

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'se.h5'
            names = [f'Image{i:04}' for i in range(9)]
            with h5py.File(path, 'w') as f:
                for i, name in enumerate(names):
                    image = np.full((2 if i % 2 else 3, 3 if i % 3 else 2), i, dtype=float)
                    image[0, 0] = np.nan if i < 5 else i
                    f.create_dataset(f'FIBImages/{name}/Data', data=image)
            serial, serial_count = prepare_se_mean(path, names, 1, 12, workers=1)
            parallel, parallel_count = prepare_se_mean(path, names, 1, 12, workers=4)
            self.assertEqual((serial_count, parallel_count), (8, 8))
            np.testing.assert_allclose(parallel, serial, equal_nan=True)
            np.testing.assert_allclose(parallel, [[6.5, 4.5, 4.5], [4.5, 4.5, 4.5], [5., 5., 14 / 3]])
            with patch('tofscope.science.se_preview._subprocess', side_effect=OSError('worker unavailable')):
                fallback, count = prepare_se_mean(path, names, 1, 12, workers=4)
            self.assertEqual(count, 8)
            np.testing.assert_allclose(fallback, serial, equal_nan=True)

    def test_inclusive_window_empty_pixels_and_invalid_timestamps(self):
        events = np.empty((2, 2), dtype=object)
        events[0, 0] = np.array([0, 64, 128, 192, 99999], dtype=np.uint32)
        events[0, 1] = np.array([], dtype=np.uint32)
        events[1, 0] = np.array([128, 128], dtype=np.uint32)
        events[1, 1] = np.array([64], dtype=np.uint32)
        result = integrate_events(events, np.array([0., 1., 2., 3.]), 64, 2, 1, 2)
        np.testing.assert_array_equal(result, [[1., 0.], [1., .5]])

    def test_empty_slice(self):
        events = np.empty((1, 2), dtype=object)
        for pixel in np.ndindex(events.shape):
            events[pixel] = np.array([], dtype=np.uint32)
        np.testing.assert_array_equal(
            integrate_events(events, np.arange(4.), 64, 1, 1, 2), [[0., 0.]]
        )

    def test_rejects_invalid_mass_bounds(self):
        with self.assertRaises(ValueError):
            integrate_events(np.empty((0, 0), dtype=object), np.arange(4.), 64, 1, 2, 1)

    def test_preview_pools_thin_features_and_partial_blocks(self):
        data = np.zeros((5, 3, 3), dtype=np.float32)
        data[1, :, :] = 8
        data[4, :, :] = 4
        pooled, axes = preview_grid(data, (10, 14), (0, 2, 0, 2), max_depth=3, max_xy=2)
        self.assertEqual(pooled.shape, (3, 2, 2))
        np.testing.assert_array_equal(pooled[:, 0, 0], [4, 0, 4])
        np.testing.assert_array_equal(axes[0], [10.5, 12.5, 14])

    def test_drawn_region_selects_pixel_centers_and_handles_reversed_axes(self):
        self.assertEqual(roi_from_bounds([2,6,8,4], (1301,128,128), 20), (13,37,26,50))
        self.assertEqual(roi_from_bounds([0,20,0,20], (1301,128,128), 20), (0,127,0,127))

    def test_region_roundtrip_and_clipping(self):
        scale = 20/128
        self.assertEqual(roi_from_bounds([10*scale,21*scale,30*scale,41*scale], (1301,128,128), 20),
                         (10,20,30,40))
        self.assertEqual(roi_from_bounds([-10,50,-20,50], (2,4,4), None), (0,3,0,3))

    def test_depth_projection_sums_inclusive_bounds_in_original_units(self):
        data=np.array([[[1,2]],[[10,20]],[[100,200]],[[1000,2000]]],dtype=np.float32)
        np.testing.assert_array_equal(sum_depth_window(data,(10,13),(11,12)),[[110,220]])

    def test_se_mean_handles_short_final_image_without_padding_bias(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'se.h5'
            names=['Image0000','Image0001']
            with h5py.File(path,'w') as f:
                f.create_dataset('FIBImages/Image0000/Data',data=[[2.,4.],[8.,10.]])
                f.create_dataset('FIBImages/Image0001/Data',data=[[6.,8.]])
            image,count=se_mean(path,names,0,1)
            np.testing.assert_array_equal(image,[[4.,6.],[8.,10.]])
            self.assertEqual(count,2)


if __name__ == '__main__':
    unittest.main()
