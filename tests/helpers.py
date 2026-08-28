"""Shared helpers for the full test suite.

* points imports at ``spacekids`` (the repo root),
* forces Qt's ``offscreen`` platform so GUI tests run anywhere,
* isolates user data (settings + places) into temp files,
* stops the animated timers cleanly so windows can be torn down.
"""

import contextlib
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@contextlib.contextmanager
def isolated_env():
    """Point SPACEKIDS_SETTINGS / SPACEKIDS_LOCATIONS at throwaway files."""
    saved = (os.environ.get("SPACEKIDS_SETTINGS"),
             os.environ.get("SPACEKIDS_LOCATIONS"))
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["SPACEKIDS_SETTINGS"] = os.path.join(tmp, "settings.json")
        os.environ["SPACEKIDS_LOCATIONS"] = os.path.join(tmp, "locations.json")
        try:
            yield tmp
        finally:
            pass
    for var, val in (("SPACEKIDS_SETTINGS", saved[0]),
                     ("SPACEKIDS_LOCATIONS", saved[1])):
        if val is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = val


def get_app():
    """The one shared QApplication (created offscreen on demand)."""
    import PySide6
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def pump():
    app = get_app()
    for _ in range(4):
        app.processEvents()


def shut_window(win):
    """Stop every page timer before the window goes away, release its theme
    listener (so closed windows stop restyling), then free it."""
    from PySide6.QtCore import QTimer
    for timer in win.findChildren(QTimer):
        timer.stop()
    for page in getattr(win, "pages", {}).values():
        fn = getattr(page, "_shut", None)
        if fn is not None:
            fn()
    from spacekids import theme
    theme._listeners[:] = [fn for fn in theme._listeners
                           if getattr(fn, "__self__", None) is not win]
    win.close()
    win.deleteLater()
    pump()


@contextlib.contextmanager
def no_network():
    """Neutralise the background ISS TLE fetch (Spotter page opens it)."""
    from unittest import mock
    import spacekids.astro.satellites as satmod
    with mock.patch.object(satmod, "refresh_iss", lambda _cb: None):
        yield


def make_mouse(type_, pos, button=0b00000000, buttons=0b00000000):
    """A bare QMouseEvent (button/buttons bitfields or Qt enum values)."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    _TYPES = {
        "MouseButtonPress": QEvent.Type.MouseButtonPress,
        "MouseButtonRelease": QEvent.Type.MouseButtonRelease,
        "MouseButtonDblClick": QEvent.Type.MouseButtonDblClick,
        "MouseMove": QEvent.Type.MouseMove,
    }
    evtype = _TYPES.get(type_, type_ if isinstance(type_, QEvent.Type) else
                        QEvent.Type.MouseMove)
    return QMouseEvent(
        evtype,
        QPointF(*pos),
        button if button else Qt.NoButton,
        buttons if buttons else Qt.NoButton,
        Qt.NoModifier,
    )