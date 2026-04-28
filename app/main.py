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
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
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
# (tag, label, breedte, bewerkbaar)
# Tags met '_' zijn berekend: read-only, niet in XML.
COLUMNS: list[tuple[str, str, int, bool]] = [
    ('nr',        'Nr',           50,  False),
    ('code',      'Code',         80,  True),
    ('s',         'S',            36,  True),
    ('oms',       'Omschrijving', 260, True),
    ('hvh',       'Hvh',          72,  True),
    ('enh',       'Enh',          44,  True),
    ('arb',       'Arb',          68,  True),
    ('uurloon',   'Uurloon',      72,  True),
    ('maa',       'Maa',          80,  True),
    ('mee',       'Mee',          72,  True),
    ('ond',       'Ond',          80,  True),
    ('productie', 'Factor%',      64,  True),
    ('_prijspe',  'Prijspe',      88,  False),
    ('_toturen',  'Toturen',      72,  False),
    ('_totaal',   'Totaal',       96,  False),
    ('btw',       'BTW',          44,  True),
    ('code1',     'Onderaannemer', 150, True),
    ('code4',     'Bestek/Off.',  110, True),
]

COL_S   = next(i for i, c in enumerate(COLUMNS) if c[0] == 's')
COL_OMS = next(i for i, c in enumerate(COLUMNS) if c[0] == 'oms')

# Numerieke kolommen → rechts uitlijnen
NUMBER_TAGS = frozenset({
    'hvh', 'arb', 'uurloon', 'maa', 'mee', 'ond', 'productie',
    '_prijspe', '_toturen', '_totaal',
})


# ── Kleurenpalet (Mac-geïnspireerd, rustige tonen) ───────────────────────────
# Begrotingsniveaus
C_H1_BG   = '#2c5f8a'   # hoofdstuk: gedempte marineblauw
C_H1_FG   = '#ffffff'
C_H2_BG   = '#daeeff'   # werksoort: licht hemelsblauw
C_H2_FG   = '#1a3a5c'
C_H3_BG   = '#eef6fc'   # locatie: bijna wit, lichtblauw
C_H3_FG   = '#2a4a6a'

# Bijzondere begrotingsposten
C_STEL_BG = '#fffae6'   # stelpost S: lichtgeel
C_VERR_BG = '#fff3e0'   # verrekenpost V: lichtoranje
C_GEST_BG = '#eaf7e4'   # geschatte post G: lichtgroen
C_AAND_BG = '#f3eefb'   # aandachtpost ?: lichtpaars
C_XPST_BG = '#fff0e6'   # X-post: pale peach + cursief

# Staart
C_SLASH_BG = '#6d6d72'  # '/' scheiding: Mac donkergrijs
C_SLASH_FG = '#ffffff'
C_PERC_BG  = '#f9f4e8'  # '%' / '&' opslag: warm off-white
C_SOM_BG   = '#c8c8cc'  # '=' subtotaal: Mac lichtgrijs
C_SOM_FG   = '#1c1c1e'
C_PLUS_BG  = '#e8f8ec'  # '+' toevoeging: lichtgroen
C_MIN_BG   = '#fce8e8'  # '-' aftrek: lichtrood
C_BTW_BG   = '#e5effe'  # BTW (a/b/c): lichtblauw

# Berekende kolommen: iets afgezwakte versie van de rijkleur
CALC_BG_MAP: dict[str, str] = {
    '1': '#3a6f9e', '2': '#c4e4f5', '3': '#dceefa',
    '/': '#828287', '=': '#b8b8bc',
}
CALC_BG_DEFAULT = '#efefef'

# Alle rijstijlen per S-code
ROW_STYLE: dict[str, dict] = {
    '1': {'bg': C_H1_BG,    'fg': C_H1_FG,    'bold': True,  'italic': False, 'size+': 1},
    '2': {'bg': C_H2_BG,    'fg': C_H2_FG,    'bold': True,  'italic': False, 'size+': 0},
    '3': {'bg': C_H3_BG,    'fg': C_H3_FG,    'bold': True,  'italic': False, 'size+': 0},
    'S': {'bg': C_STEL_BG,  'fg': None,        'bold': False, 'italic': False, 'size+': 0},
    'V': {'bg': C_VERR_BG,  'fg': None,        'bold': False, 'italic': False, 'size+': 0},
    'G': {'bg': C_GEST_BG,  'fg': None,        'bold': False, 'italic': False, 'size+': 0},
    '?': {'bg': C_AAND_BG,  'fg': None,        'bold': False, 'italic': False, 'size+': 0},
    'X': {'bg': C_XPST_BG,  'fg': '#7a3a00',   'bold': False, 'italic': True,  'size+': 0},
    '/': {'bg': C_SLASH_BG, 'fg': C_SLASH_FG,  'bold': True,  'italic': False, 'size+': 0},
    '=': {'bg': C_SOM_BG,   'fg': C_SOM_FG,    'bold': True,  'italic': False, 'size+': 0},
    '%': {'bg': C_PERC_BG,  'fg': None,        'bold': False, 'italic': False, 'size+': 0},
    '&': {'bg': C_PERC_BG,  'fg': None,        'bold': False, 'italic': True,  'size+': 0},
    '+': {'bg': C_PLUS_BG,  'fg': '#1a5a1a',   'bold': False, 'italic': False, 'size+': 0},
    '-': {'bg': C_MIN_BG,   'fg': '#7a0000',   'bold': False, 'italic': False, 'size+': 0},
    'a': {'bg': C_BTW_BG,   'fg': '#1a2a6a',   'bold': False, 'italic': False, 'size+': 0},
    'b': {'bg': C_BTW_BG,   'fg': '#1a2a6a',   'bold': False, 'italic': False, 'size+': 0},
    'c': {'bg': '#f0f0f4',  'fg': '#555555',   'bold': False, 'italic': True,  'size+': 0},
}
STYLE_DEFAULT = {'bg': None, 'fg': '#000000', 'bold': False, 'italic': False, 'size+': 0}

# Inspringing omschrijving per S-niveau (visualiseert hiërarchie)
INDENT = {'1': '', '2': '  ', '3': '    '}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.doc: C4YDocument | None = None
        self._dirty = False
        self._base_font_size: int = QApplication.font().pointSize()

        self._build_actions()
        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._update_title()
        self._update_action_state()
        self.resize(1540, 800)

    # ── Gedeelde acties ──────────────────────────────────────────────────────
    def _build_actions(self) -> None:
        sp = self.style()
        self.act_open = QAction(
            sp.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
            'Openen', self, shortcut=QKeySequence.StandardKey.Open,
        )
        self.act_open.triggered.connect(self.on_open)

        self.act_save = QAction(
            sp.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
            'Opslaan', self, shortcut=QKeySequence.StandardKey.Save,
        )
        self.act_save.triggered.connect(self.on_save)

        self.act_save_as = QAction(
            sp.standardIcon(QStyle.StandardPixmap.SP_DriveFDIcon),
            'Opslaan als', self, shortcut=QKeySequence.StandardKey.SaveAs,
        )
        self.act_save_as.triggered.connect(self.on_save_as)

        self.act_quit = QAction(
            'Afsluiten', self, shortcut=QKeySequence.StandardKey.Quit,
        )
        self.act_quit.triggered.connect(self.close)

    # ── UI opbouw ────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 4)
        root.setSpacing(6)

        # Projectkop: twee QFormLayouts naast elkaar
        form_row = QHBoxLayout()
        form_row.setSpacing(20)

        left_form  = QFormLayout()
        right_form = QFormLayout()
        for f in (left_form, right_form):
            f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
            f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            f.setHorizontalSpacing(8)

        self.f_kop = QLineEdit(); self.f_kop.setPlaceholderText('20261.00260')
        self.f_r1  = QLineEdit(); self.f_r1.setPlaceholderText('Projectnaam')
        self.f_r2  = QLineEdit(); self.f_r2.setPlaceholderText('Adres')
        self.f_r4  = QLineEdit(); self.f_r4.setPlaceholderText('Omschrijving werkzaamheden')

        left_form.addRow('Nummer',       self.f_kop)
        left_form.addRow('Naam',         self.f_r1)
        right_form.addRow('Adres',       self.f_r2)
        right_form.addRow('Omschrijving', self.f_r4)

        for w in (self.f_r1, self.f_r4):
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        for fld in (self.f_kop, self.f_r1, self.f_r2, self.f_r4):
            fld.editingFinished.connect(self._on_project_edit)

        form_row.addLayout(left_form, 1)
        form_row.addLayout(right_form, 2)
        root.addLayout(form_row)

        # Begrotingstabel
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in COLUMNS])
        for i, (_, _, w, _) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, w)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setGridStyle(Qt.PenStyle.SolidLine)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(False)  # eigen kleuren per rij
        self.table.itemChanged.connect(self._on_cell_changed)
        root.addWidget(self.table)

        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        f = self.menuBar().addMenu('&Bestand')
        f.addAction(self.act_open)
        f.addAction(self.act_save)
        f.addAction(self.act_save_as)
        f.addSeparator()
        f.addAction(self.act_quit)

    def _build_toolbar(self) -> None:
        bar = QToolBar('Hoofd', self)
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        bar.setIconSize(bar.iconSize().__class__(22, 22))
        bar.addAction(self.act_open)
        bar.addAction(self.act_save)
        bar.addAction(self.act_save_as)
        self.addToolBar(bar)

    def _build_statusbar(self) -> None:
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self._lbl_totaal = QLabel('Geen bestand geopend')
        sb.addPermanentWidget(self._lbl_totaal)

    # ── Titelstatus + actie-enabled ───────────────────────────────────────────
    def _update_title(self) -> None:
        base = 'CalcMacApp'
        if self.doc and self.doc.path:
            mark = ' •' if self._dirty else ''  # macOS-stijl middelpunt
            self.setWindowTitle(f'{Path(self.doc.path).name}{mark} — {base}')
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
        except Exception as exc:
            QMessageBox.critical(self, 'Fout bij openen', str(exc))
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
            self.statusBar().showMessage(
                f'Opgeslagen: {Path(self.doc.path).name}', 3000
            )
        except Exception as exc:
            QMessageBox.critical(self, 'Fout bij opslaan', str(exc))

    def on_save_as(self) -> None:
        if not self.doc:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Opslaan als', self.doc.path or '',
            'Calc4You bestanden (*.c4y)',
        )
        if not path:
            return
        if not path.lower().endswith('.c4y'):
            path += '.c4y'
        try:
            self.doc.save(path)
            self._set_dirty(False)
            self.statusBar().showMessage(
                f'Opgeslagen: {Path(self.doc.path).name}', 3000
            )
        except Exception as exc:
            QMessageBox.critical(self, 'Fout bij opslaan', str(exc))

    # ── Tabel vullen ─────────────────────────────────────────────────────────
    def _populate_ui(self) -> None:
        if not self.doc:
            return

        for fld, tag in (
            (self.f_kop, 'kop'), (self.f_r1, 'r1'),
            (self.f_r2,  'r2'),  (self.f_r4, 'r4'),
        ):
            fld.blockSignals(True)
            fld.setText(self.doc.get_project_field(tag))
            fld.blockSignals(False)

        self.table.blockSignals(True)
        try:
            n = self.doc.row_count()
            self.table.setRowCount(n)
            for r in range(n):
                s_code = self.doc.get_row_field(r, 's').strip()
                for c, (tag, _, _, editable) in enumerate(COLUMNS):
                    value = '' if tag.startswith('_') \
                            else self.doc.get_row_field(r, tag)
                    item = QTableWidgetItem(value)
                    if not editable:
                        item.setFlags(
                            item.flags() & ~Qt.ItemFlag.ItemIsEditable
                        )
                    if tag in NUMBER_TAGS:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight |
                            Qt.AlignmentFlag.AlignVCenter
                        )
                    self.table.setItem(r, c, item)
                self._apply_row_style(r, s_code)
        finally:
            self.table.blockSignals(False)

        self._recompute_and_refresh()

    # ── Rijstyling ────────────────────────────────────────────────────────────
    def _apply_row_style(self, row: int, s_code: str) -> None:
        style = ROW_STYLE.get(s_code, STYLE_DEFAULT)
        bg_hex  = style['bg']
        fg_hex  = style['fg'] or '#1c1c1e'
        bold    = style['bold']
        italic  = style['italic']
        size_d  = style['size+']

        calc_bg_hex = CALC_BG_MAP.get(s_code, CALC_BG_DEFAULT)

        font = QFont()
        font.setBold(bold)
        font.setItalic(italic)
        if size_d:
            font.setPointSize(self._base_font_size + size_d)

        fg_brush = QBrush(QColor(fg_hex))

        for c, (tag, _, _, _) in enumerate(COLUMNS):
            item = self.table.item(row, c)
            if item is None:
                continue
            is_calc = tag.startswith('_')
            if is_calc:
                item.setBackground(QBrush(QColor(calc_bg_hex)))
            elif bg_hex:
                item.setBackground(QBrush(QColor(bg_hex)))
            else:
                item.setBackground(QBrush(QColor('#ffffff')))

            item.setForeground(fg_brush)
            item.setFont(font)

        # Inspringing in de omschrijving voor titelniveaus
        oms_item = self.table.item(row, COL_OMS)
        if oms_item is not None and s_code in INDENT:
            raw_oms = self.doc.get_row_field(row, 'oms') if self.doc else ''
            oms_item.setText(INDENT[s_code] + raw_oms)

    # ── Herberekening ─────────────────────────────────────────────────────────
    def _recompute_and_refresh(self) -> None:
        if not self.doc:
            return

        n = self.doc.row_count()
        input_tags = ('s', 'hvh', 'arb', 'maa', 'mee', 'ond', 'uurloon', 'productie')
        rows_in = [
            {t: self.doc.get_row_field(i, t) for t in input_tags}
            for i in range(n)
        ]
        results = recompute(rows_in)

        calc_map = {
            '_prijspe': 'prijspe',
            '_toturen':  'toturen',
            '_totaal':   'totaal',
        }
        col_idx = {tag: i for i, (tag, _, _, _) in enumerate(COLUMNS)}

        self.table.blockSignals(True)
        try:
            for r, res in enumerate(results):
                for ctag, rkey in calc_map.items():
                    item = self.table.item(r, col_idx[ctag])
                    if item is not None:
                        item.setText(res[rkey])
        finally:
            self.table.blockSignals(False)

        totaal = totaal_begroting(results, rows_in)
        self._lbl_totaal.setText(f'Totaal: € {format_nl(totaal)}')

    # ── Celwijzigingen ───────────────────────────────────────────────────────
    def _on_project_edit(self) -> None:
        if not self.doc:
            return
        for fld, tag in (
            (self.f_kop, 'kop'), (self.f_r1, 'r1'),
            (self.f_r2,  'r2'),  (self.f_r4, 'r4'),
        ):
            self.doc.set_project_field(tag, fld.text())
        self._set_dirty(True)

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        if not self.doc:
            return
        tag = COLUMNS[item.column()][0]
        if tag.startswith('_'):
            return

        # Omschrijving: strip inspringing voor opslag in XML
        value = item.text()
        if tag == 'oms':
            value = value.lstrip()

        self.doc.set_row_field(item.row(), tag, value)
        self._set_dirty(True)

        if item.column() == COL_S:
            s_code = item.text().strip()
            self.table.blockSignals(True)
            try:
                self._apply_row_style(item.row(), s_code)
            finally:
                self.table.blockSignals(False)

        if tag in ('s', 'hvh', 'arb', 'maa', 'mee', 'ond', 'uurloon', 'productie'):
            self._recompute_and_refresh()

    # ── Sluiten ──────────────────────────────────────────────────────────────
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

    # macOS: toolbar samenvoegen met titelbar (unified look)
    if sys.platform == 'darwin':
        from PyQt6.QtGui import QPalette
        app.setAttribute(
            Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True
        )

    win = MainWindow()
    if sys.platform == 'darwin':
        win.setUnifiedTitleAndToolBarOnMac(True)
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
