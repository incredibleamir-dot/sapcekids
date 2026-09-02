"""SpaceView: a friendly top-down orbital scene painter.

Draws heliocentric or Earth-centred scenes from a small declarative scene
model, then animates it with a QTimer.  Pages never touch QPainter; they just
describe what appears (paths, moving bodies, labels) and let this widget turn
it into a picture.  Uses only PySide6 QPainter so there are zero hard
dependencies beyond the GUI toolkit.
"""

import math
import random
import time as _time

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QPen, QRadialGradient,
                           QPolygonF)
from PySide6.QtWidgets import QWidget

from .. import theme
from ..settings import get as _setting


class Body:
    """A moving object on the scene: its centre is any callable given sim time."""

    __slots__ = ("pos_fn", "radius_km", "color", "label", "glow", "line",
                 "_last")

    def __init__(self, pos_fn, radius_km, color, label=None, glow=0.0, line=False):
        self.pos_fn = pos_fn
        self.radius_km = radius_km
        self.color = color
        self.label = label
        self.glow = glow
        self.line = line  # draw a small line along motion (rocket)
        self._last = None

    def position(self, t):
        p = self.pos_fn(t)
        self._last = tuple(float(v) for v in p)
        return self._last


def _jitter(rng, n, span):
    return [(rng.uniform(-span, span), rng.uniform(-span, span)) for _ in range(n)]


class SpaceView(QWidget):
    """Pans/zooms nothing - the page hands it the world.

    Scene items:
      * ``paths``  - list of dicts: points (n,3 km), color, width, label
      * ``bodies`` - list of ``Body``
      * ``axes``   - optional True to draw faint axes through the centre
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 300)
        self.setAutoFillBackground(False)

        self.paths = []
        self.bodies = []
        self.center = (0.0, 0.0)
        self.title = ""
        self.subtitle = ""
        self.pad = 44
        self.axes = True
        self.min_radius_km = 0.0   # force a minimum world radius (km)

        self.t = 0.0
        self.dt = 0.0
        self.playing = False
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 fps
        self._timer.timeout.connect(self._on_tick)

        self.set_stars(max(40, int(_setting("stars", 200))))
        self._world_radius = None
        self._needs_extent = True

        self._zoom = 1.0
        self._zoom_bounds = (0.25, 48.0)
        self._pan = QPointF(0.0, 0.0)
        self._drag_pos = None
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Wheel or +/- to zoom, drag to pan, 0 to reset")

    # ------------------------------------------------------------------ stars
    def set_stars(self, count):
        """Regenerate the backdrop star field (deterministic for a given
        count, so screenshots stay comparable)."""
        count = max(40, int(count))
        rng = random.Random(7)
        self._stars = _jitter(rng, int(count * 0.7), 0.5) + \
            _jitter(rng, int(count * 0.3), 0.5)
        self.update()

    # ------------------------------------------------------------------ zoom
    def zoom_in(self):
        self._set_zoom(self._zoom * 1.5)

    def zoom_out(self):
        self._set_zoom(self._zoom / 1.5)

    def zoom_reset(self):
        self._set_zoom(1.0)
        self._pan = QPointF(0.0, 0.0)
        self.update()

    def _set_zoom(self, z, anchor=None):
        z = max(self._zoom_bounds[0], min(self._zoom_bounds[1], z))
        if self._zoom == z:
            return
        if anchor is not None:
            w, h = self.width(), self.height()
            s0 = self._scale(w, h)
            if s0 > 1e-9 and w > 0 and h > 0:
                s1 = s0 * (z / self._zoom)
                cx0 = w / 2.0 + self._pan.x()
                cy0 = h / 2.0 + self._pan.y()
                wx = self.center[0] + (anchor.x() - cx0) / s0
                wy = self.center[1] + (cy0 - anchor.y()) / s0
                cx1 = anchor.x() - (wx - self.center[0]) * s1
                cy1 = anchor.y() + (wy - self.center[1]) * s1
                self._pan = QPointF(cx1 - w / 2.0, cy1 - h / 2.0)
        self._zoom = z
        self.update()

    def wheelEvent(self, ev):
        step = 1.5 if ev.angleDelta().y() > 0 else 1.0 / 1.5
        if ev.angleDelta().y() == 0:
            ev.ignore()
            return
        self._set_zoom(self._zoom * step, ev.position())
        ev.accept()

    def keyPressEvent(self, ev):
        key = ev.key()
        if key in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom_in()
            ev.accept()
            return
        if key in (Qt.Key_Minus, Qt.Key_Underscore):
            self.zoom_out()
            ev.accept()
            return
        if key in (Qt.Key_0, Qt.Key_R):
            self.zoom_reset()
            ev.accept()
            return
        super().keyPressEvent(ev)

    def _zoom_buttons(self, w):
        """(name, QRectF) list for the top-right zoom controls."""
        y0, h, gap = 8.0, 24.0, 6.0
        rects = []
        x = w - 24.0 - h * 1.05
        for name in ("zoom_in", "zoom_out", "zoom_reset"):
            rects.append((name, QRectF(x, y0, h, h)))
            x -= h + gap
        return rects

    def mousePressEvent(self, ev):
        pos = ev.position()
        for name, rect in self._zoom_buttons(self.width()):
            if rect.contains(pos):
                getattr(self, name)()
                ev.accept()
                return
        if ev.button() == Qt.LeftButton:
            self._drag_pos = pos
            self.setCursor(Qt.ClosedHandCursor)
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drag_pos is not None and ev.buttons() & Qt.LeftButton:
            pos = ev.position()
            d = pos - self._drag_pos
            self._drag_pos = pos
            self._pan = self._pan + d
            self.update()
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._drag_pos is not None:
            self._drag_pos = None
            self.setCursor(Qt.OpenHandCursor)
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.zoom_reset()
            ev.accept()
            return
        super().mouseDoubleClickEvent(ev)

    # ------------------------------------------------------------------ model
    def clear(self):
        self.paths = []
        self.bodies = []
        self.t = 0.0
        self.playing = False
        self._needs_extent = True
        self.update()

    def set_scene(self, paths, bodies, center=(0.0, 0.0), title="",
                  subtitle="", min_radius_km=0.0, view_axis=None):
        self.paths = paths or []
        self.bodies = bodies or []
        self.center = center
        self.title = title
        self.subtitle = subtitle
        self.min_radius_km = min_radius_km
        self.t = 0.0
        self._needs_extent = True
        self.update()

    def set_paths(self, paths):
        """Replace just the path list (kept for parity with OrbitalView3D)."""
        self.paths = paths or []
        self._needs_extent = True
        self.update()

    # ------------------------------------------------------------------ playback
    def play(self, on=True):
        self.playing = bool(on)
        if on:
            self._timer.start()
        else:
            self._timer.stop()

    def seek(self, t):
        self.t = float(t)
        self.update()

    def elapsed_frames(self, rate_hz=1.0):
        return int(self.t * rate_hz)

    def _on_tick(self):
        self.t += self.dt
        self.update()

    # ------------------------------------------------------------------ extent
    def world_radius(self):
        """Radius (km) needed to see every path from ``center``."""
        if not self._needs_extent and self._world_radius:
            return self._world_radius
        r = self.min_radius_km
        for p in self.paths:
            pts = p.get("points")
            if pts is None:
                continue
            a = pts[:, :2] - self.center
            d = float(((a * a).sum(axis=1)).max())
            if math.isfinite(d):
                r = max(r, math.sqrt(d))
        r = max(r, 1e-6)
        self._world_radius = r
        self._needs_extent = False
        return r

    def _scale(self, w, h):
        wr = self.world_radius()
        return float(min((w - 2 * self.pad) / (2 * wr),
                         (h - 2 * self.pad) / (2 * wr)) * self._zoom)

    def _to_px(self, x, y, s, cx, cy):
        return (cx + (x - self.center[0]) * s, cy - (y - self.center[1]) * s)

    def scene_point_to_px(self, xyz, w=None, h=None):
        w = w or self.width()
        h = h or self.height()
        s = self._scale(w, h)
        cx = w / 2.0 + self._pan.x()
        cy = h / 2.0 + self._pan.y()
        return self._to_px(float(xyz[0]), float(xyz[1]), s, cx, cy)

    def radius_to_px(self, radius_km, w=None, h=None):
        w = w or self.width()
        s = self._scale(w, h)
        return float(radius_km) * s

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        bg = QColor(theme.BG)
        sky = QColor("#0a1424")
        grad = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.7)
        grad.setColorAt(0.0, bg.lighter(106))
        grad.setColorAt(1.0, sky)
        painter.fillRect(QRectF(0, 0, w, h), grad)

        self._paint_stars(painter, w, h)
        s = self._scale(w, h)
        cx = w / 2.0 + self._pan.x()
        cy = h / 2.0 + self._pan.y()

        for b in self.bodies:  # refresh positions from sim time every frame
            b.position(self.t)

        if self.axes and self.paths:
            self._paint_axis(painter, cx, cy, s)
        self._paint_paths(painter, cx, cy, s)
        self._paint_bodies(painter, cx, cy, s)
        self._paint_titles(painter, w)
        self._paint_zoom_controls(painter, w)

    def _paint_zoom_controls(self, painter, w):
        labels = {"zoom_in": "+", "zoom_out": "\u2013", "zoom_reset": "0"}
        font = painter.font()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        for name, rect in self._zoom_buttons(w):
            painter.setPen(QPen(QColor(theme.BORDER), 1))
            painter.setBrush(QColor(theme.PANEL))
            painter.drawRoundedRect(rect, 5, 5)
            painter.setPen(QPen(QColor(theme.TEXT), 1))
            painter.drawText(rect, Qt.AlignCenter, labels[name])
        pct = painter.fontMetrics().horizontalAdvance
        text = "%0.0f%%" % (self._zoom * 100)
        painter.setPen(QPen(QColor(theme.TEXT_MUT), 1))
        painter.drawText(QRectF(8, 6, pct(text) + 12, 20),
                         Qt.AlignLeft | Qt.AlignVCenter, text)

    def _paint_stars(self, painter, w, h):
        painter.setPen(Qt.NoPen)
        for x, y in self._stars:
            sx = (x + 0.5) * w
            sy = (y + 0.5) * h
            tw = 0.35 + 0.5 * abs(math.sin(self.t / 17.0 + x * 9))
            painter.setBrush(QColor(255, 255, 255, int(90 + 120 * tw)))
            painter.drawEllipse(QPointF(sx, sy), 1.1, 1.1)

    def _paint_axis(self, painter, cx, cy, s):
        wr = self.world_radius()
        pen = QPen(QColor(theme.GRID), 1)
        pen.setStyle(Qt.DotLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        for k in (0.35, 0.7, 1.0, 1.4):
            r = wr * k * s
            painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.drawLine(QPointF(cx - wr * s, cy), QPointF(cx + wr * s, cy))
        painter.drawLine(QPointF(cx, cy - wr * s), QPointF(cx, cy + wr * s))

    def _paint_paths(self, painter, cx, cy, s):
        for p in self.paths:
            pts = p.get("points")
            if pts is None or len(pts) < 2:
                continue
            color = QColor(p.get("color", theme.C_TRAIL))
            pen = QPen(color, p.get("width", 1.6))
            pen.setStyle({0: Qt.SolidLine, 1: Qt.DashLine,
                          2: Qt.DotLine}.get(p.get("style", 0), Qt.SolidLine))
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            path = QPainterPath()
            started = False
            for r in pts:
                x, y = self._to_px(float(r[0]), float(r[1]), s, cx, cy)
                if not started:
                    path.moveTo(x, y)
                    started = True
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)

    def _paint_bodies(self, painter, cx, cy, s):
        for b in self.bodies:
            if b._last is None:
                continue
            x, y, _z = b._last
            px, py = self._to_px(x, y, s, cx, cy)
            r = max(1.6, b.radius_km * s)

            if b.color == "sun" or b.glow:
                glow_r = r * (5 if b.glow > 0 else 2.2)
                g = QRadialGradient(QPointF(px, py), max(glow_r, 1.0))
                gc = QColor(theme.C_SUN if b.color == "sun"
                            else QColor(b.color).lighter(130))
                g.setColorAt(0.0, QColor(gc.red(), gc.green(), gc.blue(), 170))
                g.setColorAt(1.0, QColor(gc.red(), gc.green(), gc.blue(), 0))
                painter.setPen(Qt.NoPen)
                painter.setBrush(g)
                painter.drawEllipse(QPointF(px, py), glow_r, glow_r)

            grad = QRadialGradient(QPointF(px - r * 0.35, py - r * 0.35), r * 2)
            base = QColor(b.color)
            grad.setColorAt(0.0, base.lighter(135))
            grad.setColorAt(1.0, base.darker(130))
            painter.setPen(QPen(QColor(base.lighter(115)), 1))
            painter.setBrush(grad)
            painter.drawEllipse(QPointF(px, py), r, r)

            if b.line:
                pen = QPen(QColor(theme.C_PROBE), max(2, r * 0.8))
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                painter.drawLine(QPointF(px, py),
                                 QPointF(px + r * 1.6, py - r * 1.1))

            if b.label:
                painter.setPen(QPen(QColor(theme.TEXT), 1))
                painter.drawText(QRectF(px - 90, py + r + 2, 180, 16),
                                 Qt.AlignHCenter, b.label)

    def _paint_titles(self, painter, w):
        if not (self.title or self.subtitle):
            return
        painter.setPen(QPen(QColor(theme.TEXT), 1))
        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        y = 22
        if self.title:
            painter.drawText(QRectF(6, 6, w - 12, 20), Qt.AlignHCenter,
                             self.title)
            y = 24
            font.setBold(False)
            font.setPointSize(9)
            painter.setFont(font)
            painter.setPen(QPen(QColor(theme.TEXT_MUT), 1))
        if self.subtitle:
            painter.drawText(QRectF(6, y, w - 12, 18), Qt.AlignHCenter,
                             self.subtitle)