"""Colors, scaling and Windows window helpers of the dark user interface."""

import ctypes
import tkinter.font as tkfont

from PIL import Image, ImageDraw, ImageTk
from ttkbootstrap.style import ThemeDefinition

# Greys are for surfaces, orange and blue are the brand colors, red and green carry meaning.
BG = "#111111"
PANEL = "#222222"
CARD = "#333333"
FIELD = "#444444"
LINE = "#444444"
TEXT = "#e6e6e6"
MUTED = "#b3b3b3"
DISABLED = "#6b6b6b"
ORANGE = "#F56200"
BLUE = "#1779ba"
RED = "#ec300d"
RED_HOVER = "#c42609"
GREEN = "#00ff14"
YELLOW = "#ffd400"

# Segoe Fluent Icons (Windows 11) or Segoe MDL2 Assets (Windows 10) glyphs
ICONS = {
    "travel": "\ue707",
    "waypoint": "\ue81d",
    "afk": "\ue7ba",
    "dss": "\ue774",
    "stop": "\ue71a",
    "power": "\ue7e8",
    "pin": "\ue718",
    "left": "\ue76b",
    "right": "\ue76c",
    "add": "\ue710",
    "edit": "\ue70f",
    "delete": "\ue74d",
    "up": "\ue74a",
    "down": "\ue74b",
    "duplicate": "\ue8c8",
    "before": "\ue898",
    "after": "\ue896",
}

SM_CXMINTRACK = 34
GWL_STYLE = -16
WS_MAXIMIZEBOX = 0x00010000
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
PER_MONITOR_AWARE_V2 = -4


def enable_dpi_awareness():
    """Per-Monitor V2: Windows then scales the title bar for each monitor itself. Call before creating the window."""
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(PER_MONITOR_AWARE_V2))
    except Exception:
        pass


def window_handle(window):
    return ctypes.windll.user32.GetParent(window.winfo_id())


def window_dpi(window):
    try:
        return ctypes.windll.user32.GetDpiForWindow(window_handle(window)) or 96
    except Exception:
        return 96


def dark_titlebar(window):
    try:
        window.update_idletasks()
        value = ctypes.c_int(1)
        for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(window_handle(window), attribute, ctypes.byref(value), 4)
    except Exception:
        pass


def remove_maximize(window):
    try:
        hwnd = window_handle(window)
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style & ~WS_MAXIMIZEBOX)
    except Exception:
        pass


def min_caption_width(window):
    """Narrowest width Windows allows for the window (it is set by the title bar buttons)."""
    try:
        return ctypes.windll.user32.GetSystemMetricsForDpi(SM_CXMINTRACK, window_dpi(window))
    except Exception:
        return 136


def icon_font(window):
    families = set(tkfont.families(window))
    return "Segoe Fluent Icons" if "Segoe Fluent Icons" in families else "Segoe MDL2 Assets"


class Metrics:
    """Converts logical pixels to the pixels of the current monitor scaling."""

    def __init__(self, window):
        self.window = window

    @property
    def scale(self):
        return float(self.window.tk.call("tk", "scaling")) / (4 / 3)

    def px(self, n):
        return max(1, round(n * self.scale))

    def u(self, n):
        """Logical pixels as a Tk point distance, which follows 'tk scaling' by itself."""
        return f"{n * 0.75:g}p"

    def set_dpi(self, dpi):
        """Make Tk, and the fonts defined in points, follow the DPI of the monitor the window is on."""
        self.window.tk.call("tk", "scaling", dpi / 72)
        for name in tkfont.names(self.window):
            font = tkfont.nametofont(name, root=self.window)
            font.configure(size=font.actual("size"))
        _shapes.clear()


class Theme:
    def __init__(self, window, metrics):
        self.window = window
        self.metrics = metrics
        self._counter = 0

    @property
    def style(self):
        return self.window.style

    def apply(self):
        """Register and activate the theme. A new theme name makes ttkbootstrap rebuild its images at the current scaling."""
        self._counter += 1
        colors = dict(
            primary=ORANGE, secondary=LINE, success=GREEN, info=BLUE, warning=YELLOW, danger=RED,
            light=TEXT, dark=PANEL, bg=BG, fg=TEXT, selectbg=BLUE, selectfg=TEXT, border=LINE,
            inputfg=TEXT, inputbg=FIELD, active=CARD,
        )  # fmt: skip
        name = f"edap{self._counter}"
        self.style.register_theme(ThemeDefinition(name, colors, "dark"))
        self.style.theme_use(name)
        px = self.metrics.px
        self.style.configure("TNotebook", tabmargins=(0, 0, 0, 0), bordercolor=BG, lightcolor=BG, darkcolor=BG)
        self.style.configure("TNotebook.Tab", padding=(px(18), px(8)), margin=(0, 0, px(8), 0))
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", BG), ("active", "#555555"), ("!selected", LINE)],
            bordercolor=[("selected", BG), ("!selected", BG)],
            lightcolor=[("selected", BG), ("!selected", BG)],
            darkcolor=[("selected", BG), ("!selected", BG)],
        )
        self.window.configure(bg=BG)

    @property
    def surface(self):
        return self.style.lookup("TFrame", "background")


_shapes = {}


def rounded_image(width, height, radius, fill, outline, master=None):
    """Anti-aliased rounded rectangle (drawn 4x and scaled down), cached per size and colors."""
    key = (master.tk if master is not None else None, width, height, radius, fill, outline)
    if key not in _shapes:
        k = 4
        img = Image.new("RGBA", (width * k, height * k), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(
            [0, 0, width * k - 1, height * k - 1],
            radius=radius * k,
            fill=fill,
            outline=outline,
            width=k if outline else 0,
        )
        _shapes[key] = ImageTk.PhotoImage(img.resize((width, height), Image.LANCZOS), master=master)
    return _shapes[key]
