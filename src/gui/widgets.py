"""Custom widgets of the dark user interface."""

import tkinter as tk

import ttkbootstrap as ttk

from gui.theme import (
    BLUE,
    CARD,
    DISABLED,
    FIELD,
    ICONS,
    LINE,
    ORANGE,
    PANEL,
    RED,
    RED_HOVER,
    TEXT,
    icon_font,
    rounded_image,
)


def section_card(app, parent, title):
    label = tk.Label(parent, text=title, fg=BLUE, bg=app.theme.surface, font=("TkDefaultFont", 10, "bold"))
    card = ttk.LabelFrame(parent, labelwidget=label, padding=app.metrics.u(12))
    card.pack(fill="x", pady=(0, app.metrics.u(10)))
    card.columnconfigure(0, weight=1)
    return card


class DarkToolTip(ttk.ToolTip):
    """ttkbootstrap redefines the tooltip style with its own light colors, so the label is colored directly."""

    def _apply_label_style(self):
        if self._label is not None:
            ttk.Style().configure("Dark.Tooltip.TLabel", background=CARD, foreground=TEXT, bordercolor=LINE)
            self._label.configure(style="Dark.Tooltip.TLabel", borderwidth=1, relief="solid")


def add_tooltip(widget, text):
    """Show a tooltip after hovering for one second. Empty texts are ignored."""
    if text:
        return DarkToolTip(widget, text=text, delay=1000)
    return None


class RoundButton(tk.Canvas):
    """Button with an optional icon, a caption, small rounded corners and a border; can shrink to the icon only."""

    def __init__(self, master, metrics, icon, text="", command=None, danger=False, framed=True, bg=PANEL):
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, cursor="hand2", height=metrics.px(36))
        self.metrics = metrics
        self.caption = text
        self.command = command
        self.danger = danger
        self.framed = framed
        self.active = False
        self.disabled = False
        self.hover = False
        self.icon_only = bool(icon) and not text
        self.shape = self.create_image(0, 0, anchor="nw")
        self.icon_item = self.create_text(0, 0, text=ICONS[icon] if icon else "", font=(icon_font(self), 12))
        self.text_item = self.create_text(0, 0, text=text, anchor="w", font="TkDefaultFont")
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))

    def _click(self, event):
        self.invoke()

    def invoke(self):
        if self.command and not self.disabled:
            return self.command()

    def _set_hover(self, value):
        self.hover = value
        self.redraw()

    def set_active(self, value):
        self.active = value
        self.redraw()

    def set_disabled(self, value):
        self.disabled = value
        self.configure(cursor="arrow" if value else "hand2")
        self.redraw()

    def set_icon(self, name):
        self.itemconfigure(self.icon_item, text=ICONS[name])

    def set_icon_only(self, value):
        self.icon_only = (value or not self.caption) and self.has_icon
        self.redraw()

    @property
    def has_icon(self):
        return bool(self.itemcget(self.icon_item, "text"))

    def _colors(self):
        hover = self.hover and not self.disabled
        if self.active:
            return ORANGE, ORANGE
        if self.danger:
            return (RED_HOVER if hover else RED), RED
        if self.framed:
            return (FIELD if hover else CARD), (ORANGE if hover else LINE)
        return ((FIELD if hover else None), None)

    def redraw(self):
        width, height = self.winfo_width(), self.winfo_height()
        if width < 4 or height < 4:
            return
        fill, line = self._colors()
        if fill is None:
            self.itemconfigure(self.shape, image="")
        else:
            self.itemconfigure(
                self.shape, image=rounded_image(width, height, self.metrics.px(6), fill, line, master=self)
            )
        color = DISABLED if self.disabled else TEXT
        self.itemconfigure(self.icon_item, fill=color)
        self.itemconfigure(self.text_item, fill=color)
        if not self.has_icon:
            self.coords(self.text_item, width // 2, height // 2)
            self.itemconfigure(self.text_item, anchor="center", state="normal")
        elif self.icon_only:
            self.coords(self.icon_item, width // 2, height // 2)
            self.itemconfigure(self.text_item, state="hidden")
        else:
            self.coords(self.icon_item, self.metrics.px(22), height // 2)
            self.coords(self.text_item, self.metrics.px(42), height // 2)
            self.itemconfigure(self.text_item, anchor="w", state="normal")
