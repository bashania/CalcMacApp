"""CalcMacApp - PyQt6 viewer/editor voor .c4y bestanden.

Start:
    python3 -m app.main
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.c4y_io import C4YDocument, format_nl
from app.calc import recompute, totaal_begroting


# ── Kolomdefinitie ───────────────────────────────────────────────────────────
# tag begint met '_' = berekend (read-only, niet in XML)
# (tag, kolomtitel, breedte, bewerkbaar)
COLUMNS: list[tuple[str, str, int, bool]] = [
    ('nr',        'Nr',           60,  False),
    ('code',      'Code',         80,  True),
    ('s',         'S',            40,  True),
    ('oms',       'Omschrijving', 280, True),
    ('hvh',       'Hvh',          80,  True),
    ('enh',       'Enh',          50,  True),
    ('arb',       'Arb (u/eh)',   80,  True),
    ('uurloon',   'Uurloon',      80,  True),
    ('maa',       'Maa (€/eh)',   90,  True),
    ('mee',       'Mee (€/eh)',   90,  True),
    ('ond',       'Ond (€/eh)',   90,  True),
    ('productie', 'Factor (%)',   80,  True),
    ('_prijspe',  'Prijspe (€/eh)', 100, False),
    ('_toturen',  'Toturen',      80,  False),
    ('_totaal',   'Totaal (€)',   110, False),
    ('btw',       'BTW',          50,  True),
    ('code1',     'Onderaannemer', 160, True),
    ('code4',     'Bestek/Off.',  120, True),
]

# Kolomindex van 's' (voor herstijlen bij wijziging)
COL_S = next(i for i, c in enumerate(COLUMNS) if c[0] == 's')


# ── Kleuren per regeltype ────────────────────────────────────────────────────
# Achtergrondkleuren voor begrotingsregels per S-code.
ROW_COLORS: dict[str, str] = {
    '1': '#1f4e79',  # hoofdstuk: donkerblauw, witte tekst
    '2': '#d9e7f5',  # werksoort: lichtblauw
    '3': '#ecf2f9',  # locatie:  lichter blauwgrijs
    'S': '#fff8d6',  # stelpost: lichtgeel
    'V': '#ffe9c8',  # verrekenpost: lichtoranje
    'G': '#e2f3d9',  # geschatte post: lichtgroen
    '?': '#ece1f7',  # aandachtpost: lichtpaars
    'X': '#ffd9b3',  # X-post: oranje (cursief)
}

CALC_BG_DEFAULT = '#f3f3f3'  # achtergrond voor berekende kolommen op een gewone rij
TITEL_TEXT_LICHT = '#ffffff'  # witte tekst op donkere kop
TITEL_TEXT_DONKER = '#1f4e79'  # donkerblauwe tekst op lichte kop


def _calc_bg_for(s_code: str) -> str:
    """Achtergrond voor berekende kolommen — tint van de rijkleur."""
    if s_code == '1':
        return '#345d83'  # iets lichter dan rij om leesbaar te blijven
    return ROW_COLORS.get(s_code, CALC_BG_DEFAULT)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.doc: C4YDocument | None = None
        self._dirty = False

        self._build_actions()
        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._update_title()
        self._update_action_state()
        self.resize(1500, 760)

    # ── Acties (gedeeld door menu en toolbar) ────────────────────────────────
    def _build_actions(self) -> None:
        style = self.style()
        self.act_open = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
            'Openen...', self,
        )
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self.on_open)

        self.act_save = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
            'Opslaan', self,
        )
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(self.on_save)

        self.act_save_as = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DriveFDIcon),
            'Opslaan als...', self,
        )
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_as.triggered.connect(self.on_save_as)

        self.act_quit = QAction('Afsluiten', self)
        self.act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_quit.triggered.connect(self.close)

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
        for i, (_, _, w, _) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, w)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.itemChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table)

        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        filemenu = menubar.addMenu('&Bestand')
        filemenu.addAction(self.act_open)
        filemenu.addAction(self.act_save)
        filemenu.addAction(self.act_save_as)
        filemenu.addSeparator()
        filemenu.addAction(self.act_quit)

    def _build_toolbar(self) -> None:
        bar = QToolBar('Hoofd', self)
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        bar.addAction(self.act_open)
        bar.addAction(self.act_save)
        bar.addAction(self.act_save_as)
        self.addToolBar(bar)

    def _build_statusbar(self) -> None:
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._status.showMessage('Geen bestand geopend')

    # ── Status ───────────────────────────────────────────────────────────────
    def _update_title(self) -> None:
        base = 'CalcMacApp'
        if self.doc and self.doc.path:
            mark = ' *' if self._dirty else ''
            self.setWindowTitle(f'{base} — {Path(self.doc.path).name}{mark}')
        else:
            self.setWindowTitle(base)

    def _update_action_state(self) -> None:
        has_doc = self.doc is not None
        self.act_save.setEnabled(has_doc and self._dirty)
        self.act_save_as.setEnabled(has_doc)

    def _set_dirty(self, dirty: bool = True) -> None:
        self._dirty = dirty
        self._update_title()
        self._update_action_state()

    # ── Bestandsacties ───────────────────────────────────────────────────────
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
            self._status.showMessage(f'Opgeslagen: {Path(self.doc.path).name}', 3000)
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
            self._status.showMessage(f'Opgeslagen: {Path(self.doc.path).name}', 3000)
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
                for c, (tag, _, _, editable) in enumerate(COLUMNS):
                    if tag.startswith('_'):
                        value = ''  # wordt gevuld door _recompute_and_refresh
                    else:
                        value = self.doc.get_row_field(r, tag)
                    item = QTableWidgetItem(value)
                    if not editable:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(r, c, item)
                self._apply_row_style(r)
        finally:
            self.table.blockSignals(False)

        self._recompute_and_refresh()

    def _apply_row_style(self, row: int) -> None:
        """Pas kleuren, vetdruk en cursief toe op basis van de S-code."""
        if not self.doc:
            return
        s_code = self.doc.get_row_field(row, 's').strip()
        is_titel = s_code in ('1', '2', '3')

        bg = ROW_COLORS.get(s_code)
        calc_bg = _calc_bg_for(s_code)

        if s_code == '1':
            text_color = QColor(TITEL_TEXT_LICHT)
        elif s_code in ('2', '3'):
            text_color = QColor(TITEL_TEXT_DONKER)
        elif s_code == 'X':
            text_color = QColor('#7a3a00')
        else:
            text_color = None  # default

        font = QFont()
        font.setBold(is_titel)
        font.setItalic(s_code == 'X')
        if s_code == '1':
            base_size = QApplication.font().pointSize()
            font.setPointSize(base_size + 1)

        for c, (tag, _, _, _) in enumerate(COLUMNS):
            item = self.table.item(row, c)
            if item is None:
                continue
            is_calc = tag.startswith('_')
            if is_calc and bg is None:
                item.setBackground(QBrush(QColor(CALC_BG_DEFAULT)))
            elif is_calc and bg is not None:
                item.setBackground(QBrush(QColor(calc_bg)))
            elif bg is not None:
                item.setBackground(QBrush(QColor(bg)))
            else:
                # standaard rij — geen achtergrond zetten zou de kleur van
                # een oude S-stijl achterlaten; expliciet wit/transparant.
                item.setBackground(QBrush(QColor('#ffffff')))

            if text_color is not None:
                item.setForeground(QBrush(text_color))
            else:
                item.setForeground(QBrush(QColor('#000000')))

            item.setFont(font)

    def _recompute_and_refresh(self) -> None:
        """Bereken de kolommen prijspe/toturen/totaal en zet ze in de tabel."""
        if not self.doc:
            return

        n = self.doc.row_count()
        input_tags = ('s', 'hvh', 'arb', 'maa', 'mee', 'ond', 'uurloon', 'productie')
        rows_in = [
            {t: self.doc.get_row_field(i, t) for t in input_tags}
            for i in range(n)
        ]
        results = recompute(rows_in)

        calc_cols = {
            '_prijspe': next(i for i, c in enumerate(COLUMNS) if c[0] == '_prijspe'),
            '_toturen': next(i for i, c in enumerate(COLUMNS) if c[0] == '_toturen'),
            '_totaal':  next(i for i, c in enumerate(COLUMNS) if c[0] == '_totaal'),
        }

        self.table.blockSignals(True)
        try:
            for r, res in enumerate(results):
                for tag, col in calc_cols.items():
                    item = self.table.item(r, col)
                    if item is not None:
                        item.setText(res[tag.lstrip('_')])
        finally:
            self.table.blockSignals(False)

        self._status.showMessage(
            f'Totaal: € {format_nl(totaal_begroting(results, rows_in))}'
        )

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
        if tag.startswith('_'):
            return  # berekend, niet wegschrijven

        self.doc.set_row_field(item.row(), tag, item.text())
        self._set_dirty(True)

        # S-code gewijzigd → rij her-stijlen
        if item.column() == COL_S:
            self.table.blockSignals(True)
            try:
                self._apply_row_style(item.row())
            finally:
                self.table.blockSignals(False)

        # Velden die de rekening beïnvloeden → herrekenen
        if tag in ('s', 'hvh', 'arb', 'maa', 'mee', 'ond', 'uurloon', 'productie'):
            self._recompute_and_refresh()

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
            if self._dirty:
                event.ignore()
            else:
                event.accept()
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
