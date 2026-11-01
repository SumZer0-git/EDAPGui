"""Detection of targets, the compass and supercruise state on screen."""

import math
from math import atan, degrees
from time import sleep

import cv2

from core.constants import (
    Flags2FsdHyperdriveCharging,
    FlagsBeingInterdicted,
    FlagsFsdCooldown,
    FlagsFsdJump,
    FlagsSupercruise,
)
from core.logger import logger


class DetectionMixin:
    def have_destination(self, scr_reg) -> bool:
        """Check to see if the compass is on the screen."""
        icompass_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region_x3(
            "compass", "compass"
        )

        logger.debug("has_destination:" + str(maxVal))

        # need > x in the match to say we do have a destination
        if maxVal < scr_reg.compass_match_thresh:
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

    def get_nav_offset(self, scr_reg):
        """Determine the x,y offset from center of the compass of the nav point.
        Returns the x,y,z value as x,y in degrees (-90 to 90) and z as 1 or -1.
        {'roll': r, 'pit': p, 'yaw': y}
        Where 'roll' is:
           -180deg (6 o'clock anticlockwise) to
            0deg (12 o'clock) to
            180deg (6 o'clock clockwise)
        """

        icompass_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region_x3(
            "compass", "compass"
        )

        pt = maxLoc

        # get wid/hgt of templates
        c_wid = scr_reg.templates.template["compass"]["width"]
        c_hgt = scr_reg.templates.template["compass"]["height"]
        wid = scr_reg.templates.template["navpoint"]["width"]
        hgt = scr_reg.templates.template["navpoint"]["height"]

        # cut out the compass from the region
        pad = 5
        compass_image = icompass_image[
            abs(pt[1] - pad) : pt[1] + c_hgt + pad, abs(pt[0] - pad) : pt[0] + c_wid + pad
        ].copy()
        # compass_image_gray = cv2.cvtColor(compass_image, cv2.COLOR_BGR2GRAY)

        # find the nav point within the compass box
        navpt_image, (n_minVal, n_maxVal, n_minLoc, n_maxLoc), match = scr_reg.match_template_in_image_x3(
            compass_image, "navpoint"
        )
        n_pt = n_maxLoc

        compass_x_min = pad
        compass_x_max = c_wid + pad - wid
        compass_y_min = pad
        compass_y_max = c_hgt + pad - hgt

        if n_maxVal < scr_reg.navpoint_match_thresh:
            final_z_pct = -1.0  # Behind

            # find the nav point within the compass box using the -behind template
            navpt_image, (n_minVal, n_maxVal, n_minLoc, n_maxLoc), match = scr_reg.match_template_in_image_x3(
                compass_image, "navpoint-behind"
            )
            n_pt = n_maxLoc
        else:
            final_z_pct = 1.0  # Ahead

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
                print("exception in getdest: " + str(e))
            cv2.waitKey(30)

        if maxVal > scr_reg.target_occluded_thresh:
            logger.debug(f"Target is occluded ({maxVal:5.4f} > {scr_reg.target_occluded_thresh:5.2f})")
            return True
        else:
            # logger.debug(f"Target is not occluded ({maxVal:5.4f} < {scr_reg.target_occluded_thresh:5.2f})")
            return False

    def get_destination_offset(self, scr_reg):
        """Determine how far off we are from the target being in the middle of the screen
        (in this case the specified region)."""
        dst_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region("target", "target")

        pt = maxLoc

        destination_width = scr_reg.reg["target"]["width"]
        destination_height = scr_reg.reg["target"]["height"]

        width = scr_reg.templates.template["target"]["width"]
        height = scr_reg.templates.template["target"]["height"]

        # need some fug numbers since our template is not symetric to determine center
        final_x = ((pt[0] + ((1 / 2) * width)) - ((1 / 2) * destination_width)) - 7
        final_y = (((1 / 2) * destination_height) - (pt[1] + ((1 / 2) * height))) + 22

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
                print("exception in getdest: " + str(e))
            cv2.waitKey(30)

        # print (maxVal)
        # must be > x to have solid hit, otherwise we are facing wrong way (empty circle)
        if maxVal < scr_reg.target_thresh:
            result = None
        else:
            result = {"x": final_x, "y": final_y}

        return result

    def sc_disengage_label_up(self, scr_reg) -> bool:
        """look for messages like "PRESS [J] TO DISENGAGE" or "SUPERCRUISE OVERCHARGE ACTIVE",
         if in this region then return true.
        The aim of this function is to return that a message is there, and then use OCR to determine
        what the message is. This will only use the high CPU usage OCR when necessary."""
        dis_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region("disengage", "disengage")

        pt = maxLoc

        width = scr_reg.templates.template["disengage"]["width"]
        height = scr_reg.templates.template["disengage"]["height"]

        # # Draw box around region
        # reg_rect = scr_reg.reg['disengage']['rect']
        # if self.debug_overlay:
        #     abs_rect = [pt[0] + reg_rect[0], pt[1] + reg_rect[1], pt[0] + reg_rect[0] + width, pt[1] + reg_rect[1] + height]
        #     self.overlay.overlay_rect1('sc_disengage_label_up', abs_rect, (0, 255, 0), 2)
        #     self.overlay.overlay_floating_text('sc_disengage_label_up', f'Match: {maxVal:5.4f} > {scr_reg.disengage_thresh}', abs_rect[0], abs_rect[1] - 25, (0, 255, 0))
        #     self.overlay.overlay_paint()

        if self.cv_view:
            self.draw_match_rect(dis_image, pt, (pt[0] + width, pt[1] + height), (0, 255, 0), 2)
            dis_image = cv2.rectangle(dis_image, (0, 0), (1000, 25), (0, 0, 0), -1)
            cv2.putText(
                dis_image,
                f"{maxVal:5.4f} > {scr_reg.disengage_thresh}",
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

        if maxVal > scr_reg.disengage_thresh:
            return True
        else:
            return False

    def sc_disengage(self, scr_reg) -> bool:
        """DEPRECATED - Replaced with 'sc_disengage_label_up' and 'sc_disengage_active' using OCR.
        look for the "PRESS [J] TO DISENGAGE" image, if in this region then return true
        """
        dis_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region("disengage", "disengage")

        pt = maxLoc

        width = scr_reg.templates.template["disengage"]["width"]
        height = scr_reg.templates.template["disengage"]["height"]

        if self.cv_view:
            self.draw_match_rect(dis_image, pt, (pt[0] + width, pt[1] + height), (0, 255, 0), 2)
            dis_image = cv2.rectangle(dis_image, (0, 0), (1000, 25), (0, 0, 0), -1)
            cv2.putText(
                dis_image,
                f"{maxVal:5.4f} > {scr_reg.disengage_thresh}",
                (1, 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.imshow("disengage", dis_image)
            cv2.moveWindow("disengage", self.cv_view_x - 460, self.cv_view_y + 575)
            cv2.waitKey(1)

        # logger.debug("Disenage = "+str(maxVal))

        if maxVal > scr_reg.disengage_thresh:
            logger.info("'PRESS [] TO DISENGAGE' detected. Disengaging Supercruise")
            self.vce.say("Disengaging Supercruise")
            return True
        else:
            return False

    def sc_disengage_active(self, scr_reg) -> bool:
        """look for the "SUPERCRUISE OVERCHARGE ACTIVE" text using OCR, if in this region then return true."""
        image = self.scr.get_screen_region(scr_reg.reg["disengage"]["rect"])
        # TODO delete this line when COLOR_RGB2BGR is removed from get_screen()
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mask = scr_reg.capture_region_filtered(self.scr, "disengage")
        masked_image = cv2.bitwise_and(image, image, mask=mask)
        image = masked_image

        # OCR the selected item
        sim_match = 0.35  # Similarity match 0.0 - 1.0 for 0% - 100%)
        sim = 0.0
        ocr_textlist = self.ocr.image_simple_ocr(image)
        if ocr_textlist is not None:
            sim = self.ocr.string_similarity(self.locale["PRESS_TO_DISENGAGE_MSG"], str(ocr_textlist))
            logger.info(f"Disengage similarity with {str(ocr_textlist)} is {sim}")

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
            logger.info("'PRESS [] TO DISENGAGE' detected. Disengaging Supercruise")
            # cv2.imwrite(paths.debug_path('disengage.png'), image)
            return True

        return False

    def is_sun_dead_ahead(self, scr_reg):
        return scr_reg.sun_percent(scr_reg.screen) > 5
