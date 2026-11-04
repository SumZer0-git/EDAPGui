"""Draws lines and text as an overlay on top of the game screen."""

from __future__ import annotations

import ctypes
import threading
import time
import winreg
from ctypes import wintypes
from functools import lru_cache

import pywintypes
import win32api
import win32con
import win32event
import win32gui
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont

from core import paths
from core.logger import logger
from gui.theme import BG, BLUE, GREEN, LINE, MUTED, ORANGE, TEXT, YELLOW

elite_dangerous_window = "Elite - Dangerous (CLIENT)"
_PANEL_COLOR = ImageColor.getrgb(BG)
_LINE_COLOR = ImageColor.getrgb(LINE)
_STATUS_TEXT_COLORS = {
    "label": ImageColor.getrgb(ORANGE),
    "value": ImageColor.getrgb(TEXT),
    "muted": ImageColor.getrgb(MUTED),
    "active": ImageColor.getrgb(BLUE),
    "success": ImageColor.getrgb(GREEN),
    "warning": ImageColor.getrgb(YELLOW),
}

_WM_REDRAW = win32con.WM_APP + 1
_WM_DPICHANGED = 0x02E0
_WDA_EXCLUDEFROMCAPTURE = 0x11
_ULW_ALPHA = 0x2
_DIB_RGB_COLORS = 0
_BI_RGB = 0
_AC_SRC_OVER = 0
_AC_SRC_ALPHA = 1
_DPI_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
_EVENT_OBJECT_DESTROY = 0x8001
_EVENT_OBJECT_SHOW = 0x8002
_EVENT_OBJECT_HIDE = 0x8003
_EVENT_OBJECT_LOCATIONCHANGE = 0x800B
_EVENT_SYSTEM_MINIMIZESTART = 0x0016
_EVENT_SYSTEM_MINIMIZEEND = 0x0017
_WINEVENT_OUTOFCONTEXT = 0
_WINEVENTPROC = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.HWND,
    wintypes.LONG,
    wintypes.LONG,
    wintypes.DWORD,
    wintypes.DWORD,
)


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("bmiHeader", _BitmapInfoHeader), ("bmiColors", wintypes.DWORD * 1)]


class _BlendFunction(ctypes.Structure):
    _fields_ = [
        ("BlendOp", wintypes.BYTE),
        ("BlendFlags", wintypes.BYTE),
        ("SourceConstantAlpha", wintypes.BYTE),
        ("AlphaFormat", wintypes.BYTE),
    ]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

_user32.GetDC.argtypes = [wintypes.HWND]
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.ReleaseDC.restype = ctypes.c_int
_user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND,
    wintypes.HDC,
    ctypes.POINTER(wintypes.POINT),
    ctypes.POINTER(wintypes.SIZE),
    wintypes.HDC,
    ctypes.POINTER(wintypes.POINT),
    wintypes.COLORREF,
    ctypes.POINTER(_BlendFunction),
    wintypes.DWORD,
]
_user32.UpdateLayeredWindow.restype = wintypes.BOOL
_user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
_user32.SetThreadDpiAwarenessContext.argtypes = [wintypes.HANDLE]
_user32.SetThreadDpiAwarenessContext.restype = wintypes.HANDLE
_user32.SetWinEventHook.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HMODULE,
    _WINEVENTPROC,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
]
_user32.SetWinEventHook.restype = wintypes.HANDLE
_user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
_user32.UnhookWinEvent.restype = wintypes.BOOL
if hasattr(_user32, "GetDpiForWindow"):
    _user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    _user32.GetDpiForWindow.restype = wintypes.UINT
_gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
_gdi32.CreateCompatibleDC.restype = wintypes.HDC
_gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(_BitmapInfo),
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.HANDLE,
    wintypes.DWORD,
]
_gdi32.CreateDIBSection.restype = wintypes.HBITMAP
_gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
_gdi32.SelectObject.restype = wintypes.HGDIOBJ
_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi32.DeleteObject.restype = wintypes.BOOL
_gdi32.DeleteDC.argtypes = [wintypes.HDC]
_gdi32.DeleteDC.restype = wintypes.BOOL


@lru_cache(maxsize=32)
def _load_font(font_name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_name.casefold() == "rajdhani":
        try:
            return ImageFont.truetype(str(paths.FONTS_DIR / "Rajdhani-Medium.ttf"), size)
        except OSError:
            logger.warning("Could not load the bundled Rajdhani overlay font.")

    candidates = []
    try:
        fonts_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
    except OSError:
        fonts_key = None

    if fonts_key is not None:
        with fonts_key:
            index = 0
            while True:
                try:
                    name, filename, _ = winreg.EnumValue(fonts_key, index)
                except OSError:
                    break
                index += 1
                if name.split("(", maxsplit=1)[0].strip().casefold() == font_name.casefold():
                    candidates.append(filename)

    fonts_dir = win32api.GetWindowsDirectory() + r"\Fonts"
    for candidate in candidates:
        if not (len(candidate) > 1 and candidate[1] == ":"):
            candidate = fonts_dir + "\\" + candidate
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue

    if font_name.casefold() not in ("", "eurostyle"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            pass

    try:
        return ImageFont.truetype(fonts_dir + r"\arial.ttf", size)
    except OSError:
        logger.debug(f"Could not load overlay font '{font_name}'; using Pillow's default font.")
        return ImageFont.load_default(size=size)


def _draw_rect(draw: ImageDraw.ImageDraw, pt1, pt2, color, thickness: int) -> None:
    x1, y1 = pt1
    x2, y2 = pt2
    width = x2 - x1
    height = y2 - y1
    fill = (*color, 255)
    thick = max(1, int(thickness))

    def line(start, end, line_width=1):
        draw.line(
            ((round(start[0]), round(start[1])), (round(end[0]), round(end[1]))),
            fill=fill,
            width=max(1, int(line_width)),
        )

    if width < 20:
        draw.rectangle((x1, y1, x2, y2), outline=fill, width=1)
        return

    segment_x = width / 5
    segment_y = height / 5
    half_x = width / 2
    half_y = height / 2
    tick = thick - 1

    for y in (y1, y2):
        line((x1, y), (x1 + segment_x, y), thick)
        line((x1 + 2 * segment_x, y), (x1 + 3 * segment_x, y))
        line((x1 + 4 * segment_x, y), (x2, y), thick)
    line((x1 + half_x, y1), (x1 + half_x, y1 - tick))
    line((x1 + half_x, y2), (x1 + half_x, y2 + tick))

    for x in (x1, x2):
        line((x, y1), (x, y1 + segment_y), thick)
        line((x, y1 + 2 * segment_y), (x, y1 + 3 * segment_y))
        line((x, y1 + 4 * segment_y), (x, y2), thick)
    line((x1, y1 + half_y), (x1 - tick, y1 + half_y))
    line((x2, y1 + half_y), (x2 + tick, y1 + half_y))


def _render_image(
    width: int,
    height: int,
    lines: dict,
    text: dict,
    floating_text: dict,
    font_name: str,
    font_size: int,
    dpi: int,
    pos: tuple[int, int],
    anchor: str = "Top left",
    position_unit: str = "Pixels",
    panel_opacity: int = 78,
    progress: float | None = None,
) -> tuple[Image.Image, tuple[int, int]]:
    dpi_scale = dpi / 96
    pixel_size = max(1, round(dpi * font_size / 72))
    font = _load_font(font_name, pixel_size)
    line_height = pixel_size
    column_step = max(1, round(font_size * dpi_scale))
    panel_padding = max(1, round(12 * dpi_scale))
    valid_anchors = ("Top left", "Top right", "Bottom left", "Bottom right")
    anchor = anchor if anchor in valid_anchors else "Top left"
    panel_alpha = round(max(0, min(panel_opacity, 100)) * 255 / 100)
    progress_fraction = None if progress is None else max(0.0, min(progress, 1.0))

    text_elements = []
    text_bounds = []
    for entry in text.values():
        if len(entry) == 4:
            value, row, col, color = entry
            segments = ((value, color),)
        else:
            segments, row, col = entry
        x = col * column_step
        y = row * line_height
        for value, color in segments:
            if not value:
                continue
            if isinstance(color, str):
                color = _STATUS_TEXT_COLORS[color]
            text_box = font.getbbox(value, anchor="lt")
            text_bounds.append((x + text_box[0], y + text_box[1], x + text_box[2], y + text_box[3]))
            text_elements.append((value, x, y, color))
            x += text_box[2] - text_box[0]

    bounds = []
    panel = None
    progress_rect = None
    if text_bounds:
        min_x = min(bound[0] for bound in text_bounds)
        min_y = min(bound[1] for bound in text_bounds)
        max_x = max(bound[2] for bound in text_bounds)
        max_y = max(bound[3] for bound in text_bounds)
        text_height = max_y - min_y
        panel_width = max_x - min_x + 2 * panel_padding
        panel_height = text_height + 2 * panel_padding
        if progress_fraction is not None:
            progress_bar_height = max(3, round(4 * dpi_scale))
            progress_bar_gap = max(2, round(4 * dpi_scale))
            panel_height += progress_bar_gap + progress_bar_height
        offset_x, offset_y = pos
        if position_unit == "Percent":
            offset_x = round(width * max(0, min(offset_x, 100)) / 100)
            offset_y = round(height * max(0, min(offset_y, 100)) / 100)
        panel_x = offset_x if anchor.endswith("left") else width - offset_x - panel_width
        panel_y = offset_y if anchor.startswith("Top") else height - offset_y - panel_height
        panel_x = max(0, min(panel_x, max(0, width - panel_width)))
        panel_y = max(0, min(panel_y, max(0, height - panel_height)))
        panel = (panel_x, panel_y, panel_x + panel_width, panel_y + panel_height)
        bounds.append(panel)
        if progress_fraction is not None:
            progress_rect = (
                panel_x + panel_padding,
                panel_y + panel_padding + text_height + progress_bar_gap,
                panel_x + panel_width - panel_padding,
                panel_y + panel_padding + text_height + progress_bar_gap + progress_bar_height,
            )
        text_elements = [
            (value, panel_x + panel_padding + x - min_x, panel_y + panel_padding + y - min_y, color)
            for value, x, y, color in text_elements
        ]

    rect_elements = []
    for pt1, pt2, color, thickness in lines.values():
        line_padding = max(1, int(thickness))
        bounds.append(
            (
                min(pt1[0], pt2[0]) - line_padding,
                min(pt1[1], pt2[1]) - line_padding,
                max(pt1[0], pt2[0]) + line_padding + 1,
                max(pt1[1], pt2[1]) + line_padding + 1,
            )
        )
        rect_elements.append((pt1, pt2, color, thickness))

    floating_elements = []
    for value, x, y, color in floating_text.values():
        if not value:
            continue
        text_box = font.getbbox(value, anchor="lt")
        bounds.append((x + text_box[0], y + text_box[1], x + text_box[2], y + text_box[3]))
        floating_elements.append((value, x, y, color))

    if not bounds:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), (0, 0)

    left = max(0, min(bound[0] for bound in bounds))
    top = max(0, min(bound[1] for bound in bounds))
    right = min(width, max(bound[2] for bound in bounds))
    bottom = min(height, max(bound[3] for bound in bounds))
    if right <= left or bottom <= top:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), (0, 0)

    image = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if panel is not None and panel_alpha:
        panel_box = (panel[0] - left, panel[1] - top, panel[2] - left, panel[3] - top)
        draw.rounded_rectangle(
            panel_box,
            radius=round(8 * dpi_scale),
            fill=(*_PANEL_COLOR, panel_alpha),
            outline=(*_LINE_COLOR, round(panel_alpha * 0.8)),
            width=max(1, round(dpi_scale)),
        )

    if progress_rect is not None and progress_fraction is not None:
        progress_left = progress_rect[0] - left
        progress_top = progress_rect[1] - top
        progress_right = progress_rect[2] - left
        progress_bottom = progress_rect[3] - top
        progress_width = progress_right - progress_left
        progress_height = progress_bottom - progress_top
        progress_radius = progress_height // 2
        draw.rounded_rectangle(
            (progress_left, progress_top, progress_right, progress_bottom),
            radius=progress_radius,
            fill=(*_LINE_COLOR, 255),
        )
        fill_width = round(progress_width * progress_fraction)
        if fill_width:
            draw.rounded_rectangle(
                (progress_left, progress_top, progress_left + fill_width, progress_bottom),
                radius=progress_radius,
                fill=(*_STATUS_TEXT_COLORS["active"], 255),
            )

    for pt1, pt2, color, thickness in rect_elements:
        local_pt1 = (pt1[0] - left, pt1[1] - top)
        local_pt2 = (pt2[0] - left, pt2[1] - top)
        _draw_rect(draw, local_pt1, local_pt2, color, thickness)

    for value, x, y, color in text_elements:
        shadow_offset = max(1, round(dpi_scale))
        draw.text(
            (x - left + shadow_offset, y - top + shadow_offset),
            value,
            font=font,
            fill=(0, 0, 0, 180),
            anchor="lt",
        )
        draw.text((x - left, y - top), value, font=font, fill=(*color, 255), anchor="lt")
    for value, x, y, color in floating_elements:
        draw.text((x - left, y - top), value, font=font, fill=(*color, 255), anchor="lt")
    return image, (left, top)


class Overlay:
    def __init__(self, parent_window: str, elite: int = 0):
        self.parent = elite_dangerous_window if elite == 1 else parent_window
        self.hWindow = None
        self.tHwnd = None
        self.targetRect = (0, 0, 0, 0)
        self._target_position = (0, 0)
        self._target_size = (0, 0)
        self._position = (0, 0)
        self._surface_origin = (0, 0)
        self._size = (0, 0)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._class_name = f"EDAPGuiOverlay_{id(self):x}"
        self._class_atom = None
        self._wnd_class = None
        self._win_event_callback = _WINEVENTPROC(self._on_win_event)
        self._win_event_hooks = []
        self._font_name = "Rajdhani"
        self._font_size = 14
        self._pos = (0, 0)
        self._anchor = "Top left"
        self._position_unit = "Pixels"
        self._panel_opacity = 78
        self._progress = None
        self._lines = {}
        self._text = {}
        self._floating_text = {}
        self.overlay_thr = threading.Thread(target=self.overlay_win32_run, name="Overlay", daemon=True)
        self.overlay_thr.start()

    def _dpi_aware(self):
        try:
            previous = _user32.SetThreadDpiAwarenessContext(_DPI_PER_MONITOR_AWARE_V2)
        except (AttributeError, OSError):
            logger.warning("Per-monitor DPI awareness is unavailable for the overlay thread.")
            return None
        return previous

    def overlay_win32_run(self):
        previous_dpi_context = self._dpi_aware()
        try:
            self._register_window_class()
            self._register_win_event_hooks()
            while not self._stop_event.is_set():
                win32event.MsgWaitForMultipleObjects([], False, 500, win32con.QS_ALLINPUT)
                if win32gui.PumpWaitingMessages():
                    break
                try:
                    self._refresh_window()
                except (OSError, pywintypes.error) as exc:
                    logger.warning(f"Could not update the overlay window: {exc}")
        except (OSError, pywintypes.error) as exc:
            logger.error(f"Overlay window thread failed: {exc}")
        finally:
            self._destroy_overlay_window()
            self._unregister_win_event_hooks()
            try:
                if self._class_atom is not None:
                    win32gui.UnregisterClass(self._class_atom, win32api.GetModuleHandle())
            except pywintypes.error as exc:
                logger.warning(f"Could not unregister the overlay window class: {exc}")
            finally:
                self._wnd_class = None
                if previous_dpi_context:
                    _user32.SetThreadDpiAwarenessContext(previous_dpi_context)

    def _register_win_event_hooks(self):
        for event_min, event_max in (
            (_EVENT_OBJECT_DESTROY, _EVENT_OBJECT_LOCATIONCHANGE),
            (_EVENT_SYSTEM_MINIMIZESTART, _EVENT_SYSTEM_MINIMIZEEND),
        ):
            hook = _user32.SetWinEventHook(
                event_min,
                event_max,
                None,
                self._win_event_callback,
                0,
                0,
                _WINEVENT_OUTOFCONTEXT,
            )
            if hook:
                self._win_event_hooks.append(hook)
            else:
                logger.warning(
                    f"Could not register overlay window tracking hook (Windows error {ctypes.get_last_error()})."
                )

    def _unregister_win_event_hooks(self):
        for hook in self._win_event_hooks:
            if not _user32.UnhookWinEvent(hook):
                logger.warning(
                    f"Could not unregister overlay window tracking hook (Windows error {ctypes.get_last_error()})."
                )
        self._win_event_hooks.clear()

    def _on_win_event(self, *event_data: int):
        _, event, hwnd, object_id, child_id, _, _ = event_data
        if hwnd != self.tHwnd or object_id != 0 or child_id != 0:
            return
        if event in (
            _EVENT_OBJECT_DESTROY,
            _EVENT_OBJECT_SHOW,
            _EVENT_OBJECT_HIDE,
            _EVENT_OBJECT_LOCATIONCHANGE,
            _EVENT_SYSTEM_MINIMIZESTART,
            _EVENT_SYSTEM_MINIMIZEEND,
        ):
            try:
                self._refresh_window()
            except (OSError, pywintypes.error) as exc:
                logger.warning(f"Could not update the overlay after a game-window event: {exc}")

    def _register_window_class(self):
        wnd_class = win32gui.WNDCLASS()
        wnd_class.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW
        wnd_class.lpfnWndProc = self._window_proc
        wnd_class.hInstance = win32api.GetModuleHandle()
        wnd_class.hCursor = win32gui.LoadCursor(None, win32con.IDC_ARROW)
        wnd_class.lpszClassName = self._class_name
        self._wnd_class = wnd_class
        self._class_atom = win32gui.RegisterClass(wnd_class)

    def _refresh_window(self):
        target = win32gui.FindWindow(None, self.parent) if self.parent else None
        if self.parent and not target:
            if self.hWindow is not None:
                self._destroy_overlay_window()
            self.tHwnd = None
            return

        if target != self.tHwnd:
            self._destroy_overlay_window()
            self.tHwnd = target

        if self.hWindow is None:
            self._create_overlay_window()

        if target:
            rect = self._get_target_window_rect()
        else:
            rect = (
                0,
                0,
                win32api.GetSystemMetrics(win32con.SM_CXSCREEN),
                win32api.GetSystemMetrics(win32con.SM_CYSCREEN),
            )

        x, y, width, height = rect
        if width <= 0 or height <= 0:
            return
        position = (x, y)
        size = (width, height)
        if position != self._target_position or size != self._target_size:
            size_changed = size != self._target_size
            self._target_position = position
            self._target_size = size
            self.targetRect = rect
            if size_changed:
                self._render()
            else:
                self._position = (x + self._surface_origin[0], y + self._surface_origin[1])
                self._move_overlay_window()

        if target and (not win32gui.IsWindowVisible(target) or win32gui.IsIconic(target)):
            win32gui.ShowWindow(self.hWindow, win32con.SW_HIDE)
        elif not win32gui.IsWindowVisible(self.hWindow):
            win32gui.ShowWindow(self.hWindow, win32con.SW_SHOWNOACTIVATE)

    def _get_target_window_rect(self):
        client = win32gui.GetClientRect(self.tHwnd)
        left, top = win32gui.ClientToScreen(self.tHwnd, (client[0], client[1]))
        return left, top, client[2] - client[0], client[3] - client[1]

    def _create_overlay_window(self):
        ex_style = (
            win32con.WS_EX_LAYERED | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW
        )
        if self.tHwnd is None:
            ex_style |= win32con.WS_EX_TOPMOST
        style = win32con.WS_POPUP | win32con.WS_DISABLED
        hwnd = win32gui.CreateWindowEx(
            ex_style,
            self._class_atom,
            None,
            style,
            0,
            0,
            1,
            1,
            self.tHwnd,
            None,
            win32api.GetModuleHandle(),
            None,
        )
        with self._lock:
            self.hWindow = hwnd

        if not _user32.SetWindowDisplayAffinity(hwnd, _WDA_EXCLUDEFROMCAPTURE):
            error = ctypes.get_last_error()
            logger.warning(f"Could not exclude the overlay from screen capture (Windows error {error}).")

        if self.tHwnd is None:
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOACTIVATE | win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
            )
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
        self.overlay_paint()

    def _destroy_overlay_window(self):
        hwnd = self.hWindow
        if hwnd is not None and win32gui.IsWindow(hwnd):
            win32gui.DestroyWindow(hwnd)
        with self._lock:
            self.hWindow = None
        self._position = (0, 0)
        self._target_position = (0, 0)
        self._target_size = (0, 0)
        self._surface_origin = (0, 0)
        self._size = (0, 0)

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == _WM_DPICHANGED:
            self.overlay_paint()
            return 0
        if message == _WM_REDRAW:
            try:
                self._render()
            except (OSError, pywintypes.error) as exc:
                logger.warning(f"Could not draw the overlay: {exc}")
            return 0
        if message == win32con.WM_DESTROY:
            with self._lock:
                if self.hWindow == hwnd:
                    self.hWindow = None
            return 0
        return win32gui.DefWindowProc(hwnd, message, wparam, lparam)

    def _render(self):
        with self._lock:
            hwnd = self.hWindow
            lines = dict(self._lines)
            text = dict(self._text)
            floating_text = dict(self._floating_text)
            font_name = self._font_name
            font_size = self._font_size
            pos = self._pos
            anchor = self._anchor
            position_unit = self._position_unit
            panel_opacity = self._panel_opacity
            progress = self._progress
            target_position = self._target_position
            target_width, target_height = self._target_size
        if hwnd is None or target_width <= 0 or target_height <= 0:
            return

        dpi = 96
        if hasattr(_user32, "GetDpiForWindow"):
            dpi = _user32.GetDpiForWindow(hwnd)
        image, origin = _render_image(
            target_width,
            target_height,
            lines,
            text,
            floating_text,
            font_name,
            font_size,
            dpi,
            pos,
            anchor=anchor,
            position_unit=position_unit,
            panel_opacity=panel_opacity,
            progress=progress,
        )
        self._surface_origin = origin
        self._size = image.size
        self._position = (target_position[0] + origin[0], target_position[1] + origin[1])
        self._move_overlay_window()
        self._update_layered_window(hwnd, image, *self._position)

    def _move_overlay_window(self):
        if self.hWindow is None:
            return
        width, height = self._size
        if width <= 0 or height <= 0:
            width, height = 1, 1
        x, y = self._position
        win32gui.SetWindowPos(
            self.hWindow,
            win32con.HWND_TOP,
            x,
            y,
            width,
            height,
            win32con.SWP_NOACTIVATE | win32con.SWP_NOOWNERZORDER | win32con.SWP_NOZORDER,
        )

    @staticmethod
    def _update_layered_window(hwnd, image: Image.Image, x: int, y: int):
        width, height = image.size
        red, green, blue, alpha = image.split()
        premultiplied = Image.merge(
            "RGBA",
            (
                ImageChops.multiply(blue, alpha),
                ImageChops.multiply(green, alpha),
                ImageChops.multiply(red, alpha),
                alpha,
            ),
        )
        pixels = premultiplied.tobytes()

        screen_dc = _user32.GetDC(None)
        if not screen_dc:
            raise ctypes.WinError(ctypes.get_last_error())
        memory_dc = _gdi32.CreateCompatibleDC(screen_dc)
        if not memory_dc:
            _user32.ReleaseDC(None, screen_dc)
            raise ctypes.WinError(ctypes.get_last_error())

        bitmap = None
        old_bitmap = None
        try:
            bitmap_info = _BitmapInfo()
            bitmap_info.bmiHeader = _BitmapInfoHeader(
                ctypes.sizeof(_BitmapInfoHeader),
                width,
                -height,
                1,
                32,
                _BI_RGB,
                len(pixels),
                0,
                0,
                0,
                0,
            )
            bits = ctypes.c_void_p()
            bitmap = _gdi32.CreateDIBSection(
                memory_dc, ctypes.byref(bitmap_info), _DIB_RGB_COLORS, ctypes.byref(bits), None, 0
            )
            if not bitmap or not bits:
                raise ctypes.WinError(ctypes.get_last_error())
            ctypes.memmove(bits, pixels, len(pixels))
            old_bitmap = _gdi32.SelectObject(memory_dc, bitmap)

            destination = wintypes.POINT(x, y)
            size = wintypes.SIZE(width, height)
            source = wintypes.POINT(0, 0)
            blend = _BlendFunction(_AC_SRC_OVER, 0, 255, _AC_SRC_ALPHA)
            if not _user32.UpdateLayeredWindow(
                hwnd,
                screen_dc,
                ctypes.byref(destination),
                ctypes.byref(size),
                memory_dc,
                ctypes.byref(source),
                0,
                ctypes.byref(blend),
                _ULW_ALPHA,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            if old_bitmap:
                _gdi32.SelectObject(memory_dc, old_bitmap)
            if bitmap:
                _gdi32.DeleteObject(bitmap)
            _gdi32.DeleteDC(memory_dc)
            _user32.ReleaseDC(None, screen_dc)

    def overlay_rect(self, key, pt1, pt2, color, thick):
        with self._lock:
            self._lines[key] = [pt1, pt2, color, thick]

    def overlay_rect1(self, key, rect, color, thick):
        self.overlay_rect(key, (rect[0], rect[1]), (rect[2], rect[3]), color, thick)

    def overlay_setfont(self, fontname, fsize):
        with self._lock:
            self._font_name = fontname
            self._font_size = fsize

    def overlay_set_pos(self, x, y):
        with self._lock:
            self._pos = (x, y)
            self._anchor = "Top left"
            self._position_unit = "Pixels"

    def overlay_set_layout(self, anchor, position_unit, x, y, panel_opacity):
        with self._lock:
            self._anchor = anchor
            self._position_unit = position_unit
            self._pos = (x, y)
            self._panel_opacity = panel_opacity

    def overlay_text(self, key, txt, row, col, color):
        with self._lock:
            self._text[key] = [txt, row, col, color]

    def overlay_text_segments(self, key, segments, row, col):
        with self._lock:
            self._text[key] = [segments, row, col]

    def overlay_set_progress(self, progress: float | None):
        with self._lock:
            self._progress = None if progress is None else max(0.0, min(progress, 1.0))

    def overlay_floating_text(self, key, txt, x, y, color):
        with self._lock:
            self._floating_text[key] = [txt, x, y, color]

    def overlay_paint(self):
        with self._lock:
            hwnd = self.hWindow
        if hwnd is not None:
            try:
                if win32gui.IsWindow(hwnd):
                    win32gui.PostMessage(hwnd, _WM_REDRAW, 0, 0)
            except pywintypes.error as exc:
                logger.warning(f"Could not request an overlay redraw: {exc}")

    def overlay_clear(self):
        with self._lock:
            self._lines.clear()
            self._text.clear()
            self._floating_text.clear()
            self._progress = None

    def overlay_remove_rect(self, key):
        with self._lock:
            self._lines.pop(key, None)

    def overlay_remove_text(self, key):
        with self._lock:
            self._text.pop(key, None)

    def overlay_remove_floating_text(self, key):
        with self._lock:
            self._floating_text.pop(key, None)

    def overlay_quit(self):
        self._stop_event.set()


def main():
    ov = Overlay("", 0)
    rect = {
        "a": [(50, 50), (500, 500), (120, 255, 0), 2],
        "b": [(800, 800), (1000, 1000), (20, 10, 255), 15],
        "c": [(220, 30), (350, 700), (255, 20, 10), 1],
    }

    ov.overlay_setfont("Times New Roman", 12)
    ov.overlay_set_pos(2000, 50)
    ov.overlay_text("1", "Hello World", 1, 1, (0, 0, 255))
    ov.overlay_text("2", "next test in line", 2, 1, (255, 0, 255))

    for key, value in rect.items():
        ov.overlay_rect(key, value[0], value[1], value[2], value[3])

    ov.overlay_paint()
    time.sleep(5)
    ov.overlay_quit()


if __name__ == "__main__":
    main()
