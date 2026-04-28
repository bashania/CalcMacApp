"""CalcMacApp - PyQt6 viewer/editor voor .c4y bestanden.

Start:
    python3 -m app.main
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QKeySequence,
    QUndoStack,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
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

from app.c4y_io import C4YDocument, TITEL_NIVEAUS, format_nl
from app.calc import recompute, totaal_begroting
from app.commands import (
    DeleteRowCommand,
    DuplicateRowCommand,
    InsertRowCommand,
    MoveBlockCommand,
    SetCellCommand,
)


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

# Disclosure-driehoekjes voor titelrijen
DISCLOSURE_OPEN   = '▼ '   # ▼
DISCLOSURE_CLOSED = '▶ '   # ▶
DISCLOSURE_CHARS  = (DISCLOSURE_OPEN.strip(), DISCLOSURE_CLOSED.strip())


def _strip_oms_chrome(text: str) -> str:
    """Verwijder leidende whitespace + disclosure-driehoekjes uit een
    bewerkte oms-cel zodat alleen de schone tekst overblijft."""
    text = text.lstrip()
    for prefix in (DISCLOSURE_OPEN, DISCLOSURE_CLOSED):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.lstrip()


# ── Tabel met blok-bewuste drag & drop + disclosure-klik ─────────────────────
class DnDTableWidget(QTableWidget):
    """QTableWidget met:
      - Blok-bewuste drag & drop (titelrijen slepen children mee).
      - Klik op de eerste ~18 px van de Omschrijving-cel → toggle inklap.
    """

    blockMoveRequested  = pyqtSignal(int, int, int)  # (src, count, dst)
    disclosureClicked   = pyqtSignal(int)            # row index

    DISCLOSURE_HIT_PX = 18

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._block_size_for: callable | None = None
        self._oms_col: int = 0
        self._is_titel: callable | None = None
        self._drag_block_count = 1

    # ── Configuratie door MainWindow ─────────────────────────────────────────
    def set_helpers(
        self, *, block_size_for, is_titel, oms_col: int,
    ) -> None:
        self._block_size_for = block_size_for
        self._is_titel = is_titel
        self._oms_col = oms_col

    # ── Klik op disclosure-driehoekje ────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_titel:
            idx = self.indexAt(event.pos())
            if idx.isValid() and idx.column() == self._oms_col \
                    and self._is_titel(idx.row()):
                cell_rect = self.visualRect(idx)
                x_in_cell = event.pos().x() - cell_rect.x()
                if 0 <= x_in_cell <= self.DISCLOSURE_HIT_PX:
                    self.disclosureClicked.emit(idx.row())
                    event.accept()
                    return
        # Onthouden welk blok we slepen, voordat de selectie wordt gewijzigd
        if self._block_size_for and event.button() == Qt.MouseButton.LeftButton:
            idx = self.indexAt(event.pos())
            if idx.isValid():
                self._drag_block_count = self._block_size_for(idx.row())
        super().mousePressEvent(event)

    # ── Drop: bereken (src, count, dst) en signal ────────────────────────────
    def dropEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        src = self.currentRow()
        if src < 0:
            event.ignore()
            return
        count = self._drag_block_count or 1

        dst_idx = self.indexAt(event.pos())
        if not dst_idx.isValid():
            dst = self.rowCount() - count
        else:
            dst = dst_idx.row()
            # Bereken doelpositie ná verwijdering van het blok:
            if dst > src:
                dst -= count
                if dst < 0:
                    dst = 0
        # Drop binnen het bron-blok zelf wordt genegeerd
        if src <= dst < src + count:
            event.ignore()
            return
        if dst == src:
            event.ignore()
            return

        self.blockMoveRequested.emit(src, count, dst)
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.doc: C4YDocument | None = None
        self._base_font_size: int = QApplication.font().pointSize()

        # Undo-stack: bron van waarheid voor dirty-state
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(200)
        self.undo_stack.cleanChanged.connect(self._on_clean_changed)

        # Per-sessie state voor in/uitklap (stabiel onder rij-renummering)
        import xml.etree.ElementTree as _ET
        self._collapsed: set[_ET.Element] = set()

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

        # Undo / Redo via QUndoStack
        self.act_undo = self.undo_stack.createUndoAction(self, 'Ongedaan maken')
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_redo = self.undo_stack.createRedoAction(self, 'Opnieuw')
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)

        # Rijbewerkingen
        self.act_row_add_below = QAction('Rij toevoegen', self,
                                         shortcut=Qt.Key.Key_F9)
        self.act_row_add_below.triggered.connect(self.on_row_add_below)

        self.act_row_add_above = QAction('Rij toevoegen boven', self,
                                         shortcut='Shift+F9')
        self.act_row_add_above.triggered.connect(self.on_row_add_above)

        self.act_row_delete = QAction(
            sp.standardIcon(QStyle.StandardPixmap.SP_TrashIcon),
            'Rij verwijderen', self, shortcut=Qt.Key.Key_F11,
        )
        self.act_row_delete.triggered.connect(self.on_row_delete)

        self.act_row_dup = QAction('Rij kopiëren onder', self,
                                   shortcut='Shift+F4')
        self.act_row_dup.triggered.connect(self.on_row_duplicate)

        self.act_cell_dup_above = QAction(
            'Cel uit rij erboven kopiëren', self, shortcut=Qt.Key.Key_F4,
        )
        self.act_cell_dup_above.triggered.connect(self.on_cell_dup_above)

        # In/uitklap
        self.act_collapse = QAction('Niveau in/uitklappen', self,
                                    shortcut=Qt.Key.Key_F8)
        self.act_collapse.triggered.connect(self.on_toggle_collapse)

        self.act_collapse_level = QAction(
            'Alle van dit niveau in/uitklappen', self, shortcut='Shift+F8',
        )
        self.act_collapse_level.triggered.connect(
            self.on_toggle_collapse_level
        )

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

        # Begrotingstabel met drag & drop en disclosure-klik
        self.table = DnDTableWidget(0, len(COLUMNS))
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
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setAlternatingRowColors(False)

        # Drag & drop
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.table.setDefaultDropAction(Qt.DropAction.MoveAction)

        self.table.set_helpers(
            block_size_for=self._safe_block_size,
            is_titel=self._row_is_titel,
            oms_col=COL_OMS,
        )
        self.table.blockMoveRequested.connect(self._on_block_move)
        self.table.disclosureClicked.connect(self._on_disclosure_clicked)
        self.table.itemChanged.connect(self._on_cell_changed)
        root.addWidget(self.table)

        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        m = self.menuBar()
        f = m.addMenu('&Bestand')
        f.addAction(self.act_open)
        f.addAction(self.act_save)
        f.addAction(self.act_save_as)
        f.addSeparator()
        f.addAction(self.act_quit)

        b = m.addMenu('Be&werken')
        b.addAction(self.act_undo)
        b.addAction(self.act_redo)
        b.addSeparator()
        b.addAction(self.act_row_add_below)
        b.addAction(self.act_row_add_above)
        b.addAction(self.act_row_delete)
        b.addAction(self.act_row_dup)
        b.addAction(self.act_cell_dup_above)
        b.addSeparator()
        b.addAction(self.act_collapse)
        b.addAction(self.act_collapse_level)

    def _build_toolbar(self) -> None:
        bar = QToolBar('Hoofd', self)
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        bar.setIconSize(bar.iconSize().__class__(22, 22))
        bar.addAction(self.act_open)
        bar.addAction(self.act_save)
        bar.addAction(self.act_save_as)
        bar.addSeparator()
        bar.addAction(self.act_undo)
        bar.addAction(self.act_redo)
        bar.addSeparator()
        bar.addAction(self.act_row_add_below)
        bar.addAction(self.act_row_delete)
        self.addToolBar(bar)

    def _build_statusbar(self) -> None:
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self._lbl_totaal = QLabel('Geen bestand geopend')
        sb.addPermanentWidget(self._lbl_totaal)

    # ── Titelstatus + actie-enabled ───────────────────────────────────────────
    @property
    def _dirty(self) -> bool:
        return not self.undo_stack.isClean()

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
        # Rij-acties alleen bij geopend document
        for a in (
            self.act_row_add_below, self.act_row_add_above,
            self.act_row_delete,    self.act_row_dup,
            self.act_cell_dup_above,
            self.act_collapse,      self.act_collapse_level,
        ):
            a.setEnabled(has_doc)

    def _on_clean_changed(self, _is_clean: bool) -> None:
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
        self.undo_stack.clear()
        self._collapsed.clear()
        self._populate_ui()
        self.undo_stack.setClean()
        self._update_title()
        self._update_action_state()

    def on_save(self) -> None:
        if not self.doc:
            return
        if not self.doc.path:
            self.on_save_as()
            return
        try:
            self.doc.save()
            self.undo_stack.setClean()
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
            self.undo_stack.setClean()
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
        self._apply_visibility()

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

        # Inspringing en disclosure-driehoekje voor titelniveaus
        oms_item = self.table.item(row, COL_OMS)
        if oms_item is not None and self.doc is not None:
            raw_oms = self.doc.get_row_field(row, 'oms')
            if s_code in INDENT:
                disclosure = (
                    DISCLOSURE_CLOSED if self._row_is_collapsed(row)
                    else DISCLOSURE_OPEN
                )
                oms_item.setText(INDENT[s_code] + disclosure + raw_oms)
            else:
                oms_item.setText(raw_oms)

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

        # Strip cosmetische prefixen voor de XML-opslag
        new_value = item.text()
        if tag == 'oms':
            new_value = _strip_oms_chrome(new_value)

        old_value = self.doc.get_row_field(item.row(), tag)
        if old_value == new_value:
            return  # geen echte wijziging — geen undo-entry

        self.undo_stack.push(SetCellCommand(
            self, item.row(), tag, old_value, new_value,
        ))

    # ── Helpers voor commando's en DnDTableWidget ────────────────────────────
    def _safe_block_size(self, idx: int) -> int:
        if not self.doc:
            return 1
        try:
            return self.doc.block_size(idx) or 1
        except Exception:
            return 1

    def _row_is_titel(self, idx: int) -> bool:
        if not self.doc or not 0 <= idx < self.doc.row_count():
            return False
        return self.doc.get_row_field(idx, 's').strip() in TITEL_NIVEAUS

    def _row_element(self, idx: int):
        if self.doc is None or not 0 <= idx < self.doc.row_count():
            return None
        return self.doc.begrotingen[idx]

    def _row_is_collapsed(self, idx: int) -> bool:
        el = self._row_element(idx)
        return el is not None and el in self._collapsed

    def _current_row(self) -> int:
        r = self.table.currentRow()
        return r if r >= 0 else 0

    # Hooks die QUndoCommands aanroepen via het _Host-protocol
    def refresh(self) -> None:
        """Volledige rerender van de tabel zonder undo-stack te raken."""
        self._populate_ui()

    def select_row(self, idx: int) -> None:
        if 0 <= idx < self.table.rowCount():
            self.table.setCurrentCell(idx, max(COL_OMS, 0))

    # ── Rij-acties ───────────────────────────────────────────────────────────
    def _new_row_defaults(self) -> dict[str, str]:
        if not self.doc:
            return {}
        # Uurloon overnemen uit alginfo/<ul> als die bestaat
        ul = self.doc.get_project_field('ul').strip()
        defaults: dict[str, str] = {}
        if ul:
            defaults['uurloon'] = ul
        defaults.setdefault('productie', '25,00')
        return defaults

    def on_row_add_below(self) -> None:
        if not self.doc:
            return
        idx = self._current_row() + 1 if self.doc.row_count() else 0
        self.undo_stack.push(InsertRowCommand(
            self, idx, self._new_row_defaults(),
        ))

    def on_row_add_above(self) -> None:
        if not self.doc:
            return
        idx = self._current_row() if self.doc.row_count() else 0
        self.undo_stack.push(InsertRowCommand(
            self, idx, self._new_row_defaults(),
            text='Rij toevoegen boven',
        ))

    def on_row_delete(self) -> None:
        if not self.doc or self.doc.row_count() == 0:
            return
        idx = self._current_row()
        # Bevestig als rij data heeft
        oms = self.doc.get_row_field(idx, 'oms').strip()
        if oms:
            reply = QMessageBox.question(
                self, 'Rij verwijderen',
                f'Verwijder rij {idx + 1}: "{oms[:60]}"?',
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.undo_stack.push(DeleteRowCommand(self, idx))

    def on_row_duplicate(self) -> None:
        if not self.doc or self.doc.row_count() == 0:
            return
        self.undo_stack.push(DuplicateRowCommand(self, self._current_row()))

    def on_cell_dup_above(self) -> None:
        """Kopieer de waarde van de cel direct erboven naar de actieve cel."""
        if not self.doc:
            return
        row = self.table.currentRow()
        col = self.table.currentColumn()
        if row <= 0 or col < 0:
            return
        tag = COLUMNS[col][0]
        if tag.startswith('_'):
            return  # berekende kolom
        old = self.doc.get_row_field(row, tag)
        new = self.doc.get_row_field(row - 1, tag)
        if old == new:
            return
        self.undo_stack.push(SetCellCommand(self, row, tag, old, new))

    # ── Drag & drop signal-handler ────────────────────────────────────────────
    def _on_block_move(self, src: int, count: int, dst: int) -> None:
        if not self.doc or count < 1:
            return
        self.undo_stack.push(MoveBlockCommand(self, src, count, dst))

    # ── Disclosure / inklap ──────────────────────────────────────────────────
    def _on_disclosure_clicked(self, row: int) -> None:
        self._toggle_collapse(row)

    def on_toggle_collapse(self) -> None:
        self._toggle_collapse(self._current_row())

    def on_toggle_collapse_level(self) -> None:
        """Toggle in/uitklap voor alle titels op het niveau van de huidige rij."""
        if not self.doc:
            return
        row = self._current_row()
        s = self.doc.get_row_field(row, 's').strip()
        if s not in TITEL_NIVEAUS:
            return
        # Bepaal of we gaan inklappen of uitklappen: als minstens één titel
        # van dit niveau uitgeklapt is → klap allemaal in. Anders → uitklap.
        same_level: list[int] = []
        for i in range(self.doc.row_count()):
            if self.doc.get_row_field(i, 's').strip() == s:
                same_level.append(i)
        any_open = any(not self._row_is_collapsed(i) for i in same_level)
        target_collapsed = any_open
        for i in same_level:
            el = self._row_element(i)
            if el is None:
                continue
            if target_collapsed:
                self._collapsed.add(el)
            else:
                self._collapsed.discard(el)
        self._refresh_oms_prefix()
        self._apply_visibility()

    def _toggle_collapse(self, row: int) -> None:
        el = self._row_element(row)
        if el is None or not self._row_is_titel(row):
            return
        if el in self._collapsed:
            self._collapsed.discard(el)
        else:
            self._collapsed.add(el)
        self._refresh_oms_prefix()
        self._apply_visibility()

    def _refresh_oms_prefix(self) -> None:
        """Werk alleen de oms-cellen van titelrijen bij (driehoekje)."""
        if not self.doc:
            return
        self.table.blockSignals(True)
        try:
            for i in range(self.doc.row_count()):
                if self._row_is_titel(i):
                    s_code = self.doc.get_row_field(i, 's').strip()
                    self._apply_row_style(i, s_code)
        finally:
            self.table.blockSignals(False)

    def _apply_visibility(self) -> None:
        """Verberg rijen onder ingeklapte titels.

        Als een titel zelf onder een ingeklapte ouder zit, wordt die ook
        verborgen — geneste inklap werkt natuurlijk.
        """
        if not self.doc:
            return
        n = self.doc.row_count()
        # Bouw eerst een lijst van 'verberg-tot-en-met' grenzen.
        hidden = [False] * n
        i = 0
        while i < n:
            if self._row_is_titel(i) and self._row_is_collapsed(i):
                size = self.doc.block_size(i)
                # Verberg children (niet de titel zelf)
                for j in range(i + 1, i + size):
                    hidden[j] = True
                i += size
            else:
                i += 1
        # Cleanup van stale ingeklap-elementen (verwijderd uit document)
        live_elements = set(self.doc.begrotingen)
        self._collapsed &= live_elements
        for r in range(n):
            self.table.setRowHidden(r, hidden[r])

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
