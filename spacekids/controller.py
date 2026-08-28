"""Small shared controller glue: app icon + status info."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

from . import APP_NAME, __version__
from .astro.core import PO_FOUND, PO_VERSION, poliastro_status


def _draw_logo(p, color):
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    # rocket body
    p.drawLine(24, 26, 24, 10)
    p.drawLine(19, 20, 24, 14)
    p.drawLine(29, 20, 24, 14)
    p.drawLine(19, 20, 24, 26)
    p.drawLine(29, 20, 24, 26)
    # window
    p.drawEllipse(QPointF(24, 18), 1.4, 1.4)
    # flame
    p.drawLine(24, 26, 21.5, 30)
    p.drawLine(24, 26, 26.5, 30)
    # stars
    for (x, y) in ((13, 8), (34, 6), (8, 30), (36, 30)):
        p.drawPoint(x, y)


def app_logo():
    pm = QPixmap(192, 192)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    ring = QColor("#37b6ff")
    p.setBrush(Qt.NoBrush)
    pen = QPen(ring, 7)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawEllipse(QRectF(14, 14, 164, 164))
    _draw_logo(p, "#37b6ff")
    p.end()
    return QIcon(pm)


def toolbar_icon():
    pm = QPixmap(20, 20)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    _draw_logo(p, "#9fb2c9")
    p.end()
    return QIcon(pm)


def about_html():
    return (
        "<h2>%s v%s</h2>"
        "<p>A playful orbital-mechanics playground for young explorers, "
        "built on <b>poliastro</b>.</p>"
        "<p>Six activities: plan a Hohmann transfer to Mars, design your own "
        "satellite orbit, intercept a real asteroid, spot the ISS flying "
        "over your town, watch the GPS, GLONASS and BeiDou fleets "
        "switch places into your own saved towns, and pick your favourite "
        "look in the theme settings.</p>"
        "<table>"
        "<tr><td>Orbit engine</td><td>%s</td></tr>"
        "<tr><td>Numerics</td><td>NumPy + astropy units</td></tr>"
        "<tr><td>Pass prediction</td><td>SGP4 (live TLE) + Kepler fallback</td></tr>"
        "<tr><td>Developer</td><td>Amir Arshad</td></tr>"
        "</table>"
        "<p>Textbook mean orbital elements power the planets; asteroid phases "
        "are illustrative, as stated in the app.</p>"
    ) % (APP_NAME, __version__, poliastro_status())