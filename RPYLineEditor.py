from __future__ import annotations

from copy import copy
from tkinter import messagebox
import numpy as np
from matplotlib.lines import Line2D


def line_editor(curve: dict[str, float]) -> dict[str, float] | None:
    """ A line editor. The input data is in the following format.
    The key is a string representing the angle in degree:
        PitchRate = {
        "0.5": 6.0,
        "1.0": 10.47,
        "2.5": 16.81,
        "4.3": 21.9,
        "9.3": 27.22,
        "30.0": 39.7
    }
    @param curve: The dict of line data.
    @return: The changed dict or None.
    """
    import matplotlib.pyplot as plt

    if curve is None:
        return None

    # print(f"Original curve: {curve}")

    sorted_curve = convert_curve_to_float(curve)

    # print(f"Sorted curve: {sorted_curve}")

    xs = list(sorted_curve.keys())
    ys = list(sorted_curve.values())

    fig, ax1 = plt.subplots()
    line = Line2D(xs, ys,
                  marker='o', markerfacecolor='r',
                  animated=True, figure=fig)
    old = copy(line.get_xydata())

    p = LineInteractor(ax1, line)

    ax1.set_title('Click and drag a point to move it\n\'i\' to insert, \'d\' to delete a point')
    ax1.set_xlabel('Dist to Target (Deg)')
    ax1.set_ylabel('RPY Rate (Deg/Sec)')
    ax1.set_xlim(auto=True)
    ax1.set_ylim(auto=True)
    ax1.autoscale_view()

    plt.show(block=True)

    # Get the line which may have been changed.
    new_xys = p.line.get_xydata()

    if np.array_equal(new_xys, old):
        return None
    else:
        # Recreate original dict structure
        updated_curve: dict[str, float] = {}
        for item in p.line.get_xydata():
            # Add to dict in format [str, float] format
            updated_curve[str(round(item[0], 1))] = round(float(item[1]), 2)

        # print(f"Updated curve: {updated_curve}")
        return updated_curve


def convert_curve_to_float(curve: dict[str, float]) -> dict[float, float] | None:
    """
    Converts the [str, float] dictionary to [float, float] and sorts it ascending.
    This is because it is stored in as json, where the key must be a string.
    So ['0.5', 23.4]  becomes [0.5, 23.4]
    @param curve:
    @return:
    """
    # Convert each item to float
    curve_float = {float(k): v for k, v in curve.items()}
    # Sort the curve by angle (sorts ascending)
    sorted_curve = dict(sorted(curve_float.items()))
    return sorted_curve


def convert_curve_to_str(curve: dict[float, float]) -> dict[str, float] | None:
    """
    Converts the [float, float] dictionary to [str, float].
    This allows it to be stored in as json, where the key must be a string.
    So [0.5, 23.4]  becomes ['0.5', 23.4]
    @param curve:
    @return:
    """
    # Sort the curve by angle (sorts ascending)
    sorted_curve = dict(sorted(curve.items()))
    # Recreate original dict structure
    curve_str = {str(k): v for k, v in sorted_curve.items()}
    return curve_str


def round_to_multiple(number: float, multiple: float) -> float:
    """
    Round a number to an interval. For example if number=153 and multiple=5, return value us 155.
    @param number: Number to round.
    @param multiple: The interval to use.
    @return: The rounded result.
    """
    if multiple >= 1:
        return multiple * round(number / multiple)
    elif multiple >= 0.1:
        return multiple * round((number * 10) / (multiple * 10))


def closest_angle(angle: float) -> float:
    """
    Rounds an angle to the desired interval. This limits the number of angles stored, by rounding
    to 1, 2, 5, 10, 15 etc.
    @param angle: Angle to round.
    @return: Rounded value.
    """
    if angle > 60:
        a = round_to_multiple(angle, 20)
    elif angle > 30:
        a = round_to_multiple(angle, 10)
    elif angle > 15:
        a = round_to_multiple(angle, 5)
    elif angle > 5:
        a = round_to_multiple(angle, 1)
    else:
        a = round_to_multiple(angle, 0.25)
    return a


class LineInteractor:
    """
    A line editor.
    Original code from Poly Editor: https://matplotlib.org/stable/gallery/event_handling/poly_editor.html

    Key-bindings

      'd' delete the vertex under point

      'i' insert a vertex at point.  You must be within epsilon of the
          line connecting two existing vertices

    """

    epsilon = 5  # max pixel distance to count as a vertex hit

    def __init__(self, ax, line2d):
        if line2d.figure is None:
            raise RuntimeError('You must first add the line to a figure '
                               'or canvas before defining the interactor')
        self.background = None
        self.ax = ax
        self.line = line2d
        self.ax.add_line(self.line)
        self._ind = None  # the active vert

        canvas = line2d.figure.canvas
        canvas.mpl_connect('draw_event', self.on_draw)
        canvas.mpl_connect('button_press_event', self.on_button_press)
        canvas.mpl_connect('key_press_event', self.on_key_press)
        canvas.mpl_connect('button_release_event', self.on_button_release)
        canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas = canvas

    @staticmethod
    def dist_point_to_segment(p: [float, float], s0, s1):
        """
        Get the distance from the point *p* to the segment (*s0*, *s1*), where
        *p*, *s0*, *s1* are ``[x, y]`` arrays.
        """
        s01 = s1 - s0
        s0p = p - s0
        if (s01 == 0).all():
            return np.hypot(*s0p)
        # Project onto segment, without going past segment ends.
        p1 = s0 + np.clip((s0p @ s01) / (s01 @ s01), 0, 1) * s01
        return np.hypot(*(p - p1))

    def on_draw(self, event):
        self.background = self.canvas.copy_from_bbox(self.ax.bbox)
        self.ax.draw_artist(self.line)

    def get_ind_under_point(self, event):
        """
        Return the index of the point closest to the event position or *None*
        if no point is within ``self.epsilon`` to the event position.
        """
        # display co-ords
        xy = np.asarray(self.line.get_xydata())
        xyt = self.line.get_transform().transform(xy)
        xt, yt = xyt[:, 0], xyt[:, 1]
        d = np.hypot(xt - event.x, yt - event.y)
        ind_seq, = np.nonzero(d == d.min())
        ind = ind_seq[0]

        if d[ind] >= self.epsilon:
            ind = None

        return ind

    def on_button_press(self, event):
        """Callback for mouse button presses."""
        if event.inaxes is None:
            return
        if event.button != 1:
            return
        self._ind = self.get_ind_under_point(event)

    def on_button_release(self, event):
        """Callback for mouse button releases."""
        if event.button != 1:
            return
        self._ind = None

    def on_key_press(self, event):
        """Callback for key presses."""
        if not event.inaxes:
            return
        elif event.key == 'd':
            ind = self.get_ind_under_point(event)
            if ind is not None:
                updated_xys = np.delete(self.line.get_xydata(), ind, axis=0)
                self.line.set_data(zip(*updated_xys))
        elif event.key == 'i':
            xys = self.line.get_transform().transform(self.line.get_xydata())
            p = event.x, event.y  # display co-ords
            best_i = -1
            best_d = -1
            for i in range(len(xys) - 1):
                s0 = xys[i]
                s1 = xys[i + 1]
                d = self.dist_point_to_segment(p, s0, s1)
                # Check if this is closer segment
                if d < best_d or best_d == -1:
                    best_i = i
                    best_d = d

            if best_i > -1:
                updated_xys = np.insert(
                    self.line.get_xydata(), best_i + 1,
                    [event.xdata, event.ydata],
                    axis=0)
                self.line.set_data(zip(*updated_xys))

        if self.line.stale:
            self.canvas.draw_idle()

    def on_mouse_move(self, event):
        """Callback for mouse movements."""
        if self._ind is None:
            return
        if event.inaxes is None:
            return
        if event.button != 1:
            return
        x, y = event.xdata, event.ydata

        xys = self.line.get_xydata()
        # Update co-ords of edited index
        xys[self._ind] = [x, y]
        # Write data back to line
        self.line.set_data(zip(*xys))

        self.canvas.restore_region(self.background)
        self.ax.draw_artist(self.line)
        self.canvas.blit(self.ax.bbox)


def main():
    print(f"Round 0.3: {closest_angle(0.3)}")
    print(f"Round 0.8: {closest_angle(0.8)}")
    print(f"Round 1.6: {closest_angle(1.6)}")
    print(f"Round 6.65: {closest_angle(6.65)}")
    print(f"Round 16.65: {closest_angle(16.65)}")
    print(f"Round 36.65: {closest_angle(36.65)}")
    print(f"Round 66.65: {closest_angle(66.65)}")

    PitchRate = {
        "0.5": 6.0,
        "1.0": 10.47,
        "5.5": 16.81,
        "4.3": 21.9,
        "9.3": 27.22,
        "30.0": 39.7,
        "60.0": 39.7
    }
    # print(f"old arr: {PitchRate}")

    # Test convert and revert
    y1 = convert_curve_to_float(PitchRate)
    x1 = convert_curve_to_str(y1)

    new_arr = line_editor(PitchRate)
    if new_arr is not None:
        print("Line changed")
        # print(f"new arr: {new_arr}")
        if messagebox.askyesno("RPY calibration", "Keep the changes made to calibration?"):
            messagebox.showinfo("EDAP", "Save configuration changes once complete.")
    else:
        print("Line is same")


if __name__ == "__main__":
    main()
