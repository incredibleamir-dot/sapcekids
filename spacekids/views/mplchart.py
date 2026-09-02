"""MplChart: a theme-aware matplotlib Figure embedded in PySide6.

Used below the PyVista 3D view for contour plots, cost curves, and
other data-viz charts.  Automatically syncs with the active Space Kids
palette so text, axes, and backgrounds match the dark/light theme.
"""

import matplotlib
matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from .. import theme


def _theme_mpl_colors():
    """Return a dict of matplotlib-ready colours from the active palette."""
    return {
        "bg": theme.BG,
        "panel": theme.PANEL,
        "text": theme.TEXT,
        "text_mut": theme.TEXT_MUT,
        "accent": theme.ACCENT,
        "ok": theme.OK,
        "warn": theme.WARN,
        "err": theme.ERR,
        "grid": theme.GRID,
        "border": theme.BORDER,
    }


class MplChart(FigureCanvasQTAgg):
    """A matplotlib canvas that respects the current Space Kids theme.

    Usage::

        chart = MplChart(figsize=(6, 3))
        ax = chart.axes
        ax.plot(x, y, color=chart.color("accent"))
        chart.refresh()          # redraw
        chart.refresh_theme()    # call on palette switch
    """

    def __init__(self, figsize=(6, 2.8), parent=None):
        self._fig = Figure(figsize=figsize, dpi=100)
        super().__init__(self._fig)
        self.setParent(parent)
        self.axes = self._fig.add_subplot(111)
        self._apply_theme()

    # ----------------------------------------------------------- helpers
    def color(self, name):
        """Return an RGB tuple for a palette key (e.g. 'accent', 'ok')."""
        return _theme_mpl_colors().get(name, (0.7, 0.7, 0.7))

    def color_hex(self, name):
        return _theme_mpl_colors().get(name, "#aaaaaa")

    def refresh(self):
        self._fig.tight_layout(pad=1.2)
        self.draw()

    def refresh_theme(self):
        self._apply_theme()
        self.refresh()

    def _apply_theme(self):
        c = _theme_mpl_colors()
        self._fig.patch.set_facecolor(c["bg"])
        ax = self.axes
        ax.set_facecolor(c["panel"])
        for spine in ax.spines.values():
            spine.set_color(c["border"])
        ax.tick_params(colors=c["text_mut"], labelsize=8)
        ax.xaxis.label.set_color(c["text_mut"])
        ax.yaxis.label.set_color(c["text_mut"])
        ax.title.set_color(c["text"])
        ax.title.set_fontsize(10)
        ax.title.set_fontweight("bold")
        ax.grid(True, color=c["grid"], linewidth=0.5, alpha=0.6)

    def clear_plot(self):
        self._fig.clear()
        self.axes = self._fig.add_subplot(111)
        self._apply_theme()
