"""Reusable, kid-friendly UI bits: labelled sliders, stat chips, panels."""

import datetime

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (QCalendarWidget, QDialog, QDialogButtonBox,
                               QHBoxLayout, QFrame, QLabel, QLineEdit,
                               QPushButton, QSizePolicy, QSlider, QToolButton,
                               QVBoxLayout, QWidget)

from . import settings, theme


def prompt_add_place(parent=None):
    """Ask for a new place's name + lat/lon; return a dict or None on cancel."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Add my place")
    form = QVBoxLayout(dlg)
    form.addWidget(QLabel("Name (e.g. Grandma's house)"))
    name = QLineEdit()
    form.addWidget(name)
    form.addWidget(QLabel("Latitude (e.g. 34.05)"))
    lat = QLineEdit()
    form.addWidget(lat)
    form.addWidget(QLabel("Longitude (e.g. -118.24)"))
    lon = QLineEdit()
    form.addWidget(lon)
    info = QLabel("West longitudes are negative, like -74 for New York.")
    info.setWordWrap(True)
    info.setStyleSheet("color: %s;" % theme.TEXT_MUT)
    form.addWidget(info)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    form.addWidget(buttons)
    dlg.resize(320, 230)
    if dlg.exec() != QDialog.Accepted:
        return None
    try:
        return {"name": name.text().strip(),
                "lat": float(lat.text().strip()),
                "lon": float(lon.text().strip())}
    except ValueError:
        return None


def section_label(text, parent=None):
    lbl = QLabel(text, parent)
    lbl.setProperty("section", True)
    return lbl


def pill(text, kind="info", parent=None):
    """A small rounded status chip; kinds: ok/warn/err/info."""
    lbl = QLabel("  %s  " % text, parent)
    col = theme.chip_color(kind).name()
    lbl.setStyleSheet(
        "QLabel { color: %s; border: 1px solid %s;"
        " border-radius: 10px; padding: 2px 8px; font-weight: 600; }"
        % (col, col))
    return lbl


def _as_qdate(value):
    if isinstance(value, QDate):
        return QDate(value)
    if isinstance(value, datetime.datetime):
        return QDate(value.year, value.month, value.day)
    if isinstance(value, datetime.date):
        return QDate(value.year, value.month, value.day)
    return QDate.currentDate()


class DatePicker(QWidget):
    """A real calendar picker: click the field and a calendar pops up.

    Exposes the same surface a ``QDateEdit`` does (``date()``, ``setDate``,
    ``setDateRange``, ``setCalendarPopup``) so pages keep their code unchanged.
    """

    dateChanged = Signal(object)

    def __init__(self, initial=None, minimum=None, maximum=None,
                 fmt="%d %b %Y", parent=None):
        super().__init__(parent)
        self._date = _as_qdate(initial or datetime.date.today())
        self._min = _as_qdate(minimum) if minimum is not None else None
        self._max = _as_qdate(maximum) if maximum is not None else None
        self._fmt = fmt
        self._inside_min = self._min
        self._inside_max = self._max

        self._field = QPushButton()
        self._field.setProperty("primary", True)
        self._field.setCursor(Qt.PointingHandCursor)
        self._field.clicked.connect(self._open_calendar)
        self._field.setToolTip("Click to open the calendar")

        self._today = QToolButton()
        self._today.setText("Today")
        self._today.setCursor(Qt.PointingHandCursor)
        self._today.setAutoRaise(True)
        self._today.clicked.connect(self._go_today)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self._field, 0)
        lay.addWidget(self._today, 0)
        self._refresh_text()
        fm = self._field.fontMetrics()
        width = fm.horizontalAdvance(self._field.text()) + 24
        self._field.setFixedWidth(max(112, min(150, width)))
        self._field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._today.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMaximumWidth(280)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

    # ------------------------------------------------------------ surface
    def date(self):
        return QDate(self._date)

    def setDate(self, qdate):
        self._date = _as_qdate(qdate)
        if self._min is not None and self._date < self._min:
            self._date = self._min
        if self._max is not None and self._date > self._max:
            self._date = self._max
        self._refresh_text()
        self.dateChanged.emit(self._date.toPython())

    def setDateRange(self, lo, hi):
        self._min = _as_qdate(lo)
        self._max = _as_qdate(hi)
        self.setDate(self._date)

    def setMinimumDate(self, qdate):
        self._min = _as_qdate(qdate)
        self.setDate(self._date)

    def setMaximumDate(self, qdate):
        self._max = _as_qdate(qdate)
        self.setDate(self._date)

    def setCalendarPopup(self, on):
        pass  # always a popup; kept for QDateEdit compatibility

    # ------------------------------------------------------------ internals
    def _refresh_text(self):
        py = self._date.toPython()
        self._field.setText("%s  " % py.strftime(self._fmt) + "\u25be")

    def _go_today(self):
        today = QDate.currentDate()
        if self._min is not None and today < self._min:
            today = self._min
        if self._max is not None and today > self._max:
            today = self._max
        self.setDate(today)

    def _open_calendar(self):
        cal = QCalendarWidget()
        cal.setGridVisible(True)
        cal.setFirstDayOfWeek(Qt.Monday)
        cal.setSelectedDate(self._date)
        if self._min is not None:
            cal.setMinimumDate(self._min)
        if self._max is not None:
            cal.setMaximumDate(self._max)
        cal.setStyleSheet(
            "QCalendarWidget QWidget { alternate-background-color: %s; }"
            % theme.PANEL)

        pop = QDialog(self, Qt.Popup)
        pop.setAttribute(Qt.WA_DeleteOnClose)
        lay = QVBoxLayout(pop)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        lay.addWidget(cal)
        cal.activated.connect(pop.accept)
        cal.selectionChanged.connect(
            lambda: self.setDate(cal.selectedDate()))
        pop.setLayout(lay)
        top = self.mapToGlobal(self.rect().bottomLeft())
        pop.move(top.x(), top.y() + 4)
        pop.exec()


class Panel(QFrame):
    """A raised card panel."""

    def __init__(self, parent=None, title=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._title = title
        self._restyle()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        if title:
            lbl = section_label(title)
            lbl.setMinimumWidth(1)
            lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            lay.addWidget(lbl)
            self.setMinimumWidth(1)
        self._lay = lay

    def _restyle(self):
        self.setStyleSheet(
            "QFrame { background: %s; border: 1px solid %s;"
            " border-radius: 10px; }" % (theme.PANEL, theme.BORDER))

    def refresh_theme(self):
        self._restyle()

    @property
    def layout_box(self):
        return self._lay


class SliderRow(QWidget):
    """Label + value + horizontal slider that emits float values."""

    valueChanged = Signal(float)

    def __init__(self, label, vmin, vmax, value, step=1.0, suffix="",
                 decimals=0, fmt=None, parent=None):
        super().__init__(parent)
        self._min = float(vmin)
        self._max = float(vmax)
        self._step = float(step)
        self._dec = decimals
        self._fmt = fmt
        self._suffix = suffix

        self._name = QLabel(label)
        self._name.setMinimumWidth(1)
        self._name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._val = QLabel()
        self._val.setMinimumWidth(72)
        self._val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._restyle_labels()

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, self._count())
        self._slider.valueChanged.connect(self._on_slider)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(8)
        row.addWidget(self._name, 1)
        row.addWidget(self._val)
        row.addWidget(self._slider, 1)
        self._slider.setMinimumWidth(96)
        self.setMinimumWidth(1)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.set_value(float(value))

    def _restyle_labels(self):
        self._name.setStyleSheet(theme.css_for("muted"))
        self._val.setStyleSheet(
            "color: %s; font-family: %s; font-weight: 600;"
            % (theme.ACCENT, theme.MONO))

    def refresh_theme(self):
        self._restyle_labels()

    def _count(self):
        return int(round((self._max - self._min) / self._step))

    def _to_float(self, i):
        return self._min + i * self._step

    def _on_slider(self, i):
        v = self._to_float(i)
        self._render(v)
        self.valueChanged.emit(v)

    def _render(self, v):
        if self._fmt:
            text = self._fmt(v)
        elif self._dec:
            text = ("%%.%df%%s" % self._dec) % (v, self._suffix)
        else:
            text = "%d%s" % (int(round(v)), self._suffix)
        self._val.setText(text)

    def value(self):
        return self._to_float(self._slider.value())

    def set_value(self, v):
        i = int(round((float(v) - self._min) / self._step))
        self._slider.setValue(max(0, min(self._count(), i)))
        self._render(self.value())

    def set_range(self, vmin, vmax, step=None, suffix=None, value=None):
        """Replace the slider's min/max/step (keeping the current value)."""
        old = self.value()
        self._min = float(vmin)
        self._max = float(vmax)
        if step is not None:
            self._step = float(step)
        if suffix is not None:
            self._suffix = suffix
        self._slider.setRange(0, self._count())
        self.set_value(value if value is not None else old)

    def slider(self):
        return self._slider


class StatBox(QWidget):
    """A big value with a caption, for numbers kids should notice."""

    def __init__(self, label, parent=None, color=None):
        super().__init__(parent)
        self._color = color
        self._cap = QLabel(label)
        self._cap.setWordWrap(True)
        self._val = QLabel("--")
        self._val.setWordWrap(True)
        self._val.setAlignment(Qt.AlignCenter)
        self._restyle()
        for w in (self._val, self._cap):
            w.setMinimumWidth(1)
            from PySide6.QtWidgets import QSizePolicy
            w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(0)
        lay.addWidget(self._val)
        lay.addWidget(self._cap)

    def _restyle(self):
        self._cap.setStyleSheet(theme.css_for("muted"))
        self._val.setStyleSheet(
            "color: %s; font-size: 22px; font-weight: 700; font-family: %s;"
            % (self._color or theme.ACCENT, theme.MONO))

    def refresh_theme(self):
        self._restyle()

    def set_value(self, text):
        self._val.setText(text)


class PlayBar(QWidget):
    """play/pause + step + speed for canvas animations."""

    playToggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QToolButton, QComboBox

        self._play_btn = QToolButton()
        self._play_btn.setText("Play")
        self._play_btn.setCheckable(True)
        self._play_btn.setChecked(False)
        self._play_btn.toggled.connect(self.playToggled)

        self.speed = QComboBox()
        for i, (label, mult) in enumerate((("1x", 1.0), ("2x", 2.0),
                                           ("5x", 5.0), ("10x", 10.0),
                                           ("30x", 30.0))):
            self.speed.addItem(label, mult)
            if i == int(settings.get("playback", 1)):
                self.speed.setCurrentIndex(i)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self._play_btn)
        lay.addWidget(QLabel("Speed"))
        lay.addWidget(self.speed)
        lay.addStretch(1)

    def set_playing(self, on):
        self._play_btn.setChecked(on)


class HLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self._restyle()

    def _restyle(self):
        self.setStyleSheet("background: %s;" % theme.BORDER_SOFT)

    def refresh_theme(self):
        self._restyle()