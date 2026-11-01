"""Tests for template matching and the screen detection on real screenshot crops.

The crops in tests/fixtures were captured at the 3440x1440 reference resolution, so the templates are
loaded unscaled. A fake screen returns the crop for every region, which exercises the real region
filters, templates, thresholds and offset calculations without the game or a monitor.
"""

import unittest

import cv2
import numpy as np

from tests.helpers import FakeScreen, load_fixture_image
from vision.detection import DetectionMixin
from vision.regions import Screen_Regions
from vision.templates import Image_Templates


class Detector(DetectionMixin):
    cv_view = False


class MatchingTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = Image_Templates(1.0, 1.0, 1.0)
        cls.images = {name: load_fixture_image(name) for name in
                      ('compass', 'navpoint', 'navpoint-behind', 'target', 'disengage')}
        cls.images['empty'] = np.zeros((700, 700, 3), np.uint8)

    def regions(self, image_name):
        return Screen_Regions(FakeScreen(self.images[image_name]), self.templates)

    def detect(self, method, image_name):
        return getattr(Detector(), method)(self.regions(image_name))


class TemplateTestCase(MatchingTestCase):
    def test_all_templates_are_loaded(self):
        for name, template in self.templates.template.items():
            with self.subTest(template=name):
                self.assertIsNotNone(template['image'])
                self.assertEqual(template['image'].shape[::-1], (template['width'], template['height']))

    def test_templates_are_scaled(self):
        half = Image_Templates(0.5, 0.5, 0.5)

        for name in ('compass', 'navpoint', 'target', 'disengage'):
            with self.subTest(template=name):
                self.assertAlmostEqual(half.template[name]['width'], self.templates.template[name]['width'] / 2, delta=1)
                self.assertAlmostEqual(half.template[name]['height'], self.templates.template[name]['height'] / 2, delta=1)

    def test_template_is_found_at_its_position(self):
        regions = self.regions('empty')
        for name in ('compass', 'target', 'disengage', 'navpoint'):
            with self.subTest(template=name):
                template = self.templates.template[name]['image']
                canvas = np.zeros((300, 400), np.uint8)
                canvas[40:40 + template.shape[0], 25:25 + template.shape[1]] = template

                _, (_, max_val, _, max_loc), _ = regions.match_template_in_image(canvas, name)

                self.assertGreater(max_val, 0.99)
                self.assertEqual(max_loc, (25, 40))

    def test_x3_matching_finds_the_template_in_a_colour_image(self):
        regions = self.regions('empty')
        template = self.templates.template['compass']['image']
        canvas = np.zeros((300, 400, 3), np.uint8)
        canvas[60:60 + template.shape[0], 90:90 + template.shape[1]] = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)

        _, (_, max_val, _, max_loc), _ = regions.match_template_in_image_x3(canvas, 'compass')

        self.assertGreater(max_val, 0.99)
        self.assertEqual(max_loc, (90, 60))


class CompassTestCase(MatchingTestCase):
    def test_compass_is_found(self):
        for name in ('compass', 'navpoint', 'navpoint-behind'):
            with self.subTest(image=name):
                self.assertTrue(self.detect('have_destination', name))

    def test_no_compass_in_other_screens(self):
        for name in ('empty', 'target', 'disengage'):
            with self.subTest(image=name):
                self.assertFalse(self.detect('have_destination', name))

    def test_nav_point_at_the_bottom_is_behind(self):
        offset = self.detect('get_nav_offset', 'compass')

        self.assertEqual(offset['z'], -1.0)
        self.assertAlmostEqual(offset['x'], -0.1, delta=0.1)
        self.assertLess(offset['y'], -0.8)
        self.assertLess(offset['roll'], -150)

    def test_nav_point_on_the_right_is_behind(self):
        offset = self.detect('get_nav_offset', 'navpoint')

        self.assertEqual(offset['z'], -1.0)
        self.assertGreater(offset['x'], 0.8)
        self.assertAlmostEqual(offset['y'], -0.25, delta=0.15)
        self.assertGreater(offset['roll'], 90)
        self.assertGreater(offset['yaw'], 90)

    def test_nav_point_at_the_top_is_behind(self):
        offset = self.detect('get_nav_offset', 'navpoint-behind')

        self.assertEqual(offset['z'], -1.0)
        self.assertAlmostEqual(offset['x'], -0.07, delta=0.1)
        self.assertGreater(offset['y'], 0.5)
        self.assertAlmostEqual(offset['roll'], 0, delta=15)

    def test_offset_values_stay_within_range(self):
        for name in ('compass', 'navpoint', 'navpoint-behind', 'target'):
            with self.subTest(image=name):
                offset = self.detect('get_nav_offset', name)
                self.assertTrue(-1.0 <= offset['x'] <= 1.0)
                self.assertTrue(-1.0 <= offset['y'] <= 1.0)
                self.assertTrue(-180 <= offset['roll'] <= 180)


class TargetTestCase(MatchingTestCase):
    def test_target_circle_is_found_and_offset_to_the_left(self):
        offset = self.detect('get_destination_offset', 'target')

        self.assertIsNotNone(offset)
        self.assertAlmostEqual(offset['x'], -284.5, delta=5)
        self.assertAlmostEqual(offset['y'], 22.0, delta=5)

    def test_no_target_in_other_screens(self):
        for name in ('empty', 'compass', 'disengage'):
            with self.subTest(image=name):
                self.assertIsNone(self.detect('get_destination_offset', name))

    def test_target_is_not_occluded(self):
        for name in ('empty', 'target', 'disengage'):
            with self.subTest(image=name):
                self.assertFalse(self.detect('is_destination_occluded', name))

    def test_occluded_template_is_recognised(self):
        template = self.templates.template['target_occluded']['image']
        image = np.zeros((700, 700, 3), np.uint8)
        # The region filter keeps only pixels within the occluded colour range, so draw the template in that colour.
        mask = template > 128
        image[:template.shape[0], :template.shape[1]][mask] = cv2.cvtColor(
            np.uint8([[[20, 120, 180]]]), cv2.COLOR_HSV2BGR)[0, 0]
        regions = Screen_Regions(FakeScreen(image), self.templates)

        self.assertTrue(Detector().is_destination_occluded(regions))


class DisengageTestCase(MatchingTestCase):
    def test_disengage_message_is_recognised(self):
        regions = self.regions('disengage')

        _, (_, max_val, _, _), _ = regions.match_template_in_region('disengage', 'disengage')

        self.assertGreater(max_val, regions.disengage_thresh)
        self.assertTrue(Detector().sc_disengage_label_up(regions))

    def test_empty_screen_has_no_message(self):
        self.assertFalse(self.detect('sc_disengage_label_up', 'empty'))


class RegionFilterTestCase(MatchingTestCase):
    def test_region_rects_follow_the_screen_size(self):
        regions = Screen_Regions(FakeScreen(None, 1920, 1080), self.templates)

        compass = regions.reg['compass']
        self.assertEqual(compass['rect'], [633, 702, 883, 1080])
        self.assertEqual((compass['width'], compass['height']), (250, 378))

    def test_all_regions_lie_inside_the_screen(self):
        for width, height in ((1920, 1080), (3440, 1440), (2560, 1440)):
            regions = Screen_Regions(FakeScreen(None, width, height), self.templates)
            for name, region in regions.reg.items():
                with self.subTest(resolution=f'{width}x{height}', region=name):
                    left, top, right, bottom = region['rect']
                    self.assertTrue(0 <= left < right <= width)
                    self.assertTrue(0 <= top < bottom <= height)

    def test_equalize_returns_a_grey_image(self):
        result = self.regions('compass').equalize(self.images['compass'])

        self.assertEqual(result.shape, self.images['compass'].shape[:2])

    def test_filter_by_color_keeps_only_pixels_in_range(self):
        regions = self.regions('empty')
        orange = cv2.cvtColor(np.uint8([[[10, 200, 180]]]), cv2.COLOR_HSV2BGR)[0, 0]
        image = np.zeros((10, 10, 3), np.uint8)
        image[:, :5] = orange
        image[:, 5:] = (255, 0, 0)

        mask = regions.filter_by_color(image, regions.orange_color_range)

        self.assertTrue((mask[:, :5] == 255).all())
        self.assertTrue((mask[:, 5:] == 0).all())

    def test_sun_filter_uses_the_threshold(self):
        regions = self.regions('empty')
        image = np.full((4, 4, 3), 100, np.uint8)

        regions.set_sun_threshold(125)
        self.assertEqual(regions.filter_sun(image).sum(), 0)
        regions.set_sun_threshold(50)
        self.assertTrue((regions.filter_sun(image) == 255).all())

    def test_sun_percent(self):
        image = np.zeros((100, 100, 3), np.uint8)
        image[:, :50] = 255
        regions = Screen_Regions(FakeScreen(image), self.templates)

        self.assertEqual(regions.sun_percent(regions.screen), 50)


if __name__ == '__main__':
    unittest.main()
