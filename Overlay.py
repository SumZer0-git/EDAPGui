import threading
from copy import copy
from ctypes.wintypes import PRECT
from datetime import datetime
from time import sleep

import win32api
import win32con
import win32gui
import win32ui
from Screen_Regions import Quad, Point

"""
File:Overlay.py    

Description:
  Class to support drawing lines and text which would overlay the parent screen

Author: sumzer0@yahoo.com

to use:
ov = Overlay("")
# key = a string to be any identifier you want it to be
ov.overlay_rect(key, (pt[0]+x_start, pt[1]+y_start), (pt[0] + compass_width+x_start, pt[1] + compass_height+y_start), (R,G,B), thinkness)

ov.overlay_setfont("Times New Roman", 12 )
ov.overlay_set_pos(2000, 50)
#                                        row,col, color   based on fontSize
ov.overlay_text('1', "Hello World",       1, 1,(0,0,255) )

ov.overlay_paint()

#@end
ov.overlay_quit()
"""

lines = {}
text = {}
floating_text = {}
quadrilaterals = {}
fnt = ["Times New Roman", 12, 12]
pos = [0,0]
elite_dangerous_window = "Elite - Dangerous (CLIENT)"

class Vector:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
    def __ne__(self, other):
        this = self.x + self.y + self.w + self.h
        _other = other.x + other.y + other.w + other.h
        return this != _other

class Overlay:
       
    def __init__(self, parent_window, elite=0):

        self.parent = parent_window
        if elite == 1:
            self.parent = elite_dangerous_window
        
        self.hWindow = None
        self.overlay_thr = threading.Thread(target=self.overlay_win32_run)
        self.overlay_thr.setDaemon(False)
        self.overlay_thr.start()
        self.targetRect = Vector(0, 0, 1920, 1200)
        self.tHwnd = None
        self._overlay_update_thread = threading.Thread(target=self._overlay_cleanup_loop, daemon=True)
        self._overlay_update_thread.start()

    def overlay_win32_run(self):
        hInstance = win32api.GetModuleHandle()
        className = 'OverlayClassName'
        hWndParent = None

        if self.parent != "":
            self.tHwnd= win32gui.FindWindow(None, self.parent)
            if self.tHwnd:
                rect = win32gui.GetWindowRect(self.tHwnd)
                self.targetRect = Vector(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])

        wndClass                = win32gui.WNDCLASS()

        wndClass.style          = win32con.CS_HREDRAW | win32con.CS_VREDRAW
        wndClass.lpfnWndProc    = self.wndProc
        wndClass.hInstance      = hInstance
        wndClass.hCursor        = win32gui.LoadCursor(None, win32con.IDC_ARROW)
        wndClass.hbrBackground  = win32gui.GetStockObject(win32con.WHITE_BRUSH)
        wndClass.lpszClassName  = className

        wndClassAtom = win32gui.RegisterClass(wndClass)

        exStyle = win32con.WS_EX_COMPOSITED | win32con.WS_EX_LAYERED | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOPMOST | win32con.WS_EX_TRANSPARENT

        style = win32con.WS_DISABLED | win32con.WS_POPUP | win32con.WS_VISIBLE

        self.hWindow = win32gui.CreateWindowEx(
            exStyle,
            wndClassAtom,
            None, # WindowName
            style,
            0, # x
            0, # y
            win32api.GetSystemMetrics(win32con.SM_CXSCREEN), # width
            win32api.GetSystemMetrics(win32con.SM_CYSCREEN), # height
            hWndParent, # hWndParent
            None, # hMenu
            hInstance,
            None # lpParam
        )

        win32gui.SetLayeredWindowAttributes(self.hWindow, 0x00ffffff, 255, win32con.LWA_COLORKEY | win32con.LWA_ALPHA)

        win32gui.SetWindowPos(self.hWindow, win32con.HWND_TOPMOST, 0, 0, 0, 0,
            win32con.SWP_NOACTIVATE | win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)

        # If a parent was specified, and we found it move our window over that window
        if self.tHwnd != None:
            win32gui.MoveWindow(self.hWindow, self.targetRect.x, self.targetRect.y, self.targetRect.w, self.targetRect.h, True)


        # Dispatch messages, this function needs to be its own task to run forever until Quit
        win32gui.PumpMessages()

    def _GetTargetWindowRect(self):
        rect = win32gui.GetWindowRect(self.tHwnd)
        ret = Vector(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
        return ret

    def overlay_rect(self, key, pt1, pt2, color, thick, duration: float = 3.0):
        """ Adds a rectangle overlay. Does not force a redraw.
        @duration: Duration to display overlay in secs before it is removed, or <0.0 to prevent removal. """
        global lines
        lines[key] = [pt1, pt2, color, thick, duration, datetime.now()]

    def overlay_rect1(self, key, rect, color, thick, duration: float = 3.0):
        """ Adds a rectangle overlay. Does not force a redraw.
        @duration: Duration to display overlay in secs before it is removed, or <0.0 to prevent removal. """
        global lines
        lines[key] = [(rect[0], rect[1]), (rect[2], rect[3]), color, thick, duration, datetime.now()]

    def overlay_quad_pct(self, key, quad: Quad, color, thick, duration: float = 3.0):
        """ Adds a quadrilateral overlay. Does not force a redraw.
        @param key: Name of the overlay.
        @param quad: The quadrilateral to display in % (0.0 - 1.0).
        @param color: The color.
        @param thick: The line thickness.
        @param duration: The duration in seconds to display until removed, or <0.0 to prevent removal.
        @duration: Duration to display overlay in secs before it is removed, or <0.0 to prevent removal. """
        global quadrilaterals
        q = copy(quad)
        q.scale_from_origin(self.targetRect.w, self.targetRect.h)
        quadrilaterals[key] = [q, color, thick, duration, datetime.now()]

    @staticmethod
    def overlay_quad_pix(key, quad: Quad, color, thick, duration: float = 3.0):
        """ Adds a quadrilateral overlay. Does not force a redraw.
        @param key: Name of the overlay.
        @param quad: The quadrilateral to display in pixels.
        @param color: The color.
        @param thick: The line thickness.
        @param duration: The duration in seconds to display until removed, or <0.0 to prevent removal.
        @duration: Duration to display overlay in secs before it is removed, or <0.0 to prevent removal. """
        global quadrilaterals
        quadrilaterals[key] = [quad, color, thick, duration, datetime.now()]

    def overlay_setfont(self, fontname, fsize ):
        global fnt
        fnt = [fontname, fsize, fsize]

    def overlay_set_pos(self, x, y):
        global pos
        pos = [x, y]

    def overlay_text(self, key, txt, row, col, color, duration: float = 3.0):
        """ Adds a text overlay. Does not force a redraw.
        @duration: Duration to display overlay in secs before it is removed, or <0.0 to prevent removal. """
        global text
        text[key] = [txt, row, col, color, duration, datetime.now()]

    def overlay_floating_text(self, key, txt, x, y, color, duration: float = 3.0):
        """ Adds a floating text overlay. Does not force a redraw.
        @duration: Duration to display overlay in secs before it is removed, or <0.0 to prevent removal. """
        global floating_text
        floating_text[key] = [txt, x, y, color, duration, datetime.now()]

    def overlay_paint(self):
        """ Forces a redraw of all overlays. Call after adding or removing an overlay. """
        # if a parent was specified check to see if it moved, if so reposition our origin to new window location
        if self.tHwnd:
            if self.targetRect != self._GetTargetWindowRect():
                rect = win32gui.GetWindowRect(self.tHwnd)
                self.targetRect = Vector(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
                win32gui.MoveWindow(self.hWindow, self.targetRect.x, self.targetRect.y, self.targetRect.w, self.targetRect.h, True)

        win32gui.RedrawWindow(self.hWindow, None, None, win32con.RDW_INVALIDATE | win32con.RDW_ERASE) 

    def overlay_clear(self):
        """ Removes rectangle, text and floating text overlays. Does not force a redraw."""
        lines.clear()
        quadrilaterals.clear()
        text.clear()
        floating_text.clear()

    def overlay_remove_rect(self, key):
        """ Removes a rectangle overlay. Does not force a redraw."""
        if key in lines:
            lines.pop(key)

    def overlay_remove_quad(self, key):
        """ Removes a quadrilateral overlay. Does not force a redraw."""
        if key in quadrilaterals:
            quadrilaterals.pop(key)

    def overlay_remove_text(self, key):
        """ Removes a text overlay. Does not force a redraw."""
        if key in text:
            text.pop(key)

    def overlay_remove_floating_text(self, key):
        """ Removes a floating text overlay. Does not force a redraw."""
        if key in floating_text:
            floating_text.pop(key)

    def overlay_quit(self):
        win32gui.PostMessage(self.hWindow, win32con.WM_CLOSE, 0, 0)

    def _overlay_cleanup_loop(self):
        """ Cleans up the overlay by removing overlays that are old from the list. """
        global lines, quadrilaterals, text, floating_text
        while 1:
            # Check each list and remove items that are old
            time_now = datetime.now()
            force_redraw = False

            # Check lines
            for key in list(lines):
                # Check the datetime diff between when the overlay was added and now
                time_diff = (time_now - lines[key][5]).total_seconds()
                # Remove overlay if it is too old. Keep overlay if dur < 0
                if 0 < lines[key][4] < time_diff:
                    del lines[key]
                    force_redraw = True

            # Check quadrilaterals
            for key in list(quadrilaterals):
                # Check the datetime diff between when the overlay was added and now
                time_diff = (time_now - quadrilaterals[key][4]).total_seconds()
                # Remove overlay if it is too old. Keep overlay if dur < 0
                if 0 < quadrilaterals[key][3] < time_diff:
                    del quadrilaterals[key]
                    force_redraw = True

            # Check text
            for key in list(text):
                # Check the datetime diff between when the overlay was added and now
                time_diff = (time_now - text[key][5]).total_seconds()
                # Remove overlay if it is too old. Keep overlay if dur < 0
                if 0 < text[key][4] < time_diff:
                    del text[key]
                    force_redraw = True

            # Check floating_text
            for key in list(floating_text):
                # Check the datetime diff between when the overlay was added and now
                time_diff = (time_now - floating_text[key][5]).total_seconds()
                # Remove overlay if it is too old. Keep overlay if dur < 0
                if 0 < floating_text[key][4] < time_diff:
                    del floating_text[key]
                    force_redraw = True

            if force_redraw:
                self.overlay_paint()

            sleep(0.5)

    @staticmethod 
    def overlay_draw_rect(hdc, pt1, pt2, line_type, color, thick):
        wid = int(pt2[0] - pt1[0])
        hgt = int(pt2[1] - pt1[1])

        pin_thick = win32gui.CreatePen(line_type, thick, win32api.RGB(color[0], color[1], color[2]))
        pin_thin  = win32gui.CreatePen(line_type, 1, win32api.RGB(color[0], color[1], color[2]))
   
        if wid < 20:
            win32gui.SelectObject(hdc, pin_thin)
            win32gui.Rectangle(hdc, int(pt1[0]), int(pt1[1]), int(pt2[0]), int(pt2[1]))
        else:
            len_wid = wid / 5
            len_hgt = hgt / 5
            half_wid = wid/ 2
            half_hgt = hgt/ 2
            tic_len = thick-1
            # top
            win32gui.SelectObject(hdc, pin_thick)
            win32gui.MoveToEx(hdc, int(pt1[0]),             int(pt1[1]))
            win32gui.LineTo  (hdc, int(pt1[0]+len_wid),     int(pt1[1]))

            win32gui.SelectObject(hdc, pin_thin)
            win32gui.MoveToEx(hdc, int(pt1[0]+(2*len_wid)), int(pt1[1]))
            win32gui.LineTo  (hdc, int(pt1[0]+(3*len_wid)), int(pt1[1]))

            win32gui.SelectObject(hdc, pin_thick)
            win32gui.MoveToEx(hdc, int(pt1[0]+(4*len_wid)), int(pt1[1]))
            win32gui.LineTo  (hdc, int(pt2[0]),             int(pt1[1]))

            # top tic
            win32gui.MoveToEx(hdc, int(pt1[0]+half_wid),    int(pt1[1]))
            win32gui.LineTo  (hdc, int(pt1[0]+half_wid),    int(pt1[1])-tic_len)

            # bot
            win32gui.MoveToEx(hdc, int(pt1[0]),             int(pt2[1]))
            win32gui.LineTo  (hdc, int(pt1[0]+len_wid),     int(pt2[1]))

            win32gui.SelectObject(hdc, pin_thin)
            win32gui.MoveToEx(hdc, int(pt1[0]+(2*len_wid)), int(pt2[1]))
            win32gui.LineTo  (hdc, int(pt1[0]+(3*len_wid)), int(pt2[1]))

            win32gui.SelectObject(hdc, pin_thick)
            win32gui.MoveToEx(hdc, int(pt1[0]+(4*len_wid)), int(pt2[1]))
            win32gui.LineTo  (hdc, int(pt2[0]),             int(pt2[1]))
            # bot tic
            win32gui.MoveToEx(hdc, int(pt1[0]+half_wid),    int(pt2[1]))
            win32gui.LineTo  (hdc, int(pt1[0]+half_wid),    int(pt2[1])+tic_len)

            # left
            win32gui.MoveToEx(hdc, int(pt1[0]),  int(pt1[1]))
            win32gui.LineTo  (hdc, int(pt1[0]),  int(pt1[1]+len_hgt))

            win32gui.SelectObject(hdc, pin_thin)
            win32gui.MoveToEx(hdc, int(pt1[0]),  int(pt1[1]+(2*len_hgt)))
            win32gui.LineTo  (hdc, int(pt1[0]),  int(pt1[1]+(3*len_hgt)))

            win32gui.SelectObject(hdc, pin_thick)
            win32gui.MoveToEx(hdc, int(pt1[0]),  int(pt1[1]+(4*len_hgt)))
            win32gui.LineTo  (hdc, int(pt1[0]),  int(pt2[1]))

            # left tic
            win32gui.MoveToEx(hdc, int(pt1[0]),          int(pt1[1]+half_hgt))
            win32gui.LineTo  (hdc, int(pt1[0]-tic_len),  int(pt1[1]+half_hgt))

            # right
            win32gui.MoveToEx(hdc, int(pt2[0]),  int(pt1[1]))
            win32gui.LineTo  (hdc, int(pt2[0]),  int(pt1[1]+len_hgt))

            win32gui.SelectObject(hdc, pin_thin)
            win32gui.MoveToEx(hdc, int(pt2[0]),  int(pt1[1]+(2*len_hgt)))
            win32gui.LineTo  (hdc, int(pt2[0]),  int(pt1[1]+(3*len_hgt)))

            win32gui.SelectObject(hdc, pin_thick)
            win32gui.MoveToEx(hdc, int(pt2[0]),  int(pt1[1]+(4*len_hgt)))
            win32gui.LineTo  (hdc, int(pt2[0]),  int(pt2[1]))
            # right tic
            win32gui.MoveToEx(hdc, int(pt2[0]),    int(pt1[1]+half_hgt))
            win32gui.LineTo  (hdc, int(pt2[0]+tic_len),   int(pt1[1]+half_hgt))

    @staticmethod
    def overlay_draw_quad(hdc, quad: Quad, line_type, color, thick):
        pin_thick = win32gui.CreatePen(line_type, thick, win32api.RGB(color[0], color[1], color[2]))
        pin_thin = win32gui.CreatePen(line_type, 1, win32api.RGB(color[0], color[1], color[2]))

        # top
        win32gui.SelectObject(hdc, pin_thick)
        win32gui.MoveToEx(hdc, int(quad.pt1.get_x()), int(quad.pt1.get_y()))
        win32gui.LineTo(hdc, int(quad.pt2.get_x()), int(quad.pt2.get_y()))
        win32gui.LineTo(hdc, int(quad.pt3.get_x()), int(quad.pt3.get_y()))
        win32gui.LineTo(hdc, int(quad.pt4.get_x()), int(quad.pt4.get_y()))
        win32gui.LineTo(hdc, int(quad.pt1.get_x()), int(quad.pt1.get_y()))

    @staticmethod 
    def overlay_set_font(hdc, fontname, fontSize):
        global fnt
        dpiScale = win32ui.GetDeviceCaps(hdc, win32con.LOGPIXELSX) / 60.0

        lf = win32gui.LOGFONT()
        lf.lfFaceName = fontname
        lf.lfHeight = int(round(dpiScale * fontSize))
        #lf.lfWeight = 150
        # Use nonantialiased to remove the white edges around the text.
        lf.lfQuality = win32con.NONANTIALIASED_QUALITY
        hf = win32gui.CreateFontIndirect(lf)
        win32gui.SelectObject(hdc, hf)
        fnt[2] = lf.lfHeight

    @staticmethod 
    def overlay_draw_text(hWnd, hdc, txt, row, col, color):
        global pos, fnt

        x = pos[0]+col*fnt[1]
        y = pos[1]+row*fnt[2]
        rect = (x, y, 1, 1) 
        win32gui.SetTextColor(hdc,win32api.RGB(color[0], color[1], color[2]))    

        win32gui.DrawText(hdc,  txt,  -1,  rect,   win32con.DT_LEFT | win32con.DT_NOCLIP | win32con.DT_SINGLELINE | win32con.DT_TOP   )

    @staticmethod
    def overlay_draw_floating_text(hWnd, hdc, txt, x, y, color):
        rect = (int(x), int(y), 1, 1)
        win32gui.SetTextColor(hdc,win32api.RGB(color[0], color[1], color[2]))

        win32gui.DrawText(hdc,  txt,  -1,  rect,   win32con.DT_LEFT | win32con.DT_NOCLIP | win32con.DT_SINGLELINE | win32con.DT_TOP   )

    @staticmethod 
    def wndProc(hWnd, message, wParam, lParam):
        global lines, quadrilaterals, text
        if message == win32con.WM_PAINT:
            hdc, paintStruct = win32gui.BeginPaint(hWnd)

            Overlay.overlay_set_font(hdc, fnt[0], fnt[1])

            #for i, key in enumerate(lines):
            for key in list(lines.keys()):
                #print(lines[key])
                Overlay.overlay_draw_rect(hdc, lines[key][0], lines[key][1], win32con.PS_SOLID, lines[key][2], lines[key][3])

            #for i, key in enumerate(quadrilaterals):
            for key in list(quadrilaterals.keys()):
                #print(lines[key])
                Overlay.overlay_draw_quad(hdc, quadrilaterals[key][0], win32con.PS_SOLID, quadrilaterals[key][1],
                                          quadrilaterals[key][2])

            #for i, key in enumerate(text):
            for key in list(text.keys()):
                #print(text[key])
                Overlay.overlay_draw_text(hWnd, hdc, text[key][0], text[key][1], text[key][2], text[key][3])

            #for i, key in enumerate(floating_text):
            for key in list(floating_text.keys()):
                #print(text[key])
                Overlay.overlay_draw_floating_text(hWnd, hdc, floating_text[key][0], floating_text[key][1],
                                                   floating_text[key][2], floating_text[key][3])

            win32gui.EndPaint(hWnd, paintStruct)
            return 0

        elif message == win32con.WM_DESTROY:
            #print 'Closing the window.'
            win32gui.PostQuitMessage(0)
            return 0

        else:
            return win32gui.DefWindowProc(hWnd, message, wParam, lParam)


def main():
    ov = Overlay("",0)

    #       key    x,y       x,y end      color      thinkness
    rect = {'a': [(50,50), (500, 500), (120, 255, 0),2],
            'b': [(800,800), (1000, 1000), (20, 10, 255),15] ,
            'c': [(220,30), (350, 700), (255, 20, 10),1] 
           }
    #               TL            TR          BR        BL
    quad = {'a': [(.1, .1), (.3, .05), (.275, .45), (.15, .5), (120, 255, 0), 2]}

    ov.overlay_setfont("Times New Roman", 12 )
    ov.overlay_set_pos(2000, 50)
    #                                        row,col, color   based on fontSize
    ov.overlay_text('1', "Hello World",       1, 1,(0,0,255), -1)
    ov.overlay_text('2', "next test in line", 2, 1,(255,0,255), -1)

    for i, key in enumerate(rect):
        ov.overlay_rect(key, rect[key][0], rect[key][1], rect[key][2], rect[key][3], 5)
        print("Adding")
        print(rect[key])
    q = Quad(Point.from_xy(quad['a'][0]), Point.from_xy(quad['a'][1]),
             Point.from_xy(quad['a'][2]), Point.from_xy(quad['a'][3]))
    ov.overlay_quad_pct('a', q, quad['a'][4], quad['a'][5],5)
    ov.overlay_paint()

    sleep(5)
    rect['d'] = [(400,150), (900, 550), (255, 10, 255),25]
    ov.overlay_rect('d', rect['d'][0], rect['d'][1], rect['d'][2], rect['d'][3],5)
    ov.overlay_text('3', "Changed", 3, 3, (255, 0, 0), -1)
    ov.overlay_setfont("Times New Roman", 16)
    ov.overlay_set_pos(1800, 50)
    ov.overlay_paint() 

    sleep(5)
    rect['b'] = [(40,150), (90, 550), (155, 10, 255),10]
    ov.overlay_rect('b', rect['b'][0], rect['b'][1], rect['b'][2], rect['b'][3],5)
    ov.overlay_text('3', "", 3, 3,(255, 0, 0), -1)
    ov.overlay_paint()   
    sleep(5)
    ov.overlay_quit()
    sleep(2)

if __name__ == "__main__":
    main()




 