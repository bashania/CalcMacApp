"""CalcMacApp - PyQt6 viewer/editor voor .c4y bestanden.

Start:
    python3 -m app.main
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.c4y_io import C4YDocument


# (xml_tag, kolomtitel, breedte)
COLUMNS: list[tuple[str, str, int]] = [
    ('code',  'Code',           80),
    ('s',     'S',              40),
    ('oms',   'Omschrijving',   320),
    ('hvh',   'Hvh',            80),
    ('enh',   'Enh',            60),
    ('arb',   'Arb (u/eh)',     90),
    ('maa',   'Maa (€/eh)',     90),
    ('ond',   'Ond (€/eh)',     90),
    ('code1', 'Onderaannemer',  180),
    ('code4', 'Bestek/Offerte', 130),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.doc: C4YDocument | None = None
        self._dirty = False

        self._build_ui()
        self._build_menu()
        self._update_title()
        self.resize(1280, 720)

    # ── UI opbouw ────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        form = QFormLayout()
        self.f_kop = QLineEdit()
        self.f_r1 = QLineEdit()
        self.f_r2 = QLineEdit()
        self.f_r4 = QLineEdit()
        for fld in (self.f_kop, self.f_r1, self.f_r2, self.f_r4):
            fld.editingFinished.connect(self._on_project_edit)
        form.addRow('Projectnummer', self.f_kop)
        form.addRow('Naam',          self.f_r1)
        form.addRow('Adres',         self.f_r2)
        form.addRow('Omschrijving',  self.f_r4)
        layout.addLayout(form)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in COLUMNS])
        for i, (_, _, w) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, w)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.itemChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table)

        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        filemenu = menubar.addMenu('&Bestand')

        act_open = QAction('Openen...', self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self.on_open)
        filemenu.addAction(act_open)

        act_save = QAction('Opslaan', self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self.on_save)
        filemenu.addAction(act_save)

        act_save_as = QAction('Opslaan als...', self)
        act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        act_save_as.triggered.connect(self.on_save_as)
        filemenu.addAction(act_save_as)

        filemenu.addSeparator()
        act_quit = QAction('Afsluiten', self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        filemenu.addAction(act_quit)

    # ── Status ───────────────────────────────────────────────────────────────
    def _update_title(self) -> None:
        base = 'CalcMacApp'
        if self.doc and self.doc.path:
            mark = ' *' if self._dirty else ''
            self.setWindowTitle(f'{base} — {Path(self.doc.path).name}{mark}')
        else:
            self.setWindowTitle(base)

    def _set_dirty(self, dirty: bool = True) -> None:
        self._dirty = dirty
        self._update_title()

    # ── Acties ───────────────────────────────────────────────────────────────
    def on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open .c4y bestand', '',
            'Calc4You bestanden (*.c4y);;Alle bestanden (*)',
        )
        if not path:
            return
        try:
            self.doc = C4YDocument.load(path)
        except Exception as e:
            QMessageBox.critical(self, 'Fout bij openen', str(e))
            return
        self._populate_ui()
        self._set_dirty(False)

    def on_save(self) -> None:
        if not self.doc:
            return
        if not self.doc.path:
            self.on_save_as()
            return
        try:
            self.doc.save()
            self._set_dirty(False)
        except Exception as e:
            QMessageBox.critical(self, 'Fout bij opslaan', str(e))

    def on_save_as(self) -> None:
        if not self.doc:
            return
        suggested = self.doc.path or ''
        path, _ = QFileDialog.getSaveFileName(
            self, 'Opslaan als', suggested,
            'Calc4You bestanden (*.c4y)',
        )
        if not path:
            return
        if not path.lower().endswith('.c4y'):
            path += '.c4y'
        try:
            self.doc.save(path)
            self._set_dirty(False)
        except Exception as e:
            QMessageBox.critical(self, 'Fout bij opslaan', str(e))

    # ── UI ↔ document synchronisatie ─────────────────────────────────────────
    def _populate_ui(self) -> None:
        if not self.doc:
            return

        for fld, tag in (
            (self.f_kop, 'kop'),
            (self.f_r1,  'r1'),
            (self.f_r2,  'r2'),
            (self.f_r4,  'r4'),
        ):
            fld.blockSignals(True)
            fld.setText(self.doc.get_project_field(tag))
            fld.blockSignals(False)

        self.table.blockSignals(True)
        try:
            n = self.doc.row_count()
            self.table.setRowCount(n)
            for r in range(n):
                for c, (tag, _, _) in enumerate(COLUMNS):
                    value = self.doc.get_row_field(r, tag)
                    self.table.setItem(r, c, QTableWidgetItem(value))
        finally:
            self.table.blockSignals(False)

    def _on_project_edit(self) -> None:
        if not self.doc:
            return
        for fld, tag in (
            (self.f_kop, 'kop'),
            (self.f_r1,  'r1'),
            (self.f_r2,  'r2'),
            (self.f_r4,  'r4'),
        ):
            self.doc.set_project_field(tag, fld.text())
        self._set_dirty(True)

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        if not self.doc:
            return
        tag = COLUMNS[item.column()][0]
        self.doc.set_row_field(item.row(), tag, item.text())
        self._set_dirty(True)

    # ── Sluiten met dirty-check ──────────────────────────────────────────────
    def closeEvent(self, event) -> None:
        if not self._dirty:
            event.accept()
            return
        reply = QMessageBox.question(
            self, 'Niet-opgeslagen wijzigingen',
            'Er zijn wijzigingen die nog niet zijn opgeslagen. Toch sluiten?',
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if reply == QMessageBox.StandardButton.Save:
            self.on_save()
            event.accept() if not self._dirty else event.ignore()
        elif reply == QMessageBox.StandardButton.Discard:
            event.accept()
        else:
            event.ignore()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName('CalcMacApp')
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
