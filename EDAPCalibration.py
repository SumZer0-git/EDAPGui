from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox
import json
import os

from Screen_Regions import Quad, load_default_calib_data, MyRegion


def str_to_float(input_str: str) -> float:
    try:
        return float(input_str)
    except ValueError:
        return 0.0  # Assign a default value on error


class Calibration:
    def __init__(self, ed_ap, cb):
        self.ap = ed_ap
        self.ap_ckb = cb
        self.frame = None

        self.ocr_calibration_data: dict[str, MyRegion] = {}
        self.subregion_keys = None

    def create_calibration_tab(self, tab):
        self.ocr_calibration_data = load_default_calib_data()
        tab.columnconfigure(0, weight=1)

        # Region Calibration
        blk_region_cal = ttk.LabelFrame(tab, text="Region Calibration")
        blk_region_cal.grid(row=0, column=0, padx=10, pady=5, sticky="NSEW")
        blk_region_cal.columnconfigure(1, weight=1)

        ttk.Label(blk_region_cal, text="Region:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        region_keys = sorted([key for key, value in self.ocr_calibration_data.items() if isinstance(value,
                                                                                                    dict) and 'rect' in value and 'compass' not in key and 'target' not in key and 'subregion' not in key])
        self.calibration_region_var = tk.StringVar()
        self.calibration_region_combo = ttk.Combobox(blk_region_cal, textvariable=self.calibration_region_var,
                                                     values=region_keys)
        self.calibration_region_combo.grid(row=0, column=1, padx=5, pady=5, sticky="EW")
        self.calibration_region_combo.bind("<<ComboboxSelected>>", self.on_region_select)

        ttk.Label(blk_region_cal, text="Procedure:").grid(row=1, column=0, padx=5, pady=5, sticky="NW")
        self.calibration_rect_text_var = tk.StringVar()
        ttk.Label(blk_region_cal, textvariable=self.calibration_rect_text_var).grid(row=1, column=1, padx=5, pady=5,
                                                                                    sticky=tk.W)

        ttk.Label(blk_region_cal, text="Rect:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.calibration_rect_label_var = tk.StringVar()
        ttk.Label(blk_region_cal, textvariable=self.calibration_rect_label_var).grid(row=2, column=1, padx=5, pady=5,
                                                                                     sticky=tk.W)

        ttk.Label(blk_region_cal,
                  text="Manually change the region below and save.\nHint: You can also use your keyboard up and down arrow keys.").grid(
            row=3, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        self.calibration_rect_left_var = tk.StringVar()
        lbl_calibration_rect_left = ttk.Label(blk_region_cal, text='Left:')
        lbl_calibration_rect_left.grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        spn_calibration_rect_left = ttk.Spinbox(blk_region_cal, textvariable=self.calibration_rect_left_var, width=10,
                                                from_=0, to=1, increment=0.001, justify=tk.RIGHT,
                                                command=self.on_region_size_change)
        spn_calibration_rect_left.grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)

        self.calibration_rect_top_var = tk.StringVar()
        lbl_calibration_rect_top = ttk.Label(blk_region_cal, text='Top:')
        lbl_calibration_rect_top.grid(row=5, column=0, padx=5, pady=5, sticky=tk.W)
        spn_calibration_rect_top = ttk.Spinbox(blk_region_cal, textvariable=self.calibration_rect_top_var, width=10,
                                               from_=0, to=1, increment=0.001, justify=tk.RIGHT,
                                               command=self.on_region_size_change)
        spn_calibration_rect_top.grid(row=5, column=1, padx=5, pady=5, sticky=tk.W)

        self.calibration_rect_right_var = tk.StringVar()
        lbl_calibration_rect_right = ttk.Label(blk_region_cal, text='Right:')
        lbl_calibration_rect_right.grid(row=6, column=0, padx=5, pady=5, sticky=tk.W)
        spn_calibration_rect_right = ttk.Spinbox(blk_region_cal, textvariable=self.calibration_rect_right_var, width=10,
                                                 from_=0, to=1, increment=0.001, justify=tk.RIGHT,
                                                 command=self.on_region_size_change)
        spn_calibration_rect_right.grid(row=6, column=1, padx=5, pady=5, sticky=tk.W)

        self.calibration_rect_bottom_var = tk.StringVar()
        lbl_calibration_rect_bottom = ttk.Label(blk_region_cal, text='Bottom:')
        lbl_calibration_rect_bottom.grid(row=7, column=0, padx=5, pady=5, sticky=tk.W)
        spn_calibration_rect_bottom = ttk.Spinbox(blk_region_cal, textvariable=self.calibration_rect_bottom_var,
                                                  width=10, from_=0, to=1, increment=0.001, justify=tk.RIGHT,
                                                  command=self.on_region_size_change)
        spn_calibration_rect_bottom.grid(row=7, column=1, padx=5, pady=5, sticky=tk.W)
        r = 9

        # Region Calibration
        blk_subregion_cal = ttk.LabelFrame(blk_region_cal, text="Sub-Region Calibration")
        blk_subregion_cal.grid(row=r, column=0, columnspan=2, padx=10, pady=5, sticky="NSEW")
        blk_subregion_cal.columnconfigure(1, weight=1)

        # SUB-REGION
        ttk.Label(blk_subregion_cal, text="Sub-region:").grid(row=r, column=0, padx=5, pady=5, sticky=tk.W)
        self.calibration_subregion_var = tk.StringVar()
        self.calibration_subregion_combo = ttk.Combobox(blk_subregion_cal, textvariable=self.calibration_subregion_var,
                                                        values=self.subregion_keys)
        self.calibration_subregion_combo.grid(row=r, column=1, padx=5, pady=5, sticky="EW")
        self.calibration_subregion_combo.bind("<<ComboboxSelected>>", self.on_subregion_select)
        r += 1

        ttk.Label(blk_subregion_cal, text="Procedure:").grid(row=r, column=0, padx=5, pady=5, sticky="NW")
        self.calibration_subrect_text_var = tk.StringVar()
        ttk.Label(blk_subregion_cal, textvariable=self.calibration_subrect_text_var).grid(row=r, column=1, padx=5, pady=5, sticky=tk.W)
        r += 1

        self.calibration_subrect_left_var = tk.StringVar()
        lbl_calibration_subrect_left = ttk.Label(blk_subregion_cal, text='Left:')
        lbl_calibration_subrect_left.grid(row=r, column=0, padx=5, pady=5, sticky=tk.W)
        spn_calibration_subrect_left = ttk.Spinbox(blk_subregion_cal, textvariable=self.calibration_subrect_left_var,
                                                   width=10,
                                                   from_=0, to=1, increment=0.001, justify=tk.RIGHT,
                                                   command=self.on_subregion_size_change)
        spn_calibration_subrect_left.grid(row=r, column=1, padx=5, pady=5, sticky=tk.W)
        r += 1

        self.calibration_subrect_top_var = tk.StringVar()
        lbl_calibration_subrect_top = ttk.Label(blk_subregion_cal, text='Top:')
        lbl_calibration_subrect_top.grid(row=r, column=0, padx=5, pady=5, sticky=tk.W)
        spn_calibration_subrect_top = ttk.Spinbox(blk_subregion_cal, textvariable=self.calibration_subrect_top_var,
                                                  width=10,
                                                  from_=0, to=1, increment=0.001, justify=tk.RIGHT,
                                                  command=self.on_subregion_size_change)
        spn_calibration_subrect_top.grid(row=r, column=1, padx=5, pady=5, sticky=tk.W)
        r += 1

        self.calibration_subrect_right_var = tk.StringVar()
        lbl_calibration_subrect_right = ttk.Label(blk_subregion_cal, text='Right:')
        lbl_calibration_subrect_right.grid(row=r, column=0, padx=5, pady=5, sticky=tk.W)
        spn_calibration_subrect_right = ttk.Spinbox(blk_subregion_cal, textvariable=self.calibration_subrect_right_var,
                                                    width=10,
                                                    from_=0, to=1, increment=0.001, justify=tk.RIGHT,
                                                    command=self.on_subregion_size_change)
        spn_calibration_subrect_right.grid(row=r, column=1, padx=5, pady=5, sticky=tk.W)
        r += 1

        self.calibration_subrect_bottom_var = tk.StringVar()
        lbl_calibration_subrect_bottom = ttk.Label(blk_subregion_cal, text='Bottom:')
        lbl_calibration_subrect_bottom.grid(row=r, column=0, padx=5, pady=5, sticky=tk.W)
        spn_calibration_subrect_bottom = ttk.Spinbox(blk_subregion_cal, textvariable=self.calibration_subrect_bottom_var,
                                                     width=10, from_=0, to=1, increment=0.001, justify=tk.RIGHT,
                                                     command=self.on_subregion_size_change)
        spn_calibration_subrect_bottom.grid(row=r, column=1, padx=5, pady=5, sticky=tk.W)
        r += 1

        # Button Frame
        button_frame = ttk.Frame(blk_region_cal)
        button_frame.grid(row=r, column=0, padx=10, pady=10, sticky=tk.W)
        ttk.Button(button_frame, text="Calibrate Region help online", command=self.calibrate_region_help).grid(row=r, column=0, padx=5, pady=10, sticky=tk.W)
        ttk.Button(button_frame, text="Save All Calibrations", command=self.save_ocr_calibration_data, style="Accent.TButton").grid(row=r, column=1, padx=5, pady=10, sticky=tk.W)
        ttk.Button(button_frame, text="Reset All to Default", command=self.reset_all_calibrations).grid(row=r, column=2, padx=5, pady=10, sticky=tk.W)
        r += 1

        # Compass and Target Calibrations
        blk_other_cal = ttk.LabelFrame(tab, text="Target Calibration")
        blk_other_cal.grid(row=r, column=0, padx=10, pady=5, sticky="NSEW")

        btn_calibrate_target = ttk.Button(blk_other_cal, text="Calibrate Target", command=self.calibrate_callback)
        btn_calibrate_target.grid(row=1, padx=10, pady=5, sticky="W")

        lbl_calibrate_target = ttk.Label(blk_other_cal, wraplength=500, text='Performs target calibration for your '
                                                                             'screen. Perform when the target is '
                                                                             'visible center screen.')
        lbl_calibrate_target.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)

    def save_ocr_calibration_data(self):
        # q = Quad.from_rect(self.ocr_calibration_data['EDCodex.full_panel']['rect'])
        # fx = 0.95
        # fy = 0.96
        # q.scale(fx, fy)
        # self.ocr_calibration_data['EDStationServicesInShip.station_services']['rect'] = q.to_rect_list(round_dp=4)

        q = Quad.from_rect(self.ocr_calibration_data['EDCodex.full_panel']['rect'])
        q.scale(fx=1.025, fy=1.0)
        self.ocr_calibration_data['EDStationServicesInShip.commodities_market']['rect'] = q.to_rect_list(round_dp=4)

        q = Quad.from_rect(self.ocr_calibration_data['EDCodex.full_panel']['rect'])
        q.scale(fx=1.05, fy=1.08)
        self.ocr_calibration_data['EDSystemMap.full_panel']['rect'] = q.to_rect_list(round_dp=4)

        q = Quad.from_rect(self.ocr_calibration_data['EDCodex.full_panel']['rect'])
        q.scale(fx=1.05, fy=1.08)
        self.ocr_calibration_data['EDGalaxyMap.full_panel']['rect'] = q.to_rect_list(round_dp=4)

        q = Quad.from_rect(self.ocr_calibration_data['EDCodex.full_panel']['rect'])
        q.scale(fx=1.0, fy=1.0)
        self.ocr_calibration_data['EDFSS.full_panel']['rect'] = q.to_rect_list(round_dp=4)

        # q = Quad.from_rect(self.ocr_calibration_data['EDStationServicesInShip.station_services']['rect'])
        # q.crop(0.0, 0.0, 0.25, 0.25)
        # self.ocr_calibration_data['EDStationServicesInShip.connected_to']['rect'] = q.to_rect_list(round_dp=4)

        calibration_file = 'configs/ocr_calibration.json'
        with open(calibration_file, 'w') as f:
            json.dump(self.ocr_calibration_data, f, indent=4)
        # self.log_msg("OCR calibration data saved.")
        self.ap_ckb('log', f"OCR calibration data saved.")
        # messagebox.showinfo("Saved", "OCR calibration data saved.\nPlease restart the application for changes to take effect.")

    def reset_all_calibrations(self):
        if messagebox.askyesno("Reset All Calibrations",
                               "Are you sure you want to reset all OCR calibrations to their default values? This cannot be undone."):
            calibration_file = 'configs/ocr_calibration.json'
            if os.path.exists(calibration_file):
                os.remove(calibration_file)
                # self.log_msg("Removed existing ocr_calibration.json.")
                self.ap_ckb('log', f"Removed existing ocr_calibration.json.")

            # This will recreate the file with defaults
            self.ocr_calibration_data = load_default_calib_data()

            # --- Repopulate UI ---
            # Clear current selections
            self.calibration_region_var.set('')
            # self.calibration_size_var.set('')
            self.calibration_rect_label_var.set('')
            # self.calibration_rect_left_var.set('')
            # self.calibration_size_label_var.set('')

            # Repopulate region dropdown
            region_keys = sorted([key for key in self.ocr_calibration_data.keys() if
                                  '.size.' not in key and 'compass' not in key and 'target' not in key])
            self.calibration_region_combo['values'] = region_keys

            # Repopulate size dropdown
            # size_keys = sorted([key for key in self.ocr_calibration_data.keys() if '.size.' in key])
            # self.calibration_size_combo['values'] = size_keys

            # self.log_msg("All OCR calibrations have been reset to default.")
            self.ap_ckb('log', f"All OCR calibrations have been reset to default.")
            messagebox.showinfo("Reset Complete",
                                "All calibrations have been reset to default. Please restart the application for all changes to take effect.")

    def on_region_select(self, event):
        selected_region = self.calibration_region_var.get()
        if selected_region in self.ocr_calibration_data.keys():
            reg = self.ocr_calibration_data[selected_region]
            rect = reg['rect']
            self.calibration_rect_label_var.set(f"[{rect[0]:.4f}, {rect[1]:.4f}, {rect[2]:.4f}, {rect[3]:.4f}]")
            self.calibration_rect_text_var.set(f"{self.ocr_calibration_data[selected_region].get('text', '')}")
            self.calibration_rect_left_var.set(str(rect[0]))
            self.calibration_rect_top_var.set(str(rect[1]))
            self.calibration_rect_right_var.set(str(rect[2]))
            self.calibration_rect_bottom_var.set(str(rect[3]))

            self.subregion_keys = [key for key, value in self.ocr_calibration_data.items() if
                                   isinstance(value, dict) and key.startswith(selected_region) and 'subregion' in key]
            self.calibration_subregion_var.set('')
            self.calibration_subregion_combo['values'] = self.subregion_keys
            if len(self.subregion_keys) > 0:
                self.calibration_subregion_var.set(self.subregion_keys[0])
            else:
                # No subregion
                self.ap.overlay.overlay_remove_quad('subregion select')
                self.ap.overlay.overlay_paint()

            # if 'regions' in reg:
            #     self.sub_region_keys = reg['regions'].keys
            # self.sub_region_keys = [key for key, value in reg['regions'] if isinstance(value, dict) and 'regions' in value]

            reg_f = Quad.from_rect(rect)
            self.ap.overlay.overlay_quad_pct('region select', reg_f, (0, 255, 0), 2, 15)
            self.ap.overlay.overlay_paint()

            # Trigger the subregion select to highlight the default subregion
            self.on_subregion_select(None)

    def on_subregion_select(self, event):
        selected_region = self.calibration_region_var.get()
        selected_subregion = self.calibration_subregion_var.get()
        if selected_region in self.ocr_calibration_data.keys() and selected_subregion in self.ocr_calibration_data.keys():
            reg = self.ocr_calibration_data[selected_region]
            rect = reg['rect']
            sub_reg = self.ocr_calibration_data[selected_subregion]
            sub_rect = sub_reg['rect']
            self.calibration_subrect_text_var.set(f"{self.ocr_calibration_data[selected_subregion].get('text', '')}")
            self.calibration_subrect_left_var.set(str(sub_rect[0]))
            self.calibration_subrect_top_var.set(str(sub_rect[1]))
            self.calibration_subrect_right_var.set(str(sub_rect[2]))
            self.calibration_subrect_bottom_var.set(str(sub_rect[3]))

            scaled_rect = Quad.from_rect(reg['rect'])
            sub_reg_quad = Quad.from_rect(sub_reg['rect'])
            scaled_rect.crop(sub_reg_quad)
            self.ap.overlay.overlay_quad_pct('subregion select', scaled_rect, (0, 255, 0), 2, 15)
            self.ap.overlay.overlay_paint()
        else:
            self.calibration_subrect_text_var.set('')
            self.calibration_subrect_left_var.set('0.0')
            self.calibration_subrect_top_var.set('0.0')
            self.calibration_subrect_right_var.set('0.0')
            self.calibration_subrect_bottom_var.set('0.0')

    def on_region_size_change(self):
        # Check if variables are valid
        l_str = self.calibration_rect_left_var.get()
        t_str = self.calibration_rect_top_var.get()
        r_str = self.calibration_rect_right_var.get()
        b_str = self.calibration_rect_bottom_var.get()
        # Check if any are empty
        if l_str == '' or r_str == '' or t_str == '' or b_str == '':
            return

        selected_region = self.calibration_region_var.get()
        if selected_region in self.ocr_calibration_data:
            rect = self.ocr_calibration_data[selected_region]['rect']
            rect[0] = str_to_float(l_str)
            rect[1] = str_to_float(t_str)
            rect[2] = str_to_float(r_str)
            rect[3] = str_to_float(b_str)

            self.calibration_rect_label_var.set(f"[{rect[0]:.4f}, {rect[1]:.4f}, {rect[2]:.4f}, {rect[3]:.4f}]")
            self.calibration_rect_text_var.set(f"{self.ocr_calibration_data[selected_region].get('text', '')}")

            reg_f = Quad.from_rect(rect)
            self.ap.overlay.overlay_quad_pct('region select', reg_f, (0, 255, 0), 2, 15)
            self.ap.overlay.overlay_paint()

    def on_subregion_size_change(self):
        # Check if variables are valid
        l_str = self.calibration_rect_left_var.get()
        t_str = self.calibration_rect_top_var.get()
        r_str = self.calibration_rect_right_var.get()
        b_str = self.calibration_rect_bottom_var.get()

        sub_l_str = self.calibration_subrect_left_var.get()
        sub_t_str = self.calibration_subrect_top_var.get()
        sub_r_str = self.calibration_subrect_right_var.get()
        sub_b_str = self.calibration_subrect_bottom_var.get()
        # Check if any are empty
        if l_str == '' or r_str == '' or t_str == '' or b_str == '':
            return

        selected_region = self.calibration_region_var.get()
        selected_subregion = self.calibration_subregion_var.get()
        if selected_region in self.ocr_calibration_data.keys() and selected_subregion in self.ocr_calibration_data.keys():
            reg = self.ocr_calibration_data[selected_region]
            rect = self.ocr_calibration_data[selected_region]['rect']
            rect[0] = str_to_float(l_str)
            rect[1] = str_to_float(t_str)
            rect[2] = str_to_float(r_str)
            rect[3] = str_to_float(b_str)

            sub_reg = self.ocr_calibration_data[selected_subregion]
            sub_rect = self.ocr_calibration_data[selected_subregion]['rect']
            sub_rect[0] = str_to_float(sub_l_str)
            sub_rect[1] = str_to_float(sub_t_str)
            sub_rect[2] = str_to_float(sub_r_str)
            sub_rect[3] = str_to_float(sub_b_str)

            scaled_rect = Quad.from_rect(reg['rect'])
            sub_reg_quad = Quad.from_rect(sub_reg['rect'])
            scaled_rect.crop(sub_reg_quad)
            self.ap.overlay.overlay_quad_pct('subregion select', scaled_rect, (0, 255, 0), 2, 15)
            self.ap.overlay.overlay_paint()

    @staticmethod
    def calibrate_region_help():
        webbrowser.open_new("https://github.com/SumZer0-git/EDAPGui/blob/main/docs/Calibration.md")

    def calibrate_callback(self):
        self.ap.calibrate_target()


def dummy_cb(msg, body=None):
    pass


def main():
    # from ED_AP import EDAutopilot

    #ed_ap = EDAutopilot(cb=None)
    ce = Calibration(None, cb=dummy_cb)  # False = Horizons
    # ce.create_calibration_tab()


if __name__ == "__main__":
    main()
