"""Detection of targets, the compass and supercruise state on screen."""

import math
import time
from math import atan, degrees
from time import sleep

import cv2
import numpy as np

from core import paths
from core.constants import (
    Flags2FsdHyperdriveCharging,
    FlagsBeingInterdicted,
    FlagsFsdCooldown,
    FlagsFsdJump,
    FlagsSupercruise,
)
from core.logger import logger
from i18n.localization import normalize_text


class DetectionMixin:
    def have_destination(self, scr_reg) -> bool:
        """Check to see if the compass is on the screen."""
        icompass_image, (minVal, maxVal, minLoc, maxLoc), template_scale = scr_reg.match_compass_multiscale()

        logger.debug(f"has_destination: score {maxVal:.3f}, compass scale {template_scale:.2f}")

        # need > x in the match to say we do have a destination
        if maxVal < scr_reg.compass_match_thresh:
            logger.info(
                f"Compass not found: score {maxVal:5.3f} (needs {scr_reg.compass_match_thresh}), "
                f"screen {scr_reg.screen.screen_width}x{scr_reg.screen.screen_height}, compass template "
                f"{scr_reg.templates.template['compass']['width']}x{scr_reg.templates.template['compass']['height']}"
            )
            return False
        else:
            return True

    def interdiction_check(self) -> bool:
        """Checks if we are being interdicted. This can occur in SC and maybe in system jump by Thargoids
        (needs to be verified). Returns False if not interdicted, True after interdiction is detected and we
        get away. Use return result to determine the next action (continue, or do something else).
        """
        # Return if we are not being interdicted.
        if not self.status.get_flag(FlagsBeingInterdicted):
            return False

        # Interdiction detected.
        self.vce.say("Danger. Interdiction detected.")
        self.ap_ckb("log", "Interdiction detected.")

        # Keep setting speed to zero to submit while in supercruise or system jump.
        while self.status.get_flag(FlagsSupercruise) or self.status.get_flag2(Flags2FsdHyperdriveCharging):
            self.keys.send("SetSpeedZero")  # Submit.
            sleep(0.5)

        # Set speed to 100%.
        self.keys.send("SetSpeed100")

        # Wait for cooldown to start.
        self.status.wait_for_flag_on(FlagsFsdCooldown)

        # Boost while waiting for cooldown to complete.
        while not self.status.wait_for_flag_off(FlagsFsdCooldown, timeout=1):
            self.keys.send("UseBoostJuice")

        # Cooldown over, get us out of here.
        self.keys.send("Supercruise")

        # Start SCO monitoring
        self.start_sco_monitoring()

        # Wait for jump to supercruise, keep boosting.
        while not self.status.get_flag(FlagsFsdJump):
            self.keys.send("UseBoostJuice")
            sleep(1)

        # Update journal flag.
        self.jn.ship_state()["interdicted"] = False  # reset flag
        return True

    @staticmethod
    def fit_compass_ring(image, approx_center, radius):
        """Fit a circle to the bright outer ring of the compass sphere near approx_center.
        Returns (x, y, radius) of the ring in image coordinates, or None if the ring is not found."""
        value = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[..., 2].astype(np.float32)
        cx, cy = approx_center
        for _ in range(4):
            x_start, y_start = max(int(cx - 70), 0), max(int(cy - 70), 0)
            sub = value[y_start : int(cy) + 71, x_start : int(cx) + 71]
            if sub.size == 0:
                return None
            ys, xs = np.mgrid[0 : sub.shape[0], 0 : sub.shape[1]]
            xs = xs + x_start
            ys = ys + y_start
            dist = np.hypot(xs - cx, ys - cy)
            band = (dist > radius * 0.82) & (dist < radius * 1.1)
            if band.sum() < 50:
                return None
            selected = band & (sub >= np.percentile(sub[band], 85))
            px = xs[selected].astype(np.float64)
            py = ys[selected].astype(np.float64)
            if len(px) < 30:
                return None
            solution = np.linalg.lstsq(np.c_[2 * px, 2 * py, np.ones_like(px)], px**2 + py**2, rcond=None)[0]
            cx, cy = float(solution[0]), float(solution[1])
        return cx, cy, float(np.sqrt(solution[2] + cx**2 + cy**2))

    @staticmethod
    def find_white_navpoint(compass_image, center, radius):
        """Find the hollow white 'target behind' marker inside the compass sphere without a template (it is not
        matched when it sits on the bright sphere rim) or the filled white 'target ahead' dot.
        Returns (x, y, hollow) in compass_image coordinates or None; a hollow ring is preferred over a filled dot."""
        hsv = cv2.cvtColor(compass_image, cv2.COLOR_BGR2HSV)
        yy, xx = np.mgrid[0 : hsv.shape[0], 0 : hsv.shape[1]]
        inside = np.hypot(xx - center[0], yy - center[1]) <= radius * 1.2
        mask = ((hsv[..., 1] < 70) & (hsv[..., 2] > 215) & inside).astype(np.uint8)
        # A bright background (ship hull, planet edge) can touch the dot and merge with it into one big blob; the
        # second pass opens the mask so thin bright lines drop away and only compact round dots remain.
        size = max(3, round(radius * 0.12) // 2 * 2 + 1)
        opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)))
        candidates = [
            DetectionMixin._best_white_blob(hsv, candidate_mask, center, radius, min_area)
            for candidate_mask, min_area in ((mask, 25), (opened, 40))
        ]
        candidates = [c for c in candidates if c is not None]
        if not candidates:
            return None
        best = max(candidates, key=lambda c: c[3])
        return best[0], best[1], best[2]

    @staticmethod
    def _best_white_blob(hsv, mask, center, radius, min_area):
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
        best = None
        for i in range(1, count):
            area = stats[i, cv2.CC_STAT_AREA]
            width, height = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            cx, cy = centroids[i]
            if not (
                min_area <= area <= 400
                and 0.6 <= width / height <= 1.6
                and math.hypot(cx - center[0], cy - center[1]) <= radius * 1.05
            ):
                continue
            # The background shows through the middle of a hollow ring, so its core is saturated
            core = hsv[round(cy) - 1 : round(cy) + 2, round(cx) - 1 : round(cx) + 2, 1]
            if not core.size:
                continue
            hollow = bool(core.mean() > 100) and area / (width * height) >= 0.35
            # A thin sliver of a bright edge with a colored fringe can look hollow too, so a ring must be compact
            rank = (hollow, area)
            if best is None or rank > best[4]:
                best = (area, float(cx), float(cy), hollow, rank)
        return None if best is None else (best[1], best[2], best[3], best[4])

    _compass_dumps = 0

    @classmethod
    def dump_compass_debug(cls, compass_image, note=""):
        """Save the compass crop when the nav point match is weak, so the case can be analysed (max. 12 files)."""
        if cls._compass_dumps >= 12:
            return
        cls._compass_dumps += 1
        name = f"compass-weak-{time.strftime('%H%M%S')}-{note}.png"
        cv2.imwrite(paths.debug_path("compass", name), compass_image)

    def get_nav_offset(self, scr_reg):
        """Determine the x,y offset from center of the compass of the nav point.
        Returns the x,y,z value as x,y in degrees (-90 to 90) and z as 1 or -1.
        {'roll': r, 'pit': p, 'yaw': y}
        Where 'roll' is:
           -180deg (6 o'clock anticlockwise) to
            0deg (12 o'clock) to
            180deg (6 o'clock clockwise)
        """

        icompass_image, (minVal, maxVal, minLoc, maxLoc), template_scale = scr_reg.match_compass_multiscale()

        pt = maxLoc

        # get wid/hgt of templates
        c_wid = round(scr_reg.templates.template["compass"]["width"] * template_scale)
        c_hgt = round(scr_reg.templates.template["compass"]["height"] * template_scale)
        # The nav point markers are drawn in the same size relation as the compass sphere, so they use its scale
        wid = round(scr_reg.templates.template["navpoint"]["width"] * template_scale)
        hgt = round(scr_reg.templates.template["navpoint"]["height"] * template_scale)
        logger.debug(f"Compass template scale {template_scale:.2f}, score {maxVal:.2f}")

        # A weak match can still sit a few pixels off the real sphere, which shifts all angles; snap to the
        # bright outer ring instead when the ring is found at about the matched size.
        if maxVal < scr_reg.compass_refine_below:
            ring = self.fit_compass_ring(icompass_image, (pt[0] + c_wid / 2, pt[1] + c_hgt / 2), c_wid / 2)
            if ring is not None and ring[2] >= c_wid / 2 - 1:
                # Use the real sphere size for the crop and the angle math
                scale = ring[2] / (c_wid / 2)
                c_wid, c_hgt = round(c_wid * scale), round(c_hgt * scale)
                pt = (max(round(ring[0] - c_wid / 2), 0), max(round(ring[1] - c_hgt / 2), 0))
                logger.debug(f"Compass sphere ring scale {scale:.2f}")

        # cut out the compass from the region
        pad = 5
        compass_image = icompass_image[
            abs(pt[1] - pad) : pt[1] + c_hgt + pad, abs(pt[0] - pad) : pt[0] + c_wid + pad
        ].copy()
        # compass_image_gray = cv2.cvtColor(compass_image, cv2.COLOR_BGR2GRAY)

        # find the nav point within the compass box
        navpt_image, (n_minVal, n_maxVal, n_minLoc, n_maxLoc), match = scr_reg.match_template_in_image_x3(
            compass_image, "navpoint", template_scale
        )
        n_pt = n_maxLoc

        compass_x_min = pad
        compass_x_max = c_wid + pad - wid
        compass_y_min = pad
        compass_y_max = c_hgt + pad - hgt

        # Bright backgrounds (sun glare) lower the score of the filled nav point, so it also counts as ahead when
        # it clearly matches better than the hollow one.
        behind_image, (_, behind_val, _, behind_loc), _ = scr_reg.match_template_in_image_x3(
            compass_image, "navpoint-behind", template_scale
        )
        ahead = n_maxVal >= scr_reg.navpoint_match_thresh or (
            n_maxVal >= scr_reg.navpoint_glare_thresh and n_maxVal > behind_val + 0.1
        )

        if ahead:
            core_x = n_maxLoc[0] + wid // 2
            core_y = n_maxLoc[1] + hgt // 2
            core = cv2.cvtColor(
                compass_image[max(core_y - 3, 0) : core_y + 4, max(core_x - 3, 0) : core_x + 4], cv2.COLOR_BGR2HSV
            )
            if core.size and core[..., 1].mean() > scr_reg.navpoint_max_core_saturation:
                ahead = False

        if not ahead:
            final_z_pct = -1.0  # Behind
            n_pt = behind_loc
        else:
            final_z_pct = 1.0  # Ahead

        logger.debug(f"Nav point scores: ahead {n_maxVal:.2f}, behind {behind_val:.2f}, ahead={ahead}")
        if max(n_maxVal, behind_val) < scr_reg.navpoint_match_thresh:
            white = self.find_white_navpoint(compass_image, (pad + c_wid / 2, pad + c_hgt / 2), c_wid / 2)
            logger.debug(f"Weak nav point match at {n_pt}, white blob: {white}")
            self.dump_compass_debug(compass_image, f"a{n_maxVal:.2f}-b{behind_val:.2f}")
            if white is not None:
                n_pt = (round(white[0] - wid / 2), round(white[1] - hgt / 2))
                final_z_pct = -1.0 if white[2] else 1.0
                logger.debug(f"Compass {'behind' if white[2] else 'ahead'} marker found without template at {n_pt}")
            else:
                logger.debug("Compass nav point not found, template position is unreliable")

        # Continue calc
        final_x_pct = 2 * (
            ((n_pt[0] - compass_x_min) / (compass_x_max - compass_x_min)) - 0.5
        )  # X as percent (-1.0 to 1.0, 0.0 in the center)
        final_x_pct = max(min(final_x_pct, 1.0), -1.0)

        final_y_pct = -2 * (
            ((n_pt[1] - compass_y_min) / (compass_y_max - compass_y_min)) - 0.5
        )  # Y as percent (-1.0 to 1.0, 0.0 in the center)
        final_y_pct = max(min(final_y_pct, 1.0), -1.0)

        # Calc angle in degrees starting at 0 deg at 12 o'clock and increasing clockwise
        # so 3 o'clock is +90° and 9 o'clock is -90°.
        final_roll_deg = 0.0
        if final_x_pct > 0.0:
            final_roll_deg = 90 - degrees(atan(final_y_pct / final_x_pct))
        elif final_x_pct < 0.0:
            final_roll_deg = -90 - degrees(atan(final_y_pct / final_x_pct))

        # 'longitudinal' radius of compass at given 'latitude'
        lng_rad_at_lat = math.cos(math.asin(final_y_pct))
        lng_rad_at_lat = max(lng_rad_at_lat, 0.001)  # Prevent div by zero

        # 'Latitudinal' radius of compass at given 'longitude'
        lat_rad_at_lng = math.sin(math.acos(final_x_pct))
        lat_rad_at_lng = max(lat_rad_at_lng, 0.001)  # Prevent div by zero

        # Pitch and yaw as a % of the max as defined by the compass circle
        pit_pct = max(min(final_y_pct / lat_rad_at_lng, 1.0), -1.0)
        yaw_pct = max(min(final_x_pct / lng_rad_at_lat, 1.0), -1.0)

        if final_z_pct > 0:
            final_pit_deg = (-1 * degrees(math.acos(pit_pct))) + 90  # Y in deg (-90.0 to 90.0, 0.0 in the center)
            final_yaw_deg = (-1 * degrees(math.acos(yaw_pct))) + 90  # X in deg (-90.0 to 90.0, 0.0 in the center)
        else:
            if final_y_pct > 0:
                final_pit_deg = degrees(math.acos(pit_pct)) + 90  # Y in deg (-90.0 to 90.0, 0.0 in the center)
            else:
                final_pit_deg = degrees(math.acos(pit_pct)) - 270  # Y in deg (-90.0 to 90.0, 0.0 in the center)

            if final_x_pct > 0:
                final_yaw_deg = degrees(math.acos(yaw_pct)) + 90  # X in deg (-90.0 to 90.0, 0.0 in the center)
            else:
                final_yaw_deg = degrees(math.acos(yaw_pct)) - 270  # X in deg (-90.0 to 90.0, 0.0 in the center)

        result = {
            "x": round(final_x_pct, 2),
            "y": round(final_y_pct, 2),
            "z": round(final_z_pct, 2),
            "roll": round(final_roll_deg, 2),
            "pit": round(final_pit_deg, 2),
            "yaw": round(final_yaw_deg, 2),
        }

        if self.cv_view:
            # icompass_image_d = cv2.cvtColor(compass_image_gray, cv2.COLOR_GRAY2RGB)
            icompass_image_d = icompass_image
            self.draw_match_rect(icompass_image_d, pt, (pt[0] + c_wid, pt[1] + c_hgt), (0, 0, 255), 2)
            # cv2.rectangle(icompass_image_display, pt, (pt[0]+c_wid, pt[1]+c_hgt), (0, 0, 255), 2)
            # self.draw_match_rect(compass_image, n_pt, (n_pt[0] + wid, n_pt[1] + hgt), (255,255,255), 2)
            self.draw_match_rect(
                icompass_image_d,
                (pt[0] + n_pt[0] - pad, pt[1] + n_pt[1] - pad),
                (pt[0] + n_pt[0] + wid - pad, pt[1] + n_pt[1] + hgt - pad),
                (0, 255, 0),
                1,
            )
            # cv2.rectangle(icompass_image_display, (pt[0]+n_pt[0]-pad, pt[1]+n_pt[1]-pad), (pt[0]+n_pt[0] + wid-pad, pt[1]+n_pt[1] + hgt-pad), (0, 0, 255), 2)

            #   dim = (int(destination_width/3), int(destination_height/3))

            #   img = cv2.resize(dst_image, dim, interpolation =cv2.INTER_AREA)
            icompass_image_d = cv2.rectangle(icompass_image_d, (0, 0), (1000, 60), (0, 0, 0), -1)
            cv2.putText(
                icompass_image_d,
                f"Compass: {maxVal:5.4f} > {scr_reg.compass_match_thresh:5.2f}",
                (1, 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                icompass_image_d,
                f"Nav Point: {n_maxVal:5.4f} > {scr_reg.navpoint_match_thresh:5.2f}",
                (1, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            # cv2.putText(icompass_image_d, f'Result: {result}', (1, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(
                icompass_image_d,
                f"x: {final_x_pct:5.2f} y: {final_y_pct:5.2f} z: {final_z_pct:5.2f}",
                (1, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                icompass_image_d,
                f"r: {final_roll_deg:5.2f}deg p: {final_pit_deg:5.2f}deg y: {final_yaw_deg:5.2f}deg",
                (1, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.imshow("compass", icompass_image_d)
            cv2.moveWindow("compass", self.cv_view_x - 400, self.cv_view_y + 600)
            cv2.waitKey(30)

        return result

    def is_destination_occluded(self, scr_reg) -> bool:
        """Looks to see if the 'dashed' line of the target is present indicating the target
        is occluded by the planet.
        @param scr_reg: The screen region to check.
        @return: True if target occluded (meets threshold), else False.
        """
        dst_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region(
            "target_occluded", "target_occluded", inv_col=False
        )

        pt = maxLoc

        if self.cv_view:
            dst_image_d = cv2.cvtColor(dst_image, cv2.COLOR_GRAY2RGB)
            destination_width = scr_reg.reg["target"]["width"]
            destination_height = scr_reg.reg["target"]["height"]

            width = scr_reg.templates.template["target_occluded"]["width"]
            height = scr_reg.templates.template["target_occluded"]["height"]
            try:
                self.draw_match_rect(dst_image_d, pt, (pt[0] + width, pt[1] + height), (0, 0, 255), 2)
                dim = (int(destination_width / 2), int(destination_height / 2))

                img = cv2.resize(dst_image_d, dim, interpolation=cv2.INTER_AREA)
                img = cv2.rectangle(img, (0, 0), (1000, 25), (0, 0, 0), -1)
                cv2.putText(
                    img,
                    f"{maxVal:5.4f} > {scr_reg.target_occluded_thresh:5.2f}",
                    (1, 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                cv2.imshow("occluded", img)
                cv2.moveWindow("occluded", self.cv_view_x, self.cv_view_y + 650)
            except Exception as e:
                logger.error(f"Exception in debug view (occluded): {e}")
            cv2.waitKey(30)

        if maxVal > scr_reg.target_occluded_thresh:
            logger.debug(f"Target is occluded ({maxVal:5.4f} > {scr_reg.target_occluded_thresh:5.2f})")
            return True

        _, (_, tan_val, _, _), _ = scr_reg.match_template_in_region(
            "target_occluded_tan", "target_occluded", inv_col=False
        )
        if tan_val > scr_reg.target_occluded_tan_thresh:
            logger.debug(f"Target is occluded, beige ring ({tan_val:5.4f} > {scr_reg.target_occluded_tan_thresh:5.2f})")
            return True
        logger.debug(f"Occluded ring scores: white {maxVal:5.4f}, beige {tan_val:5.4f}")

        return self.is_destination_hidden_ahead(scr_reg)

    def is_destination_hidden_ahead(self, scr_reg) -> bool:
        """Additional occlusion checks for when the dashed circle cannot be seen: the nav point is ahead, but the
        target circle is not shown. This is the case when the target is behind a planet in front of a very
        bright sun, or while the game shows the 'move to obtain line of sight' message (Supercruise Assist).
        @return: True if the target is occluded."""
        _, (_, target_val, _, _), _ = scr_reg.match_template_in_region("target", "target", inv_col=False)
        if target_val >= scr_reg.target_thresh:
            return False  # target circle is visible

        if not self.have_destination(scr_reg) or self.get_nav_offset(scr_reg)["z"] < 0:
            return False  # no nav point, or it is behind us

        if scr_reg.scene_is_bright():
            logger.debug("Target is occluded (nav point ahead, no target circle, bright scene)")
            return True

        if self.line_of_sight_message(scr_reg):
            logger.debug("Target is occluded (line of sight message)")
            return True

        return False

    def message_similarity(self, key: str, textlist) -> float:
        """Best similarity of the OCR text to the message in any available language, so detection does not
        depend on the configured program language."""
        text = normalize_text(" ".join(textlist))
        return max(self.ocr.string_similarity(normalize_text(msg), text) for msg in self.locale.all_values(key))

    def line_of_sight_message(self, scr_reg) -> bool:
        """Look for the 'move to obtain line of sight to target' message using OCR. The game only shows it
        when Supercruise Assist is active, so not seeing it says nothing."""
        image = scr_reg.screen.get_screen_region(scr_reg.reg["line_of_sight"]["rect"], rgb=False)[:, :, :3]
        ocr_textlist = self.ocr.image_simple_ocr(image)
        if not ocr_textlist:
            return False

        sim = self.message_similarity("LINE_OF_SIGHT_MSG", ocr_textlist)
        logger.debug(f"Line of sight similarity with {ocr_textlist} is {sim}")
        return sim >= 0.5

    def fsd_alignment_prompt(self, scr_reg) -> bool:
        """Check whether the FSD asks for better target alignment."""
        image = scr_reg.screen.get_screen_region(scr_reg.reg["fsd_align"]["rect"], rgb=False)[:, :, :3]
        ocr_textlist = self.ocr.image_simple_ocr(image)
        if not ocr_textlist:
            logger.debug("FSD alignment prompt OCR returned no text.")
            return False

        sim = self.message_similarity("ALIGN_WITH_TARGET_MSG", ocr_textlist)
        logger.debug(f"FSD alignment prompt OCR text={ocr_textlist}, similarity={sim:.3f}.")
        return sim >= 0.5

    def get_destination_offset(self, scr_reg):
        """Determine how far off we are from the target being in the middle of the screen
        (in this case the specified region)."""
        dst_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region(
            "target", "target", inv_col=False
        )
        roi_height, roi_width = dst_image.shape[:2]
        filter_pixels = cv2.countNonZero(dst_image)
        roi_pixels = roi_width * roi_height

        pt = maxLoc

        destination_width = scr_reg.reg["target"]["width"]
        destination_height = scr_reg.reg["target"]["height"]

        width = scr_reg.templates.template["target"]["width"]
        height = scr_reg.templates.template["target"]["height"]

        # The target is aligned when the center of its circle is at the center of the screen. The template is only
        # an arc, so use the circle center (anchor) instead of the center of the template.
        anchor_x, anchor_y = scr_reg.templates.template["target"]["anchor"]
        region_left, region_top = scr_reg.reg["target"]["rect"][:2]
        final_x = (pt[0] + anchor_x) - (scr_reg.screen.screen_width / 2 - region_left)
        final_y = (scr_reg.screen.screen_height / 2 - region_top) - (pt[1] + anchor_y)

        #  print("get dest, final:" + str(final_x)+ " "+str(final_y))
        #  print(destination_width, destination_height, width, height)
        #  print(maxLoc)

        if self.cv_view:
            dst_image_d = cv2.cvtColor(dst_image, cv2.COLOR_GRAY2RGB)
            try:
                self.draw_match_rect(dst_image_d, pt, (pt[0] + width, pt[1] + height), (0, 0, 255), 2)
                dim = (int(destination_width / 2), int(destination_height / 2))

                img = cv2.resize(dst_image_d, dim, interpolation=cv2.INTER_AREA)
                img = cv2.rectangle(img, (0, 0), (1000, 25), (0, 0, 0), -1)
                cv2.putText(
                    img,
                    f"{maxVal:5.4f} > {scr_reg.target_thresh:5.2f}",
                    (1, 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                cv2.imshow("target", img)
                # cv2.imshow('tt', scr_reg.templates.template['target']['image'])
                cv2.moveWindow("target", self.cv_view_x, self.cv_view_y + 425)
            except Exception as e:
                logger.error(f"Exception in debug view (target): {e}")
            cv2.waitKey(30)

        # print (maxVal)
        # must be > x to have solid hit, otherwise we are facing wrong way (empty circle)
        diagnostics = (
            f"roi={roi_width}x{roi_height}, filter_pixels={filter_pixels}/{roi_pixels} "
            f"({filter_pixels / roi_pixels:.2%}), template={width}x{height}, "
            f"score={maxVal:.4f}, threshold={scr_reg.target_thresh:.2f}"
        )
        if maxVal < scr_reg.target_thresh:
            result = None
            logger.debug(f"Target detection: {diagnostics} (below threshold)")
        else:
            result = {"x": final_x, "y": final_y}
            logger.debug(f"Target detection: {diagnostics}, offset x={final_x:.1f}, y={final_y:.1f}")

        return result

    def sc_disengage_label_up(self, scr_reg) -> bool:
        """look for messages like "PRESS [Y] TO DISENGAGE" or "SUPERCRUISE OVERCHARGE ACTIVE",
         if in this region then return true.
        The aim of this function is to return that a message is there, and then use OCR to determine
        what the message is. This will only use the high CPU usage OCR when necessary.
        The check only looks for message text colored pixels, so it does not depend on the game language."""
        text_present = scr_reg.message_text_present("disengage")

        # Heartbeat every 5 s, so the log shows that the check runs and how much message-colored area it sees
        now = time.monotonic()
        if now - getattr(self, "_message_log_time", 0.0) >= 5.0:
            self._message_log_time = now
            fraction = getattr(scr_reg, "last_message_fraction", 0.0)
            line = getattr(scr_reg, "last_message_line", 0.0)
            logger.info(
                f"Disengage message check: message-colored area {fraction:.3f} (needs {scr_reg.message_text_fraction}), "
                f"longest line {line:.2f} (needs {scr_reg.message_line_fraction})"
            )

        # Log only when a message appears, so the log shows whether the detection saw it
        if text_present != getattr(self, "_message_was_present", False):
            self._message_was_present = text_present
            if text_present:
                logger.info("HUD message text detected in the disengage region, reading it with OCR.")
        if self.cv_view:
            dis_image = scr_reg.message_image("disengage")
            dis_image = cv2.rectangle(dis_image, (0, 0), (1000, 25), (0, 0, 0), -1)
            cv2.putText(
                dis_image,
                f"Message text: {text_present}",
                (1, 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.imshow("sc_disengage_label_up", dis_image)
            cv2.moveWindow("sc_disengage_label_up", self.cv_view_x - 460, self.cv_view_y + 575)
            cv2.waitKey(1)

        return text_present

    def sc_disengage_active(self, scr_reg) -> bool:
        """look for the "PRESS [Y] TO DISENGAGE" text using OCR, if in this region then return true."""
        # OCR the selected item. The raw images are a fallback for messages partly covered by the cockpit frame,
        # the plain raw image is tried before the slower enlarged one.
        sim_match = 0.35  # Similarity match 0.0 - 1.0 for 0% - 100%)
        sim = 0.0
        ocr_textlist = None
        for variant in ({}, {"raw": True}, {"raw": True, "upscale": 2}):
            image = scr_reg.message_image("disengage", **variant)
            textlist = self.ocr.image_simple_ocr(image)
            if textlist is None:
                logger.info(f"Disengage OCR returned no text ({variant or 'masked'}).")
                continue
            variant_sim = self.message_similarity("PRESS_TO_DISENGAGE_MSG", textlist)
            logger.info(f"Disengage similarity with {str(textlist)} is {variant_sim} ({variant or 'masked'})")
            if variant_sim > sim or ocr_textlist is None:
                sim, ocr_textlist = variant_sim, textlist
            if sim > sim_match:
                break
        # Draw box around region
        if self.debug_overlay:
            abs_rect = scr_reg.reg["disengage"]["rect"]
            self.overlay.overlay_rect1("sc_disengage_active", abs_rect, (0, 255, 0), 2)
            self.overlay.overlay_floating_text(
                "sc_disengage_active", f"{str(ocr_textlist)}", abs_rect[0], abs_rect[1] - 25, (0, 255, 0)
            )
            self.overlay.overlay_paint()

        if self.cv_view:
            image = cv2.rectangle(image, (0, 0), (1000, 30), (0, 0, 0), -1)
            cv2.putText(
                image,
                f"Text: {str(ocr_textlist)}",
                (1, 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                image,
                f"Similarity: {sim:5.4f} > {sim_match}",
                (1, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.imshow("disengage2", image)
            cv2.moveWindow("disengage2", self.cv_view_x - 460, self.cv_view_y + 650)
            cv2.waitKey(30)

        if sim > sim_match:
            logger.info("Disengage message detected, sending the supercruise exit.")
            # cv2.imwrite(paths.debug_path('disengage.png'), image)
            return True

        return False

    def is_sun_dead_ahead(self, scr_reg):
        return scr_reg.sun_percent(scr_reg.screen) > 5
