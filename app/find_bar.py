"""Find-bar — Safari/Mail-stijl slide-down zoekbalk boven de tabel.

Apple HIG-conventies:
- ⌘F opent de bar; ⌘G volgende, ⌘⇧G vorige; Esc sluit.
- Live search terwijl je typt.
- Compacte hoogte (~30 px), dunne onderrand, geen frame buitenom.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QPropertyAnimation, Qt, pyqtSignal,
)
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QToolButton,
)


class FindBar(QFrame):
    """Live-search bar voor de begrotingstabel.

    Geeft signalen door aan de host:
      queryChanged(str)   — zoekterm veranderde (live)
      nextRequested()     — ⌘G of pijl-omlaag
      previousRequested() — ⌘⇧G of pijl-omhoog
      closed()            — Esc of klik op ✕
    """

    queryChanged     = pyqtSignal(str)
    nextRequested    = pyqtSignal()
    previousRequested = pyqtSignal()
    closed           = pyqtSignal()

    BAR_HEIGHT = 32

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

        h = QHBoxLayout(self)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(6)

        self._field = QLineEdit()
        self._field.setPlaceholderText('Zoeken in begroting')
        self._field.setClearButtonEnabled(True)
        self._field.textChanged.connect(self._on_text_changed)
        self._field.returnPressed.connect(self._on_return)

        self._btn_prev = QToolButton()
        self._btn_prev.setText('▲')
        self._btn_prev.setAutoRaise(True)
        self._btn_prev.setToolTip('Vorige (⌘⇧G)')
        self._btn_prev.clicked.connect(self.previousRequested)

        self._btn_next = QToolButton()
        self._btn_next.setText('▼')
        self._btn_next.setAutoRaise(True)
        self._btn_next.setToolTip('Volgende (⌘G)')
        self._btn_next.clicked.connect(self.nextRequested)

        self._lbl_count = QLabel('')
        self._lbl_count.setStyleSheet('color: palette(mid);')
        self._lbl_count.setMinimumWidth(70)

        self._btn_close = QToolButton()
        self._btn_close.setText('✕')
        self._btn_close.setAutoRaise(True)
        self._btn_close.setToolTip('Sluiten (Esc)')
        self._btn_close.clicked.connect(self._emit_closed)

        h.addWidget(self._field, 1)
        h.addWidget(self._btn_prev)
        h.addWidget(self._btn_next)
        h.addWidget(self._lbl_count)
        h.addWidget(self._btn_close)

        # Animatie voor in/uitschuiven
        self.setMaximumHeight(0)
        self._anim = QPropertyAnimation(self, b'maximumHeight', self)
        self._anim.setDuration(140)

    # ── API voor MainWindow ───────────────────────────────────────────────────
    def show_bar(self) -> None:
        if self.maximumHeight() < self.BAR_HEIGHT:
            self._anim.stop()
            self._anim.setStartValue(self.maximumHeight())
            self._anim.setEndValue(self.BAR_HEIGHT)
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
    def _on_text_changed(self, text: str) -> None:
        self.queryChanged.emit(text)

    def _on_return(self) -> None:
        self.nextRequested.emit()

    def _emit_closed(self) -> None:
        self.hide_bar()
        self.closed.emit()
