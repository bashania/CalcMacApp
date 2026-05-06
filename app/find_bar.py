"""Find-bar — Safari/Mail-stijl slide-down zoekbalk boven de tabel.

Apple HIG-conventies:
- ⌘F opent de bar; ⌘G volgende, ⌘⇧G vorige; Esc sluit.
- ⌥⌘F opent met de Replace-rij erbij.
- Live search terwijl je typt.
- Compacte hoogte (~30 px per rij), dunne onderrand.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QPropertyAnimation, Qt, pyqtSignal,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)


class FindBar(QFrame):
    """Live-search bar voor de begrotingstabel met optionele Replace-modus.

    Signalen:
      queryChanged(str)        — zoekterm veranderde (live)
      nextRequested()          — ⌘G of pijl-omlaag
      previousRequested()      — ⌘⇧G of pijl-omhoog
      replaceCurrentRequested(str) — vervang huidige match met str
      replaceAllRequested(str, str) — vervang alle matches (oud, nieuw)
      closed()                 — Esc of klik op ✕
    """

    queryChanged            = pyqtSignal(str)
    nextRequested           = pyqtSignal()
    previousRequested       = pyqtSignal()
    replaceCurrentRequested = pyqtSignal(str)
    replaceAllRequested     = pyqtSignal(str, str)
    closed                  = pyqtSignal()

    BAR_HEIGHT_FIND    = 32
    BAR_HEIGHT_REPLACE = 64

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed,
        )
        self.setStyleSheet(
            'FindBar { '
            '  background: palette(window); '
            '  border-bottom: 1px solid palette(mid); '
            '}'
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(4)

        # ── Find-rij ─────────────────────────────────────────────────────────
        find_row = QHBoxLayout()
        find_row.setSpacing(6)
        self._field = QLineEdit()
        self._field.setPlaceholderText('Zoeken in begroting')
        self._field.setClearButtonEnabled(True)
        self._field.textChanged.connect(self.queryChanged.emit)
        self._field.returnPressed.connect(self.nextRequested.emit)

        self._btn_prev = QToolButton(text='▲', autoRaise=True,
                                     toolTip='Vorige (⌘⇧G)')
        self._btn_prev.clicked.connect(self.previousRequested)
        self._btn_next = QToolButton(text='▼', autoRaise=True,
                                     toolTip='Volgende (⌘G)')
        self._btn_next.clicked.connect(self.nextRequested)

        self._lbl_count = QLabel('')
        self._lbl_count.setStyleSheet('color: palette(mid);')
        self._lbl_count.setMinimumWidth(70)

        self._btn_close = QToolButton(text='✕', autoRaise=True,
                                      toolTip='Sluiten (Esc)')
        self._btn_close.clicked.connect(self._emit_closed)

        find_row.addWidget(self._field, 1)
        find_row.addWidget(self._btn_prev)
        find_row.addWidget(self._btn_next)
        find_row.addWidget(self._lbl_count)
        find_row.addWidget(self._btn_close)
        outer.addLayout(find_row)

        # ── Replace-rij (verborgen tot ⌥⌘F) ──────────────────────────────────
        self._replace_widget = QWidget()
        rep_row = QHBoxLayout(self._replace_widget)
        rep_row.setContentsMargins(0, 0, 0, 0)
        rep_row.setSpacing(6)
        self._replace_field = QLineEdit()
        self._replace_field.setPlaceholderText('Vervang door…')
        self._replace_field.returnPressed.connect(self._on_replace_one)

        self._btn_replace = QToolButton(text='Vervang', autoRaise=True)
        self._btn_replace.clicked.connect(self._on_replace_one)
        self._btn_replace_all = QToolButton(text='Alle vervangen',
                                            autoRaise=True)
        self._btn_replace_all.clicked.connect(self._on_replace_all)

        rep_row.addWidget(self._replace_field, 1)
        rep_row.addWidget(self._btn_replace)
        rep_row.addWidget(self._btn_replace_all)
        outer.addWidget(self._replace_widget)
        self._replace_widget.setVisible(False)

        # Animatie voor in/uitschuiven
        self.setMaximumHeight(0)
        self._anim = QPropertyAnimation(self, b'maximumHeight', self)
        self._anim.setDuration(140)

    # ── API voor MainWindow ───────────────────────────────────────────────────
    def show_bar(self, *, replace: bool = False) -> None:
        self._replace_widget.setVisible(replace)
        target = (
            self.BAR_HEIGHT_REPLACE if replace else self.BAR_HEIGHT_FIND
        )
        if self.maximumHeight() != target:
            self._anim.stop()
            self._anim.setStartValue(self.maximumHeight())
            self._anim.setEndValue(target)
            self._anim.start()
        self._field.selectAll()
        self._field.setFocus()

    def hide_bar(self) -> None:
        if self.maximumHeight() > 0:
            self._anim.stop()
            self._anim.setStartValue(self.maximumHeight())
            self._anim.setEndValue(0)
            self._anim.start()

    def is_open(self) -> bool:
        return self.maximumHeight() > 0

    def go_next(self) -> None:
        if self.is_open():
            self.nextRequested.emit()
        else:
            self.show_bar()

    def go_previous(self) -> None:
        if self.is_open():
            self.previousRequested.emit()
        else:
            self.show_bar()

    def query(self) -> str:
        return self._field.text()

    def replacement(self) -> str:
        return self._replace_field.text()

    def set_count_text(self, text: str) -> None:
        self._lbl_count.setText(text)

    # ── Toetsenbord-shortcuts binnen de bar ──────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._emit_closed()
            event.accept()
            return
        super().keyPressEvent(event)

    # ── Intern ───────────────────────────────────────────────────────────────
    def _emit_closed(self) -> None:
        self.hide_bar()
        self.closed.emit()

    def _on_replace_one(self) -> None:
        self.replaceCurrentRequested.emit(self._replace_field.text())

    def _on_replace_all(self) -> None:
        self.replaceAllRequested.emit(
            self._field.text(), self._replace_field.text(),
        )
