"""Tests for the screen region scaling."""

import unittest

from vision.regions import reg_scale_for_station, size_scale_for_station


class RegionScalingTestCase(unittest.TestCase):
    REGION = {'rect': [0.1, 0.3, 0.9, 0.8]}

    def test_reference_resolution_keeps_the_region(self):
        scaled = reg_scale_for_station(self.REGION, 1920, 1080)

        self.assertEqual(scaled['rect'], [0.1, 0.3, 0.9, 0.8])

    def test_same_aspect_ratio_keeps_the_region(self):
        for width, height in ((2560, 1440), (3840, 2160)):
            scaled = reg_scale_for_station(self.REGION, width, height)
            self.assertEqual(scaled['rect'][0], 0.1)
            self.assertEqual(scaled['rect'][2], 0.9)
            self.assertAlmostEqual(scaled['rect'][1], 0.3)
            self.assertAlmostEqual(scaled['rect'][3], 0.8)

    def test_taller_screen_shrinks_the_region_around_the_centre(self):
        scaled = reg_scale_for_station(self.REGION, 1920, 1200)

        self.assertAlmostEqual(scaled['rect'][1], 0.5 - (0.5 - 0.3) / (1200 / 1080))
        self.assertAlmostEqual(scaled['rect'][3], 0.5 + (0.8 - 0.5) / (1200 / 1080))

    def test_size_scales_with_width_only(self):
        self.assertEqual(size_scale_for_station(100, 40, 1920, 1080), (100, 40))
        self.assertEqual(size_scale_for_station(100, 40, 3840, 2160), (200, 80))
        self.assertEqual(size_scale_for_station(100, 40, 1920, 1200), (100, 40))


if __name__ == '__main__':
    unittest.main()
