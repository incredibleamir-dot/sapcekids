"""OrbitalView3D: a PyVista-based 3D orbital scene viewer.

Drop-in replacement for the 2D SpaceView.  Renders heliocentric or
Earth-centred scenes with interactive rotation, zoom, and pan via
pyvistaqt's QtInteractor.  A Qt timer drives the same animation loop
that SpaceView used, so pages can ``play()``, ``seek()``, ``clear()``
and ``set_scene()`` with an identical API.

Headless/offscreen safety: PyVista needs a real OpenGL context.  When the
app runs without a display (e.g. under ``QT_QPA_PLATFORM=offscreen`` during
automated tests) ``make_orbital_view()`` returns the 2D :class:`SpaceView`
fallback so the whole app still builds and runs.
"""

import os

import numpy as np

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QSizePolicy, QWidget

import pyvista as pv

from .. import theme
from .spaceview import SpaceView

try:
    from pyvistaqt import QtInteractor as _QtInteractor
except Exception:  # pragma: no cover - pyvistaqt missing / broken
    _QtInteractor = QWidget


class Body:
    """A moving object on the 3D scene: centre is any callable given sim time."""

    __slots__ = ("pos_fn", "radius_km", "color", "label", "glow", "line",
                 "_last")

    def __init__(self, pos_fn, radius_km, color, label=None, glow=0.0,
                 line=False):
        self.pos_fn = pos_fn
        self.radius_km = radius_km
        self.color = color
        self.label = label
        self.glow = glow
        self.line = line
        self._last = None

    def position(self, t):
        p = self.pos_fn(t)
        self._last = tuple(float(v) for v in p)
        return self._last


def _headless():
    """True when running without a usable OpenGL display (offscreen/CI)."""
    if os.environ.get("QT_QPA_PLATFORM", "").lower() in ("offscreen", "minimal"):
        return True
    if os.environ.get("SPACEKIDS_FORCE_2D"):
        return True
    return False


def make_orbital_view(parent=None):
    """Return an interactive orbital view for the given context.

    Uses the PyVista 3-D viewer normally; falls back to the 2-D
    :class:`SpaceView` under offscreen/headless conditions so pages and test
    suites keep working everywhere.
    """
    if _headless():
        return SpaceView()
    try:
        from pyvistaqt import QtInteractor  # noqa: F401 - import check
        return OrbitalView3D(parent)
    except Exception:
        return SpaceView()


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _pv_color(hexcol):
    return _hex_to_rgb(hexcol)


class OrbitalView3D(_QtInteractor):
    """3-D orbital scene with pan/zoom/rotate.

    Scene API is identical to :class:`SpaceView` so pages can swap them
    with no code changes in the page module:

    * ``set_scene(paths, bodies, center, title, subtitle, min_radius_km)``
    * ``play(on=True)`` / ``seek(t)`` / ``clear()``
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.paths = []
        self.bodies = []
        self.labels = []
        self.center = (0.0, 0.0, 0.0)
        self.title = ""
        self.subtitle = ""
        self.min_radius_km = 0.0

        self.t = 0.0
        self.dt = 0.0
        self.playing = False

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._on_tick)

        self._body_actors = []
        self._glow_actors = []
        self._trail_actors = []
        self._label_actors = []
        self._path_actors = []
        self._cam_pos = None
        self._cam_focal = None
        self._cam_up = None
        self._needs_fit = True
        self._view_axis = None

        self.background = _pv_color(theme.BG)
        self.set_background(*self.background)
        self.enable_zoom_scaling()

    # ---------------------------------------------------------------- scene
    def set_scene(self, paths=None, bodies=None, center=(0.0, 0.0, 0.0),
                  title="", subtitle="", min_radius_km=0.0,
                  view_axis=None):
        self.clear()
        self.paths = paths or []
        self.bodies = bodies or []
        self.center = center
        self.title = title
        self.subtitle = subtitle
        self.min_radius_km = min_radius_km
        self._view_axis = view_axis
        self.t = 0.0
        self._needs_fit = True

        bg = _pv_color(theme.BG)
        self.set_background(*bg)

        for p in self.paths:
            self._draw_path(p)
        for b in self.bodies:
            self._draw_body(b, 0.0)
        self._fit_camera()

    def clear(self):
        self.remove_all_labeled_axes()
        self.renderer.RemoveAllViewProps()
        self.paths = []
        self.bodies = []
        self.labels = []
        self.t = 0.0
        self.playing = False
        self._body_actors = []
        self._glow_actors = []
        self._trail_actors = []
        self._label_actors = []
        self._path_actors = []

    # ------------------------------------------------------------- dynamic paths
    def set_paths(self, paths):
        """Replace just the orbital path arcs (e.g. the animated fly trail)."""
        for ac in self._path_actors:
            try:
                self.renderer.RemoveViewProp(ac)
            except Exception:
                pass
        self._path_actors = []
        self.paths = paths or []
        for p in self.paths:
            self._draw_path(p)
        self.render()

    # -------------------------------------------------------------- playback
    def play(self, on=True):
        self.playing = bool(on)
        if on:
            self._timer.start()
        else:
            self._timer.stop()

    def seek(self, t):
        self.t = float(t)
        self._update_bodies(self.t)

    def _on_tick(self):
        self.t += self.dt
        self._update_bodies(self.t)

    # ----------------------------------------------------------- internal draw
    def _draw_path(self, p):
        pts = p.get("points")
        if pts is None or len(pts) < 2:
            return
        pts = np.asarray(pts, dtype=float)
        n = len(pts)
        lines = np.column_stack([np.full(n, 2), np.arange(n)]).ravel()
        mesh = pv.PolyData(pts, lines=lines)
        color = _pv_color(p.get("color", theme.C_TRAIL))
        width = float(p.get("width", 1.6))
        ac = self.add_mesh(mesh, color=color, line_width=width,
                           render_lines_as_tubes=True, pickable=False)
        self._path_actors.append(ac)

    def _draw_body(self, b, t):
        pos = np.asarray(b.position(t), dtype=float)
        r = max(0.005, b.radius_km)
        sphere = pv.Sphere(radius=r, center=pos)
        color = _pv_color(b.color)
        ac = self.add_mesh(sphere, color=color, smooth_shading=True,
                           pickable=False)
        self._body_actors.append(ac)

        if b.glow:
            gs = pv.Sphere(radius=r * 1.4, center=pos)
            gc = self.add_mesh(gs, color=color, opacity=0.25,
                               pickable=False)
            self._glow_actors.append(gc)

        if b.line:
            end = pos + np.array([r * 1.8, r * 1.2, 0.0])
            pts = np.array([pos, end])
            lines = np.array([2, 0, 1])
            trail = pv.PolyData(pts, lines=lines)
            tc = self.add_mesh(trail, color=_pv_color(theme.C_PROBE),
                               line_width=3, render_lines_as_tubes=True,
                               pickable=False)
            self._trail_actors.append(tc)

        if b.label:
            txt_pos = pos + np.array([0.0, 0.0, r * 1.6])
            ac = self.add_point_labels(
                [txt_pos], [b.label],
                font_size=12,
                text_color=_pv_color(theme.TEXT),
                point_color=(0, 0, 0),
                point_size=0.01,
                pickable=False,
                shape_color=(0, 0, 0),
                shape_opacity=0.0,
            )
            self._label_actors.append(ac)

    def _update_bodies(self, t):
        for i, b in enumerate(self.bodies):
            if i >= len(self._body_actors):
                break
            pos = np.asarray(b.position(t), dtype=float)
            r = max(0.005, b.radius_km)

            sphere = pv.Sphere(radius=r, center=pos)
            self._body_actors[i].SetMapper(
                self._body_actors[i].GetMapper())
            self.renderer.RemoveViewProp(self._body_actors[i])
            ac = self.add_mesh(sphere, color=_pv_color(b.color),
                               smooth_shading=True, pickable=False)
            self._body_actors[i] = ac

            if b.glow and i < len(self._glow_actors):
                gs = pv.Sphere(radius=r * 1.4, center=pos)
                self.renderer.RemoveViewProp(self._glow_actors[i])
                gc = self.add_mesh(gs, color=_pv_color(b.color),
                                   opacity=0.25, pickable=False)
                self._glow_actors[i] = gc

            if b.line:
                if i < len(self._trail_actors):
                    self.renderer.RemoveViewProp(self._trail_actors[i])
                end = pos + np.array([r * 1.8, r * 1.2, 0.0])
                pts = np.array([pos, end])
                lines = np.array([2, 0, 1])
                trail = pv.PolyData(pts, lines=lines)
                tc = self.add_mesh(trail, color=_pv_color(theme.C_PROBE),
                                   line_width=3,
                                   render_lines_as_tubes=True,
                                   pickable=False)
                if i < len(self._trail_actors):
                    self._trail_actors[i] = tc
                else:
                    self._trail_actors.append(tc)

            if b.label and i < len(self._label_actors):
                self.renderer.RemoveViewProp(self._label_actors[i])
                txt_pos = pos + np.array([0.0, 0.0, r * 1.6])
                ac = self.add_point_labels(
                    [txt_pos], [b.label],
                    font_size=12,
                    text_color=_pv_color(theme.TEXT),
                    point_color=(0, 0, 0),
                    point_size=0.01,
                    pickable=False,
                    shape_color=(0, 0, 0),
                    shape_opacity=0.0,
                )
                self._label_actors[i] = ac

        if self._needs_fit:
            self._fit_camera()
            self._needs_fit = False

    # -------------------------------------------------------------- camera
    def _fit_camera(self):
        all_pts = []
        for p in self.paths:
            pts = p.get("points")
            if pts is not None and len(pts) > 0:
                all_pts.append(np.asarray(pts, dtype=float))
        for b in self.bodies:
            if b._last is not None:
                all_pts.append(np.asarray(b._last, dtype=float).reshape(1, 3))
        if not all_pts:
            return
        all_pts = np.vstack(all_pts)
        ctr = np.asarray(self.center, dtype=float)
        rmax = float(np.max(np.linalg.norm(all_pts - ctr, axis=1)))
        rmax = max(rmax, self.min_radius_km, 1.0)

        # Snap to a nice axis-aligned view unless a specific look direction
        # was requested (e.g. the satellite page asks to look down the orbit's
        # angular-momentum axis so a circular orbit reads as a circle).
        axis = self._view_axis
        if axis is None:
            # default: slightly raised orbital-plane view
            if np.allclose(ctr, 0.0):
                axis = (0.0, -1.0, 0.5)
            else:
                c = ctr / (np.linalg.norm(ctr) + 1e-12)
                axis = -c
        axis = np.asarray(axis, dtype=float)
        axis = axis / (np.linalg.norm(axis) + 1e-12)

        dist = rmax * 2.5
        self.camera.position = tuple(ctr + axis * dist)
        self.camera.focal_point = tuple(ctr)
        self.camera.view_angle = 40.0
        self.camera.up = self._orbit_view_up(axis)
        self._cam_pos = self.camera.position
        self._cam_focal = self.camera.focal_point
        self._cam_up = self.camera.up

    @staticmethod
    def _orbit_view_up(view_axis):
        """Pick a stable 'up' vector perpendicular to the view axis."""
        up = np.array([0.0, 0.0, 1.0])
        if abs(float(np.dot(up, view_axis))) > 0.9:
            up = np.array([0.0, 1.0, 0.0])
        right = np.cross(view_axis, up)
        right = right / (np.linalg.norm(right) + 1e-12)
        return tuple(np.cross(right, view_axis))

    # ------------------------------------------------------------- mouse
    def refresh_theme(self):
        """Restyle background when the Space Kids palette switches."""
        try:
            bg = _pv_color(theme.BG)
            self.set_background(*bg)
        except Exception:
            pass

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._cam_pos is not None:
            self.camera.position = self._cam_pos
            self.camera.focal_point = self._cam_focal
            self.camera.up = self._cam_up
            ev.accept()
            return
        super().mouseDoubleClickEvent(ev)
