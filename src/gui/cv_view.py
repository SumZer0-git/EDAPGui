"""Live recognition images, rendered exclusively by the Tk GUI thread."""

import threading
import tkinter as tk

import cv2
import win32api
import win32con
from PIL import Image, ImageTk

from gui.theme import PANEL, TEXT, dark_titlebar

CV_VIEWS = {
    "compass": "Compass",
    "target": "Target",
    "occluded": "Occluded Target",
    "hud": "HUD Messages",
}
_HUD_SOURCES = {"sc_disengage_label_up", "disengage2"}


def view_name(source):
    return "hud" if source in _HUD_SOURCES else source


class CvFrames:
    """Keep only the latest frames for explicitly opened views."""

    def __init__(self):
        self._lock = threading.Lock()
        self._opened = set()
        self._frames = {}

    def open(self, name):
        if name not in CV_VIEWS:
            raise ValueError(f"Unknown CV view: {name}")
        with self._lock:
            self._opened.add(name)

    def close(self, name):
        with self._lock:
            self._opened.discard(name)
            self._frames = {key: frame for key, frame in self._frames.items() if view_name(key) != name}

    def is_open(self, source):
        with self._lock:
            return view_name(source) in self._opened

    def submit(self, name, image):
        with self._lock:
            if view_name(name) in self._opened:
                self._frames[name] = image.copy()

    def take(self):
        with self._lock:
            frames, self._frames = self._frames, {}
            return frames


def fit_window(x, y, width, height, work_area):
    left, top, right, bottom = work_area
    width = min(width, max(1, right - left - 40))
    height = min(height, max(1, bottom - top - 80))
    return max(left + 10, min(x, right - width - 20)), max(top + 40, min(y, bottom - height - 40)), width, height


class CvView:
    def __init__(self, root, frames):
        self.root = root
        self.frames = frames
        self.windows = {}
        self._images = {}
        self._sizes = {}
        self.job = root.after(50, self.refresh)

    def open_view(self, name):
        if name not in CV_VIEWS:
            raise ValueError(f"Unknown CV view: {name}")
        if name in self.windows:
            self.windows[name][0].deiconify()
            self.windows[name][0].lift()
            return
        x, y = self.root.winfo_x(), self.root.winfo_y()
        monitor = win32api.MonitorFromPoint((x, y), win32con.MONITOR_DEFAULTTONEAREST)
        work = win32api.GetMonitorInfo(monitor)["Work"]
        x, y, width, height = fit_window(x + 30, y + 30, 600, 300, work)
        window = tk.Toplevel(self.root)
        window.title(f"CV View - {CV_VIEWS[name]}")
        window.configure(bg=PANEL)
        labels = {}
        sources = ("sc_disengage_label_up", "disengage2") if name == "hud" else (name,)
        window.columnconfigure(0, weight=1)
        for index, source in enumerate(sources):
            row = index * 2 if name == "hud" else index
            if name == "hud":
                title = "Message check" if source == "sc_disengage_label_up" else "OCR result"
                tk.Label(window, text=title, bg=PANEL, fg=TEXT).grid(row=row, column=0)
                row += 1
            window.rowconfigure(row, weight=1, uniform="images")
            label = tk.Label(
                window, text="Waiting for recognition...", bg=PANEL, fg=TEXT, borderwidth=0, padx=0, pady=0
            )
            label.grid(row=row, column=0, sticky="nsew")
            labels[source] = label
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.protocol("WM_DELETE_WINDOW", lambda: self.close_view(name))
        dark_titlebar(window)
        self.windows[name] = window, labels
        self.frames.open(name)

    def close_view(self, name):
        self.frames.close(name)
        window, _labels = self.windows.pop(name)
        self._sizes.pop(name, None)
        self._images = {key: image for key, image in self._images.items() if view_name(key) != name}
        window.destroy()

    def refresh(self):
        changed = set()
        for source, frame in self.frames.take().items():
            name = view_name(source)
            if name not in self.windows:
                continue
            if frame.ndim == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB if frame.shape[2] == 4 else cv2.COLOR_BGR2RGB)
            self._images[source] = Image.fromarray(frame)
            changed.add(source)
        for name, (window, labels) in self.windows.items():
            width, height = max(1, window.winfo_width()), max(1, window.winfo_height())
            resized = self._sizes.get(name) != (width, height)
            self._sizes[name] = width, height
            for source, label in labels.items():
                if source not in self._images or not (resized or source in changed):
                    continue
                image = self._images[source]
                available_height = max(1, height // 2 - 25) if name == "hud" else height
                scale = min(width / image.width, available_height / image.height)
                size = max(1, int(image.width * scale)), max(1, int(image.height * scale))
                display = image.resize(size, Image.Resampling.BILINEAR)
                photo = ImageTk.PhotoImage(display, master=window)
                label.configure(image=photo, text="")
                label.image = photo
        self.job = self.root.after(50 if self.windows else 250, self.refresh)

    def close(self):
        self.root.after_cancel(self.job)
        for name in list(self.windows):
            self.close_view(name)
