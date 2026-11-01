"""Calibration of the template matching scale."""

from time import sleep
from tkinter import messagebox

import cv2

from vision.screen import set_focus_elite_window


class CalibrationMixin:
    # draws the matching rectangle within the image
    #
    def draw_match_rect(self, img, pt1, pt2, color, thick):
        wid = pt2[0] - pt1[0]
        hgt = pt2[1] - pt1[1]

        if wid < 20:
            # cv2.rectangle(screen, pt, (pt[0] + compass_width, pt[1] + compass_height),  (0,0,255), 2)
            cv2.rectangle(img, pt1, pt2, color, thick)
        else:
            len_wid = wid / 5
            len_hgt = hgt / 5
            half_wid = wid / 2
            half_hgt = hgt / 2
            tic_len = thick - 1
            # top
            cv2.line(img, (int(pt1[0]), int(pt1[1])), (int(pt1[0] + len_wid), int(pt1[1])), color, thick)
            cv2.line(
                img, (int(pt1[0] + (2 * len_wid)), int(pt1[1])), (int(pt1[0] + (3 * len_wid)), int(pt1[1])), color, 1
            )
            cv2.line(img, (int(pt1[0] + (4 * len_wid)), int(pt1[1])), (int(pt2[0]), int(pt1[1])), color, thick)
            # top tic
            cv2.line(
                img,
                (int(pt1[0] + half_wid), int(pt1[1])),
                (int(pt1[0] + half_wid), int(pt1[1]) - tic_len),
                color,
                thick,
            )
            # bot
            cv2.line(img, (int(pt1[0]), int(pt2[1])), (int(pt1[0] + len_wid), int(pt2[1])), color, thick)
            cv2.line(
                img, (int(pt1[0] + (2 * len_wid)), int(pt2[1])), (int(pt1[0] + (3 * len_wid)), int(pt2[1])), color, 1
            )
            cv2.line(img, (int(pt1[0] + (4 * len_wid)), int(pt2[1])), (int(pt2[0]), int(pt2[1])), color, thick)
            # bot tic
            cv2.line(
                img,
                (int(pt1[0] + half_wid), int(pt2[1])),
                (int(pt1[0] + half_wid), int(pt2[1]) + tic_len),
                color,
                thick,
            )
            # left
            cv2.line(img, (int(pt1[0]), int(pt1[1])), (int(pt1[0]), int(pt1[1] + len_hgt)), color, thick)
            cv2.line(
                img, (int(pt1[0]), int(pt1[1] + (2 * len_hgt))), (int(pt1[0]), int(pt1[1] + (3 * len_hgt))), color, 1
            )
            cv2.line(img, (int(pt1[0]), int(pt1[1] + (4 * len_hgt))), (int(pt1[0]), int(pt2[1])), color, thick)
            # left tic
            cv2.line(
                img,
                (int(pt1[0]), int(pt1[1] + half_hgt)),
                (int(pt1[0] - tic_len), int(pt1[1] + half_hgt)),
                color,
                thick,
            )
            # right
            cv2.line(img, (int(pt2[0]), int(pt1[1])), (int(pt2[0]), int(pt1[1] + len_hgt)), color, thick)
            cv2.line(
                img, (int(pt2[0]), int(pt1[1] + (2 * len_hgt))), (int(pt2[0]), int(pt1[1] + (3 * len_hgt))), color, 1
            )
            cv2.line(img, (int(pt2[0]), int(pt1[1] + (4 * len_hgt))), (int(pt2[0]), int(pt2[1])), color, thick)
            # right tic
            cv2.line(
                img,
                (int(pt2[0]), int(pt1[1] + half_hgt)),
                (int(pt2[0] + tic_len), int(pt1[1] + half_hgt)),
                color,
                thick,
            )

    def calibrate_region(self, range_low, range_high, range_step, threshold: float, reg_name: str, templ_name: str):
        """Find the best scale value in the given range of scales with the passed in threshold
        @param reg_name:
        @param range_low:
        @param range_high:
        @param range_step:
        @param threshold: The minimum threshold to match (0.0 - 1.0)
        @param templ_name: The region name i.i 'compass' or 'target'
        @return:
        """
        scale = 0
        max_pick = 0
        i = range_low
        while i <= range_high:
            self.scr.scaleX = float(i / 100)
            self.scr.scaleY = self.scr.scaleX

            # reload the templates with this scale value
            self.templ.reload_templates(self.scr.scaleX, self.scr.scaleY, self.scr.scaleX)

            # do image matching on the compass and the target
            image, (minVal, maxVal, minLoc, maxLoc), match = self.scrReg.match_template_in_region_x3(
                reg_name, templ_name
            )

            border = 10  # border to prevent the box from interfering with future matches
            reg_pos = self.scrReg.reg[reg_name]["rect"]
            width = self.scrReg.templates.template[templ_name]["width"] + border + border
            height = self.scrReg.templates.template[templ_name]["height"] + border + border
            left = reg_pos[0] + maxLoc[0] - border
            top = reg_pos[1] + maxLoc[1] - border

            if maxVal > threshold and maxVal > max_pick:
                # Draw box around region
                self.overlay.overlay_rect(20, (left, top), (left + width, top + height), (0, 255, 0), 2)
                self.overlay.overlay_floating_text(20, f"Match: {maxVal:5.4f}", left, top - 25, (0, 255, 0))
            else:
                # Draw box around region
                self.overlay.overlay_rect(21, (left, top), (left + width, top + height), (255, 0, 0), 2)
                self.overlay.overlay_floating_text(21, f"Match: {maxVal:5.4f}", left, top - 25, (255, 0, 0))

            self.overlay.overlay_paint()

            # Check the match percentage
            if maxVal > threshold:
                if maxVal > max_pick:
                    max_pick = maxVal
                    scale = i
                    # self.ap_ckb('log', 'Cal: Found match:' + f'{max_pick:5.4f}' + "% with scale:" + f'{self.scr.scaleX:5.4f}')

            # Next range
            i = i + range_step

        # Leave the results for the user for a couple of seconds
        sleep(2)

        # Clean up screen
        self.overlay.overlay_remove_rect(20)
        self.overlay.overlay_remove_floating_text(20)
        self.overlay.overlay_remove_rect(21)
        self.overlay.overlay_remove_floating_text(21)
        self.overlay.overlay_paint()

        return scale, max_pick

    def calibrate_target(self):
        """Routine to find the optimal scaling values for the template images."""
        msg = "Select OK to begin Calibration. You must be in space and have a star system targeted in center screen."
        self.vce.say(msg)
        ans = messagebox.askokcancel("Calibration", msg)
        if not ans:
            return

        self.ap_ckb("log+vce", "Calibration starting.")

        set_focus_elite_window()

        # Draw the target and compass regions on the screen
        key = "target"
        targ_region = self.scrReg.reg[key]
        self.overlay.overlay_rect1(key, targ_region["rect"], (0, 0, 255), 2)
        self.overlay.overlay_floating_text(key, key, targ_region["rect"][0], targ_region["rect"][1], (0, 0, 255))
        self.overlay.overlay_paint()

        # Calibrate system target
        self.calibrate_target_worker()

        # Clean up
        self.overlay.overlay_clear()
        self.overlay.overlay_paint()

        self.ap_ckb("log+vce", "Calibration complete.")

    def calibrate_compass(self):
        """Routine to find the optimal scaling values for the template images."""
        msg = "Select OK to begin Calibration. You must be in space and have the compass visible."
        self.vce.say(msg)
        ans = messagebox.askokcancel("Calibration", msg)
        if not ans:
            return

        self.ap_ckb("log+vce", "Calibration starting.")

        set_focus_elite_window()

        # Draw the target and compass regions on the screen
        key = "compass"
        targ_region = self.scrReg.reg[key]
        self.overlay.overlay_rect1(key, targ_region["rect"], (0, 0, 255), 2)
        self.overlay.overlay_floating_text(key, key, targ_region["rect"][0], targ_region["rect"][1], (0, 0, 255))
        self.overlay.overlay_paint()

        # Calibrate compass
        self.calibrate_compass_worker()

        # Clean up
        self.overlay.overlay_clear()
        self.overlay.overlay_paint()

        self.ap_ckb("log+vce", "Calibration complete.")

    def calibrate_target_worker(self):
        """Calibrate target"""
        range_low = 30
        range_high = 200
        range_step = 1
        scale_max = 0
        max_val = 0

        # loop through the test twice. Once over the wide scaling range at 1% increments and once over a
        # small scaling range at 0.1% increments.
        # Find out which scale factor meets the highest threshold value.
        for i in range(2):
            threshold = 0.5  # Minimum match is constant. Result will always be the highest match.
            scale, max_pick = self.calibrate_region(range_low, range_high, range_step, threshold, "target", "target")
            if scale != 0:
                scale_max = scale
                max_val = max_pick
                range_low = scale - 5
                range_high = scale + 5
                range_step = 0.1
            else:
                break  # no match found with threshold

        # if we found a scaling factor that meets our criteria, then save it to the resolution.json file
        if max_val != 0:
            self.scr.scaleX = float(scale_max / 100)
            self.scr.scaleY = self.scr.scaleX
            self.ap_ckb("log", f"Target Cal: Best match: {max_val * 100:5.2f}% at scale: {self.scr.scaleX:5.4f}")
            self.config["TargetScale"] = round(self.scr.scaleX, 4)
            # self.scr.scales['Calibrated'] = [self.scr.scaleX, self.scr.scaleY]
            self.scr.write_config(data=None)  # None means the writer will use its own scales variable which we modified
        else:
            self.ap_ckb(
                "log", f"Target Cal: Insufficient matching to meet reliability, max % match: {max_val * 100:5.2f}%"
            )

        # reload the templates with the new (or previous value)
        self.templ.reload_templates(self.scr.scaleX, self.scr.scaleY, self.compass_scale)

    def calibrate_compass_worker(self):
        """Calibrate Compass"""
        range_low = 30
        range_high = 200
        range_step = 1
        scale_max = 0
        max_val = 0

        # loop through the test twice. Once over the wide scaling range at 1% increments and once over a
        # small scaling range at 0.1% increments.
        # Find out which scale factor meets the highest threshold value.
        for i in range(2):
            threshold = 0.5  # Minimum match is constant. Result will always be the highest match.
            scale, max_pick = self.calibrate_region(range_low, range_high, range_step, threshold, "compass", "compass")
            if scale != 0:
                scale_max = scale
                max_val = max_pick
                range_low = scale - 5
                range_high = scale + 5
                range_step = 0.1
            else:
                break  # no match found with threshold

        # if we found a scaling factor that meets our criteria, then save it to the resolution.json file
        if max_val != 0:
            c_scaleX = float(scale_max / 100)
            self.ap_ckb("log", f"Compass Cal: Max best match: {max_val * 100:5.2f}% with scale: {c_scaleX:5.4f}")
            # Keep new value
            self.compass_scale = c_scaleX

        else:
            self.ap_ckb(
                "log", f"Compass Cal: Insufficient matching to meet reliability, max % match: {max_val * 100:5.2f}%"
            )

        # reload the templates with the new (or previous value)
        self.templ.reload_templates(self.scr.scaleX, self.scr.scaleY, self.compass_scale)
