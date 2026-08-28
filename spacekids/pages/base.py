"""PageBase: shared chrome for the four mission pages.

Left column = kid controls in a scroll area; right column = the canvas.
A header strip carries the mission title, a short subtitle and a status pill.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QScrollArea,
                               QSizePolicy, QSplitter, QVBoxLayout, QWidget)

from .. import theme
from ..widgets import pill


class PageBase(QWidget):
    def __init__(self, title, subtitle, parent=None):
        super().__init__(parent)
        self._status_pill = None
        self._status_word = "ready"
        self._status_kind = "info"
        self._styled = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)
        outer.addWidget(self._make_header(title, subtitle))

        splitter = QSplitter(Qt.Horizontal)

        self._controls_scroll = QScrollArea()
        self._controls_scroll.setWidgetResizable(True)
        controls_host = QWidget()
        self.controls = QVBoxLayout(controls_host)
        self.controls.setContentsMargins(2, 2, 10, 2)
        self.controls.setSpacing(6)
        self.controls.addStretch(1)
        self._controls_scroll.setWidget(controls_host)
        self._controls_scroll.setMinimumWidth(360)
        self._controls_scroll.setMaximumWidth(520)
        self._controls_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff)

        self._canvas_host = QWidget()
        self._canvas_lay = QVBoxLayout(self._canvas_host)
        self._canvas_lay.setContentsMargins(0, 0, 0, 0)
        self._canvas_lay.setSpacing(8)

        splitter.addWidget(self._controls_scroll)
        splitter.addWidget(self._canvas_host)
        splitter.setSizes([430, 830])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        outer.addWidget(splitter, 1)

    def _make_header(self, title, subtitle):
        row_box = QWidget()
        row = QHBoxLayout(row_box)
        row.setContentsMargins(0, 0, 0, 0)
        texts = QVBoxLayout()
        title_lbl = QLabel(title)
        f = QFont(theme.FAMILY, 16)
        f.setBold(True)
        title_lbl.setFont(f)
        sub = QLabel(subtitle)
        sub.setWordWrap(True)
        texts.addWidget(title_lbl)
        texts.addWidget(sub)
        row.addLayout(texts, 1)
        self._register_styled(title_lbl, "text")
        self._register_styled(sub, "muted")
        self._status_pill = pill("ready", "info", parent=row_box)
        row.addWidget(self._status_pill, 0, Qt.AlignTop)
        return row_box

    # --------------------------------------------------------------- helpers
    def _register_styled(self, widget, role):
        """Remember a label so ``refresh_theme`` can restyle it in-place."""
        self._styled.append((widget, role))

    def refresh_theme(self):
        """Re-apply theme-dependent inline styles on this page."""
        for widget, role in self._styled:
            if widget is not None:
                widget.setStyleSheet(theme.css_for(role))
        if self._status_pill is not None:
            parent = self._status_pill.parentWidget()
            if parent is not None:
                self.status(self._status_word, self._status_kind)
    def status(self, word, kind="info"):
        self._status_word = word
        self._status_kind = kind
        if self._status_pill is None:
            return
        parent = self._status_pill.parentWidget()
        if parent is not None:
            lay = parent.layout()
            idx = lay.indexOf(self._status_pill)
            if idx >= 0:
                old = self._status_pill
                new = pill(word, kind, parent=parent)
                lay.replaceWidget(old, new)
                new.show()
                old.deleteLater()
                self._status_pill = new

    def add_group(self, title):
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lay.setSpacing(6)
        self.controls.addWidget(box)
        return box, lay

    def add_canvas(self, widget):
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._canvas_lay.addWidget(widget, 1)

    def add_static(self, widget):
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._canvas_lay.addWidget(widget, 0)

    def busytip(self, text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(theme.css_for("dim"))
        self.controls.addWidget(lbl)
        self._register_styled(lbl, "dim")
        return lbl

    def fact_label(self, text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setMinimumWidth(1)
        lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        lbl.setStyleSheet(theme.css_for("fact"))
        self._register_styled(lbl, "fact")
        return lbl