"""MapView: an equirectangular world map for ground tracks and pass spotting.

The continents are drawn from the embedded 1-degree land raster (see
``spacekids.geo.world``), cached as a pixmap for speed.  Pages add polylines
(ground tracks) and points (satellites, towns) that are drawn on top.
"""

import math
import numpy as np

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .. import theme
from ..geo import world


class MapView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 240)
        self.tracks = []
        self.points = []
        self.highlights = []
        self.title = ""
        self._land = None
        self._zoom = 1.0
        self._zoom_bounds = (1.0, 32.0)
        self._pan = QPointF(0.0, 0.0)
        self._drag_pos = None
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Wheel or +/- to zoom, drag to pan, 0 to reset")

    # ------------------------------------------------------------------ zoom
    def zoom_in(self):
        self._set_zoom(self._zoom * 1.6)

    def zoom_out(self):
        self._set_zoom(self._zoom / 1.6)

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
            old = self._inner_rect(w, h)
            if old.width() > 1e-9 and old.height() > 1e-9 and w > 0 and h > 0:
                lon = (anchor.x() - old.x()) / old.width() * 360.0 - 180.0
                lat = 90.0 - (anchor.y() - old.y()) / old.height() * 180.0
                self._zoom = z
                new = self._inner_rect(w, h)
                nx = anchor.x() - (lon + 180.0) / 360.0 * new.width()
                ny = anchor.y() - (90.0 - lat) / 180.0 * new.height()
                self._pan = QPointF(nx - (w - new.width()) / 2.0,
                                    ny - (h - new.height()) / 2.0)
                self.update()
                return
        self._zoom = z
        self.update()

    def wheelEvent(self, ev):
        if ev.angleDelta().y() == 0:
            ev.ignore()
            return
        step = 1.6 if ev.angleDelta().y() > 0 else 1.0 / 1.6
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
        y0, h, gap = 8.0, 24.0, 6.0
        rects = []
        x = w - 50.0 - h * 1.05
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

    # ---------------------------------------------------------------- model
    def set_title(self, text):
        self.title = text
        self.update()

    def clear(self):
        self.tracks = []
        self.points = []
        self.highlights = []
        self.update()

    def add_track(self, lats, lons, color=theme.C_SAT, width=2.0, label=None):
        self.tracks.append(dict(lats=np.asarray(lats, float),
                                lons=np.asarray(lons, float),
                                color=color, width=width, label=label))
        self.update()

    def add_point(self, lat, lon, color=theme.C_EARTH, label=None, radius=4.0,
                  glow=False):
        self.points.append(dict(lat=float(lat), lon=float(lon), color=color,
                                label=label, radius=radius, glow=glow))
        self.update()

    def clear_points(self):
        self.points = []
        self.update()

    def add_highlight(self, lat, lon, color):
        self.highlights.append((float(lat), float(lon), color))
        self.update()

    # ---------------------------------------------------------------- layout
    def _inner_rect(self, w, h):
        """Fit the world map (2:1 aspect) centered inside the widget box."""
        full_w = min(w, h * 2)
        box_w = full_w / self._zoom
        box_h = box_w / 2.0
        x0 = (w - box_w) / 2.0 + self._pan.x()
        y0 = (h - box_h) / 2.0 + self._pan.y()
        return QRectF(x0, y0, box_w, box_h)

    def _geo(self, lat, lon, box):
        x = box.x() + (lon + 180.0) / 360.0 * box.width()
        y = box.y() + (90.0 - lat) / 180.0 * box.height()
        return x, y

    def _land_pixmap(self, w, h):
        if self._land and self._land.width() == w and self._land.height() == h:
            return self._land
        pm = QPixmap(w, h)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        for (cx, cy) in world.land_cells():
            x = cx / world.W * w
            y = cy / world.H * h
            cellw = w / world.W + 0.5
            cellh = h / world.H + 0.5
            p.fillRect(QRectF(x, y, cellw, cellh), QColor("#25334a"))
            p.fillRect(QRectF(x, y, cellw - 0.5, cellh - 0.5),
                       QColor("#2c3d57"))
        p.end()
        self._land = pm
        return pm

    # ---------------------------------------------------------------- paint
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(QRectF(0, 0, w, h), QColor(theme.BG).lighter(116))

        box = self._inner_rect(w, h)
        pw = box.width()
        ph = box.height()
        ix = box.x()
        iy = box.y()

        # the world map pane (2:1, i.e. not flattened onto the floor)
        paint_rect = QRectF(ix - 1, iy - 1, pw + 2, ph + 2)
        painter.fillRect(paint_rect, QColor(theme.PANEL))

        # graticule clipped to the map pane
        painter.save()
        painter.setClipRect(paint_rect)
        pen = QPen(QColor(theme.GRID), 1)
        pen.setStyle(Qt.DotLine)
        painter.setPen(pen)
        for lo in range(-150, 181, 30):
            x = ix + (lo + 180.0) / 360.0 * pw
            painter.drawLine(QPointF(x, iy), QPointF(x, iy + ph))
        for la in range(-60, 91, 30):
            y = iy + (90.0 - la) / 180.0 * ph
            painter.drawLine(QPointF(ix, y), QPointF(ix + pw, y))

        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.drawPixmap(paint_rect, self._land_pixmap(int(pw), int(ph)),
                           QRectF(0, 0, pw, ph))
        painter.setRenderHint(QPainter.Antialiasing, True)

        for tr in self.tracks:
            lats, lons = tr["lats"], tr["lons"]
            pen = QPen(QColor(tr["color"]), tr["width"])
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            seg_lats, seg_lons = [], []

            def flush():
                if len(seg_lats) >= 2:
                    pts = [QPointF(*self._geo(a, b, box))
                           for a, b in zip(seg_lats, seg_lons)]
                    for i in range(len(pts) - 1):
                        painter.drawLine(pts[i], pts[i + 1])
                seg_lats.clear()
                seg_lons.clear()

            for la, lo in zip(lats, lons):
                if seg_lons and abs(lo - seg_lons[-1]) > 180.0:
                    flush()
                seg_lats.append(la)
                seg_lons.append(lo)
            flush()

        for pt in self.points:
            x, y = self._geo(pt["lat"], pt["lon"], box)
            col = QColor(pt["color"])
            r = float(pt["radius"])
            if pt.get("glow"):
                pen = QPen(QColor(col.red(), col.green(), col.blue(), 70),
                           r * 2)
                painter.setPen(pen)
                painter.drawEllipse(QPointF(x, y), r * 2.4, r * 2.4)
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.setBrush(col)
            painter.drawEllipse(QPointF(x, y), r, r)
            if pt.get("label"):
                painter.setPen(QPen(QColor(theme.TEXT), 1))
                painter.drawText(QRectF(x - 120, y + r + 1, 240, 16),
                                 Qt.AlignHCenter, pt["label"])

        painter.restore()
        painter.setPen(QPen(QColor(theme.BORDER), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(paint_rect)

        if self.title:
            painter.setPen(QPen(QColor(theme.TEXT), 1))
            font = painter.font()
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(6, 4, w - 110, 20), Qt.AlignHCenter,
                             self.title)

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