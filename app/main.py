"""CalcMacApp - PyQt6 viewer/editor voor .c4y bestanden.

Start:
    python3 -m app.main
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QKeySequence,
    QPen,
    QUndoStack,
)
from PyQt6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QRadioButton,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.c4y_io import (
    C4YDocument, TITEL_NIVEAUS, format_nl, format_nl_hvh, parse_nl_number,
)
from app.calc import eindtotaal_begroting, recompute, totaal_begroting
from app.commands import (
    DeleteRowCommand,
    DuplicateRowCommand,
    FillColumnCommand,
    IndexColumnCommand,
    InsertRowCommand,
    MoveBlockCommand,
    SetCellCommand,
    SetProjectFieldCommand,
)
from app.find_bar import FindBar


# ── Kolomdefinitie ───────────────────────────────────────────────────────────
# (tag, label, breedte, bewerkbaar)
# Tags met '_' zijn berekend: read-only, niet in XML.
COLUMNS: list[tuple[str, str, int, bool]] = [
    # Identificatie
    ('nr',        'Nr',                 50,  False),
    ('code',      'Code',               80,  True),
    ('s',         'S',                  36,  True),
    ('oms',       'Omschrijving',      260,  True),
    # Hoeveelheid en eenheid
    ('hvh',       'Hoeveelheid',        90,  True),
    ('enh',       'Eenheid',            60,  True),
    # Eenheidsprijzen (invoer)
    ('arb',       'Norm (uur/eh)',      90,  True),
    ('uurloon',   'Uurloon (€/u)',      90,  True),
    ('maa',       'Materiaal (€/eh)',  110,  True),
    ('mee',       'Materieel (€/eh)',  110,  True),
    ('ond',       'Onderaan. (€/eh)',  110,  True),
    ('productie', 'Factor (%)',         70,  True),
    # Berekend
    ('_prijspe',  'Prijs/eenheid (€)', 110,  False),
    ('_toturen',  'Tot. uren',          80,  False),
    ('_tot_arb',  'Tot. arbeid (€)',   110,  False),
    ('_tot_maa',  'Tot. materiaal (€)', 120, False),
    ('_tot_mee',  'Tot. materieel (€)', 120, False),
    ('_tot_ond',  'Tot. onderaan. (€)', 130, False),
    ('_totaal',   'Regeltotaal (€)',   120,  False),
    # Overige
    ('btw',       'BTW',                44,  True),
    ('code1',     'Onderaannemer',     150,  True),
    ('code4',     'Bestek / Offerte',  130,  True),
]

COL_S   = next(i for i, c in enumerate(COLUMNS) if c[0] == 's')
COL_OMS = next(i for i, c in enumerate(COLUMNS) if c[0] == 'oms')

# Numerieke kolommen → rechts uitlijnen
NUMBER_TAGS = frozenset({
    'hvh', 'arb', 'uurloon', 'maa', 'mee', 'ond', 'productie',
    '_prijspe', '_toturen',
    '_tot_arb', '_tot_maa', '_tot_mee', '_tot_ond', '_totaal',
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

# Welke velden mag je bewerken afhankelijk van het regeltype?
# Titelrijen S=1/2/3: alleen identificatie en omschrijving.
TITEL_EDITABLE_TAGS = frozenset({'code', 's', 'oms'})
# Staartrijen: ook hvh (bevat %) en enh nog zinvol; geen kosten of codes.
STAART_EDITABLE_TAGS = frozenset({'code', 's', 'oms', 'hvh', 'enh'})


def _editable_tags_for_s_code(s_code: str) -> frozenset[str] | None:
    """Geef de set tags die op dit regeltype bewerkbaar zijn.

    None betekent: regulier — alle bewerkbare kolommen blijven actief.
    """
    s = (s_code or '').strip()
    if s in ('1', '2', '3'):
        return TITEL_EDITABLE_TAGS
    if s in ('/', '%', '&', '=', '+', '-', 'a', 'b', 'c'):
        return STAART_EDITABLE_TAGS
    return None  # gewone begrotingsregel of stelpost

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
    clearCellsRequested = pyqtSignal()                # Delete/Backspace

    DISCLOSURE_HIT_PX = 18

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._block_size_for: callable | None = None
        self._oms_col: int = 0
        self._is_titel: callable | None = None
        self._drag_block_count = 1
        self._drag_src_row = -1

    # ── Configuratie door MainWindow ─────────────────────────────────────────
    def set_helpers(
        self, *, block_size_for, is_titel, oms_col: int,
    ) -> None:
        self._block_size_for = block_size_for
        self._is_titel = is_titel
        self._oms_col = oms_col

    # ── Helper: positie uit drop/mouse event (PyQt6 gebruikt position()) ─────
    @staticmethod
    def _event_pos(event):
        if hasattr(event, 'position'):
            return event.position().toPoint()
        return event.pos()

    # ── Klik op disclosure-driehoekje + onthoud blok-grootte voor drag ───────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._event_pos(event)
            idx = self.indexAt(pos)
            if idx.isValid() and self._is_titel and self._is_titel(idx.row()) \
                    and idx.column() == self._oms_col:
                cell_rect = self.visualRect(idx)
                x_in_cell = pos.x() - cell_rect.x()
                if 0 <= x_in_cell <= self.DISCLOSURE_HIT_PX:
                    self.disclosureClicked.emit(idx.row())
                    event.accept()
                    return
            # Onthouden welk blok we slepen
            if idx.isValid() and self._block_size_for is not None:
                self._drag_src_row = idx.row()
                self._drag_block_count = self._block_size_for(idx.row()) or 1
            else:
                self._drag_src_row = -1
                self._drag_block_count = 1
        super().mousePressEvent(event)

    # ── Delete / Backspace buiten edit-mode → cellen wissen ──────────────────
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) \
                and self.state() != QAbstractItemView.State.EditingState:
            self.clearCellsRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    # ── Drop: bereken (src, count, dst), defer move tot na event ─────────────
    def dropEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        src = self._drag_src_row
        if src < 0:
            src = self.currentRow()
        if src < 0:
            event.ignore()
            return
        count = self._drag_block_count or 1
        n = self.rowCount()
        if src + count > n:
            count = max(1, n - src)

        pos = self._event_pos(event)
        dst_idx = self.indexAt(pos)
        if not dst_idx.isValid():
            dst = max(0, n - count)
        else:
            dst = dst_idx.row()
            if dst > src:
                dst -= count
                if dst < 0:
                    dst = 0

        # Drop binnen het bron-blok zelf → niets doen
        if src <= dst < src + count or dst == src:
            event.ignore()
            return

        # Defer met QTimer.singleShot: laat Qt eerst klaar zijn met het
        # drop-event voordat we de tabel volledig hervullen.
        QTimer.singleShot(
            0, lambda s=src, c=count, d=dst:
            self.blockMoveRequested.emit(s, c, d),
        )
        # Belangrijk: NIET event.accept() met DragDrop mode; setDropAction
        # zorgt ervoor dat Qt's interne MoveAction-afhandeling onze rijen
        # niet ook nog eens probeert te verwijderen.
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()


class _ReturnNextRowFilter(QObject):
    """Numbers-stijl navigatie tijdens cel-bewerking.

    Vangt Return / Shift+Return / pijltjestoetsen op wanneer focus
    binnen de tabel of een cel-editor staat. Commit eerst eventuele
    bewerking, en navigeert daarna naar de aangrenzende cel.

    - Return / Shift+Return / ↓ : volgende rij (zelfde kolom)
    - ↑                         : vorige rij (zelfde kolom)
    - ← / →                     : vorige / volgende cel
    """

    NAV_KEYS = {
        Qt.Key.Key_Return, Qt.Key.Key_Enter,
        Qt.Key.Key_Up, Qt.Key.Key_Down,
        Qt.Key.Key_Left, Qt.Key.Key_Right,
    }

    def __init__(self, table: QTableWidget) -> None:
        super().__init__(table)
        self.table = table

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        key = event.key()
        if key not in self.NAV_KEYS:
            return False
        # Pijltjes alleen actief tijdens cel-bewerken — buiten edit-mode
        # heeft Qt zelf al pijltjes-navigatie.
        is_arrow = key in (
            Qt.Key.Key_Up, Qt.Key.Key_Down,
            Qt.Key.Key_Left, Qt.Key.Key_Right,
        )
        in_edit = (
            self.table.state()
            == QAbstractItemView.State.EditingState
        )
        if is_arrow and not in_edit:
            return False

        # Geldt alleen als de focus binnen de tabel staat (of in een editor
        # die als child van de tabel hangt).
        widget = obj if isinstance(obj, QWidget) else None
        w = widget
        in_table = False
        while w is not None:
            if w is self.table:
                in_table = True
                break
            w = w.parent()
        if not in_table:
            return False

        # Sluit een lopende editor netjes af (commit + close).
        focus = QApplication.focusWidget()
        if focus is not None and focus is not self.table:
            try:
                self.table.commitData(focus)
                self.table.closeEditor(
                    focus,
                    QAbstractItemDelegate.EndEditHint.NoHint,
                )
            except Exception:
                pass

        # Bepaal nieuwe positie op basis van de toets, zichtbare kolommen
        # en rijen worden gerespecteerd.
        cur = self.table.currentIndex()
        if not cur.isValid():
            return True
        r, c = cur.row(), cur.column()
        n_rows = self.table.rowCount()
        n_cols = self.table.columnCount()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down):
            r = min(r + 1, n_rows - 1)
        elif key == Qt.Key.Key_Up:
            r = max(r - 1, 0)
        elif key == Qt.Key.Key_Right:
            c = min(c + 1, n_cols - 1)
            while c < n_cols - 1 and self.table.isColumnHidden(c):
                c += 1
        elif key == Qt.Key.Key_Left:
            c = max(c - 1, 0)
            while c > 0 and self.table.isColumnHidden(c):
                c -= 1
        # Ook rij-skip als hidden (wel zeldzaam)
        while r > 0 and self.table.isRowHidden(r):
            r -= 1 if key == Qt.Key.Key_Up else -1
            r = max(0, min(n_rows - 1, r))
            if not self.table.isRowHidden(r):
                break
        self.table.setCurrentCell(r, c)
        return True


class CellFocusDelegate(QStyledItemDelegate):
    """Tekent de actieve cel als een wit blokje met dikke macOS-blue rand,
    bovenop de eventuele rij-kleur. Anders is op SelectRows nauwelijks te
    zien welke cel actief is — zeker niet op een donkere hoofdstuk-rij.
    """

    FOCUS_COLOR = QColor('#0a84ff')   # macOS systemBlue
    FOCUS_BG    = QColor('#ffffff')

    def paint(self, painter, option, index) -> None:
        if option.state & QStyle.StateFlag.State_HasFocus:
            # Standaard cel paint (bg, evt. selection-overlay, tekst)
            super().paint(painter, option, index)
            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing, False)
            # Witte vulling overschilderen voor maximale leesbaarheid
            inner = option.rect.adjusted(1, 1, -1, -1)
            painter.fillRect(inner, self.FOCUS_BG)
            # Tekst opnieuw tekenen in originele uitlijning + font + kleur
            text = index.data(Qt.ItemDataRole.DisplayRole) or ''
            font = index.data(Qt.ItemDataRole.FontRole) or option.font
            align_data = index.data(Qt.ItemDataRole.TextAlignmentRole)
            if align_data is None:
                align = (
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignVCenter
                )
            else:
                align = Qt.AlignmentFlag(int(align_data))
            painter.setFont(font)
            painter.setPen(QColor('#000000'))
            text_rect = inner.adjusted(4, 0, -4, 0)
            painter.drawText(text_rect, int(align), str(text))
            # Blauwe rand erboven
            pen = QPen(self.FOCUS_COLOR, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(option.rect.adjusted(1, 1, -2, -2))
            painter.restore()
        else:
            super().paint(painter, option, index)


class FillColumnDialog(QDialog):
    """Dialog om één kolom met dezelfde waarde te vullen."""

    def __init__(
        self, parent: QWidget,
        editable_columns: list[tuple[str, str]],
        prefill_tag: str | None = None,
        has_selection: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle('Kolom vullen met waarde')
        # Sheet-stijl op macOS (window-modal + parent = main window)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(380, 200)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cb_column = QComboBox()
        for tag, label in editable_columns:
            self.cb_column.addItem(label, tag)
        if prefill_tag:
            for i in range(self.cb_column.count()):
                if self.cb_column.itemData(i) == prefill_tag:
                    self.cb_column.setCurrentIndex(i)
                    break

        self.le_value = QLineEdit()
        self.le_value.setPlaceholderText('Bijvoorbeeld 45 of 25 of OHD 03')

        form.addRow('Kolom:', self.cb_column)
        form.addRow('Nieuwe waarde:', self.le_value)
        layout.addLayout(form)

        # Bereik
        self.rb_all = QRadioButton('Alle rijen')
        self.rb_sel = QRadioButton(
            f'Alleen geselecteerde rijen'
            f'{"" if has_selection else " (geen selectie)"}'
        )
        self.rb_sel.setEnabled(has_selection)
        if has_selection:
            self.rb_sel.setChecked(True)
        else:
            self.rb_all.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.rb_all)
        group.addButton(self.rb_sel)

        layout.addSpacing(6)
        layout.addWidget(QLabel('Bereik:'))
        layout.addWidget(self.rb_all)
        layout.addWidget(self.rb_sel)

        # Apple HIG: named actie-knop i.p.v. OK
        bb = QDialogButtonBox()
        btn_apply = bb.addButton(
            'Vul kolom', QDialogButtonBox.ButtonRole.AcceptRole
        )
        bb.addButton(
            'Annuleren', QDialogButtonBox.ButtonRole.RejectRole
        )
        btn_apply.setDefault(True)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addStretch(1)
        layout.addWidget(bb)

        self.le_value.setFocus()

    @property
    def selected_tag(self) -> str:
        return self.cb_column.currentData()

    @property
    def selected_value(self) -> str:
        return self.le_value.text()

    @property
    def use_selection(self) -> bool:
        return self.rb_sel.isChecked()


class IndexColumnDialog(QDialog):
    """Indexeer een kostensoort met een percentage, optioneel per selectie."""

    KOSTEN_VELDEN = (
        ('arb',     'Norm (uur/eh)'),
        ('uurloon', 'Uurloon'),
        ('maa',     'Materiaal'),
        ('mee',     'Materieel'),
        ('ond',     'Onderaan.'),
    )

    def __init__(
        self, parent: QWidget,
        prefill_tag: str | None = None,
        has_selection: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle('Kolom indexeren')
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(380, 220)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.cb_tag = QComboBox()
        for tag, label in self.KOSTEN_VELDEN:
            self.cb_tag.addItem(label, tag)
        if prefill_tag:
            for i in range(self.cb_tag.count()):
                if self.cb_tag.itemData(i) == prefill_tag:
                    self.cb_tag.setCurrentIndex(i)
                    break

        self.le_pct = QLineEdit()
        self.le_pct.setPlaceholderText('Bijv. 5 voor +5% of -3 voor -3%')
        form.addRow('Kostensoort:', self.cb_tag)
        form.addRow('Percentage (%):', self.le_pct)
        layout.addLayout(form)

        self.rb_all = QRadioButton('Alle begrotingsregels')
        self.rb_sel = QRadioButton(
            f'Alleen geselecteerde rijen'
            f'{"" if has_selection else " (geen selectie)"}'
        )
        self.rb_sel.setEnabled(has_selection)
        if has_selection:
            self.rb_sel.setChecked(True)
        else:
            self.rb_all.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.rb_all)
        group.addButton(self.rb_sel)
        layout.addSpacing(6)
        layout.addWidget(QLabel('Bereik:'))
        layout.addWidget(self.rb_all)
        layout.addWidget(self.rb_sel)

        bb = QDialogButtonBox()
        btn_apply = bb.addButton(
            'Indexeer', QDialogButtonBox.ButtonRole.AcceptRole
        )
        bb.addButton('Annuleren', QDialogButtonBox.ButtonRole.RejectRole)
        btn_apply.setDefault(True)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addStretch(1)
        layout.addWidget(bb)
        self.le_pct.setFocus()

    @property
    def selected_tag(self) -> str:
        return self.cb_tag.currentData()

    @property
    def percentage(self) -> float | None:
        return parse_nl_number(self.le_pct.text())

    @property
    def use_selection(self) -> bool:
        return self.rb_sel.isChecked()


class BrutoInputDialog(QDialog):
    """Bruto-invoer: voer totaalbedragen per kostensoort in en zie live
    wat de prijs per eenheid wordt. Toepassen schrijft alleen niet-lege
    velden weg via één undo-macro.
    """

    KOSTEN_VELDEN = (
        ('arb_uur', 'Totaal arbeid (€)',      'arb',     True),
        ('maa',     'Totaal materiaal (€)',   'maa',     False),
        ('mee',     'Totaal materieel (€)',   'mee',     False),
        ('ond',     'Totaal onderaan. (€)',   'ond',     False),
    )

    def __init__(
        self, parent: QWidget,
        hoeveelheid: float, eenheid: str, uurloon: float,
        productie: float,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle('Bruto invoeren')
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(420, 320)

        self.hvh = hoeveelheid
        self.eenheid = eenheid or 'eh'
        self.uurloon = uurloon
        self.factor = 1.0 + productie / 100.0

        layout = QVBoxLayout(self)
        info = QLabel(
            f'Hoeveelheid: <b>{format_nl_hvh(hoeveelheid)} {self.eenheid}</b>'
            f' &nbsp; · &nbsp; Uurloon: € {format_nl(uurloon)}'
            f' &nbsp; · &nbsp; Factor: {format_nl(productie, 0)}%'
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)

        form = QFormLayout()
        self.fields: dict[str, QLineEdit] = {}
        self.previews: dict[str, QLabel] = {}
        for key, label, _tag, _is_arb in self.KOSTEN_VELDEN:
            le = QLineEdit()
            le.setPlaceholderText('leeg laten = niet wijzigen')
            le.textChanged.connect(self._update_previews)
            preview = QLabel('—')
            preview.setStyleSheet('color: palette(mid);')
            self.fields[key] = le
            self.previews[key] = preview
            row = QVBoxLayout()
            row.setSpacing(2)
            row.addWidget(le)
            row.addWidget(preview)
            holder = QWidget(); holder.setLayout(row)
            form.addRow(label, holder)
        layout.addLayout(form)

        bb = QDialogButtonBox()
        self.btn_apply = bb.addButton(
            'Toepassen', QDialogButtonBox.ButtonRole.AcceptRole
        )
        bb.addButton('Annuleren', QDialogButtonBox.ButtonRole.RejectRole)
        self.btn_apply.setDefault(True)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addStretch(1)
        layout.addWidget(bb)

        self._update_previews()
        self.fields['ond'].setFocus()

    def _per_eh(self, key: str) -> float | None:
        """Bepaal de per-eenheid waarde uit het totaal in dit veld."""
        total = parse_nl_number(self.fields[key].text())
        if total is None or self.hvh <= 0:
            return None
        if key == 'arb_uur':
            # Arbeid: totaal = hvh * arb * uurloon * factor → per uren-eenheid
            denom = self.hvh * self.uurloon * self.factor
            return total / denom if denom else None
        # Andere kostensoort: totaal = hvh * waarde * factor → waarde = totaal / (hvh*factor)
        denom = self.hvh * self.factor
        return total / denom if denom else None

    def _update_previews(self) -> None:
        for key, _label, _tag, is_arb in self.KOSTEN_VELDEN:
            v = self._per_eh(key)
            if v is None:
                self.previews[key].setText('—')
            elif is_arb:
                self.previews[key].setText(
                    f'→ {format_nl(v, 3)} uur per {self.eenheid}'
                )
            else:
                self.previews[key].setText(
                    f'→ € {format_nl(v)} per {self.eenheid}'
                )

    def values_to_apply(self) -> dict[str, str]:
        """Geeft {tag: waarde} voor alle ingevulde velden, in NL-formaat."""
        out: dict[str, str] = {}
        for key, _label, tag, is_arb in self.KOSTEN_VELDEN:
            v = self._per_eh(key)
            if v is None:
                continue
            if is_arb:
                out['arb'] = format_nl(v, 3)
            else:
                out[tag] = format_nl(v)
        return out


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

        # Find-bar state
        self._find_query: str = ''
        self._find_matches: list[tuple[int, int]] = []  # (row, col)
        self._find_active: int = -1   # index in _find_matches

        self._build_actions()
        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._update_title()
        self._update_action_state()
        self.resize(1540, 800)

        # Return / Shift+Return → volgende rij (Numbers-stijl), ook tijdens
        # cel-bewerken
        self._return_filter = _ReturnNextRowFilter(self.table)
        QApplication.instance().installEventFilter(self._return_filter)

        # Persistente instellingen herstellen (geometrie, kolommen)
        self._restore_settings()

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

        # Kolom vullen
        self.act_fill_column = QAction(
            'Kolom vullen met waarde…', self, shortcut='Ctrl+Shift+F',
        )
        self.act_fill_column.triggered.connect(self.on_fill_column)

        # Bruto invoeren (⌘B)
        self.act_bruto = QAction(
            'Bruto invoeren…', self, shortcut='Ctrl+B',
        )
        self.act_bruto.triggered.connect(self.on_bruto_invoeren)

        # Indexeren (⌘⇧I)
        self.act_index = QAction(
            'Kolom indexeren…', self, shortcut='Ctrl+Shift+I',
        )
        self.act_index.triggered.connect(self.on_index_column)

        # Inspector toggle (⌘I op macOS, Ctrl+I elders)
        self.act_toggle_inspector = QAction(
            'Toon Inspector', self, shortcut='Ctrl+I', checkable=True,
        )
        self.act_toggle_inspector.triggered.connect(
            self.on_toggle_inspector
        )

        # Find-bar (⌘F)
        self.act_find = QAction(
            'Zoeken…', self, shortcut=QKeySequence.StandardKey.Find,
        )
        self.act_find.triggered.connect(self.on_find_open)
        self.act_find_next = QAction(
            'Volgende', self, shortcut=QKeySequence.StandardKey.FindNext,
        )
        self.act_find_next.triggered.connect(self.on_find_next)
        self.act_find_prev = QAction(
            'Vorige', self, shortcut=QKeySequence.StandardKey.FindPrevious,
        )
        self.act_find_prev.triggered.connect(self.on_find_prev)

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

        # Projectvelden komen in een Inspector-zijbalk (zie _build_inspector).
        self.f_kop = QLineEdit(); self.f_kop.setPlaceholderText('20261.00260')
        self.f_r1  = QLineEdit(); self.f_r1.setPlaceholderText('Projectnaam')
        self.f_r2  = QLineEdit(); self.f_r2.setPlaceholderText('Adres')
        self.f_r4  = QLineEdit(); self.f_r4.setPlaceholderText('Omschrijving werkzaamheden')
        for fld in (self.f_kop, self.f_r1, self.f_r2, self.f_r4):
            fld.editingFinished.connect(self._on_project_edit)

        # Find-bar (slide-down boven de tabel)
        self.find_bar = FindBar(self)
        self.find_bar.queryChanged.connect(self._on_find_query)
        self.find_bar.nextRequested.connect(self._find_advance)
        self.find_bar.previousRequested.connect(self._find_back)
        self.find_bar.closed.connect(self._on_find_closed)
        root.addWidget(self.find_bar)

        # Begrotingstabel met drag & drop en disclosure-klik
        self.table = DnDTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in COLUMNS])
        for i, (_, _, w, _) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, w)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(False)
        # Sleep aan een kolomkop (klik op de label, NIET op de resize-rand)
        # om de volgorde te wijzigen. saveState() onthoudt het.
        hh.setSectionsMovable(True)
        hh.setSectionsClickable(True)
        hh.setFirstSectionMovable(True)
        hh.sectionMoved.connect(self._on_section_moved)
        # Rechtermuisklik op een kolomkop → snel-menu
        hh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._on_header_context_menu)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setGridStyle(Qt.PenStyle.SolidLine)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setAlternatingRowColors(False)
        self.table.setTabKeyNavigation(True)   # Tab → volgende cel
        # Edit-triggers ruim zetten zodat toetsenbordnavigatie soepel werkt:
        # - dubbelklik (standaard)
        # - F2 (EditKeyPressed)
        # - één klik op een al geselecteerde cel (SelectedClicked)
        # - elke toetsaanslag op de cel begint direct te typen (AnyKeyPressed)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )

        # Drag & drop — DragDrop mode (geen InternalMove) zodat Qt's
        # eigen rij-verwijdering ons niet in de weg zit.
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.setDragDropMode(
            QAbstractItemView.DragDropMode.DragDrop
        )
        self.table.setDefaultDropAction(Qt.DropAction.MoveAction)

        self.table.set_helpers(
            block_size_for=self._safe_block_size,
            is_titel=self._row_is_titel,
            oms_col=COL_OMS,
        )
        self.table.blockMoveRequested.connect(self._on_block_move)
        self.table.disclosureClicked.connect(self._on_disclosure_clicked)
        self.table.clearCellsRequested.connect(self.on_clear_cells)
        # Aangepaste cel-focus-rand (macOS systemBlue) zodat de actieve cel
        # binnen een SelectRows-selectie duidelijk te zien is.
        self.table.setItemDelegate(CellFocusDelegate(self.table))

        self.table.itemChanged.connect(self._on_cell_changed)
        root.addWidget(self.table)

        self.setCentralWidget(central)
        self._build_inspector()

    def _build_inspector(self) -> None:
        """Inspector-zijbalk (rechts) voor projectgegevens. ⌘I toggle't."""
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(10)

        gb_proj = QGroupBox('Project')
        gp_form = QFormLayout(gb_proj)
        gp_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        gp_form.addRow('Nummer', self.f_kop)
        gp_form.addRow('Naam',   self.f_r1)

        gb_loc = QGroupBox('Locatie')
        gl_form = QFormLayout(gb_loc)
        gl_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        gl_form.addRow('Adres', self.f_r2)

        gb_omschr = QGroupBox('Omschrijving')
        go_form = QFormLayout(gb_omschr)
        go_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        go_form.addRow('Werk', self.f_r4)

        v.addWidget(gb_proj)
        v.addWidget(gb_loc)
        v.addWidget(gb_omschr)
        v.addStretch(1)

        self.inspector = QDockWidget('Inspector', self)
        self.inspector.setObjectName('inspector')
        self.inspector.setWidget(panel)
        self.inspector.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.inspector.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.inspector,
        )

        # Persist visibility tussen sessies
        settings = QSettings('CalcMacApp', 'CalcMacApp')
        visible = settings.value(
            'window/inspectorVisible', True, type=bool,
        )
        self.inspector.setVisible(visible)
        self.inspector.visibilityChanged.connect(
            self._on_inspector_visibility_changed
        )

    def _on_inspector_visibility_changed(self, visible: bool) -> None:
        QSettings('CalcMacApp', 'CalcMacApp').setValue(
            'window/inspectorVisible', visible,
        )
        if hasattr(self, 'act_toggle_inspector'):
            self.act_toggle_inspector.setChecked(visible)

    def on_toggle_inspector(self) -> None:
        self.inspector.setVisible(not self.inspector.isVisible())

    def _on_section_moved(self, _logical_idx, _old_visual, new_visual) -> None:
        """Feedback wanneer kolom is versleept (sectionMoved signal)."""
        if 0 <= new_visual < len(COLUMNS):
            label = COLUMNS[new_visual][1]
            self.statusBar().showMessage(
                f'Kolom "{label}" verplaatst', 2000,
            )
        # Direct opslaan zodat herstart de nieuwe volgorde behoudt
        self._save_settings()

    # ── Persistente instellingen ─────────────────────────────────────────────
    def _settings(self) -> QSettings:
        return QSettings('CalcMacApp', 'CalcMacApp')

    def _save_settings(self) -> None:
        s = self._settings()
        s.setValue('window/geometry', self.saveGeometry())
        s.setValue('window/state',    self.saveState())
        s.setValue('table/header',    self.table.horizontalHeader().saveState())

    def _restore_settings(self) -> None:
        s = self._settings()
        geom = s.value('window/geometry')
        if geom is not None:
            self.restoreGeometry(geom)
        state = s.value('window/state')
        if state is not None:
            self.restoreState(state)
        hdr_state = s.value('table/header')
        if hdr_state is not None:
            self.table.horizontalHeader().restoreState(hdr_state)
            # Synchroniseer de checkbox-acties met de herstelde
            # zichtbaarheid uit de header-state.
            for col, act in self._col_actions.items():
                act.blockSignals(True)
                act.setChecked(not self.table.isColumnHidden(col))
                act.blockSignals(False)

    # ── Kolommen tonen/verbergen ─────────────────────────────────────────────
    def _build_columns_menu(self, menu: QMenu) -> None:
        """Vult een submenu met checkbare items per kolom (één per kolom).
        De gestreepte structurele kolommen Nr, S en Omschrijving zijn altijd
        zichtbaar — die hebben geen toggle.
        """
        self._col_actions: dict[int, QAction] = {}
        always_visible = {'nr', 's', 'oms'}
        for col, (tag, label, _w, _e) in enumerate(COLUMNS):
            if tag in always_visible:
                continue
            act = QAction(label, self, checkable=True)
            act.setChecked(not self.table.isColumnHidden(col))
            act.toggled.connect(
                lambda checked, c=col: self._set_column_visible(c, checked)
            )
            menu.addAction(act)
            self._col_actions[col] = act

    def _set_column_visible(self, col: int, visible: bool) -> None:
        self.table.setColumnHidden(col, not visible)
        if col in self._col_actions:
            act = self._col_actions[col]
            if act.isChecked() != visible:
                act.blockSignals(True)
                act.setChecked(visible)
                act.blockSignals(False)

    # ── Find-bar slots ────────────────────────────────────────────────────────
    def on_find_open(self) -> None:
        self.find_bar.show_bar()

    def on_find_next(self) -> None:
        self.find_bar.go_next()

    def on_find_prev(self) -> None:
        self.find_bar.go_previous()

    def _on_find_query(self, query: str) -> None:
        self._find_query = query
        self._compute_find_matches()
        self._find_active = 0 if self._find_matches else -1
        self._update_find_count()
        self._apply_find_highlights()
        if self._find_active >= 0:
            self._scroll_to_active_match()

    def _on_find_closed(self) -> None:
        self._find_query = ''
        self._find_matches.clear()
        self._find_active = -1
        self._apply_find_highlights()

    def _compute_find_matches(self) -> None:
        self._find_matches = []
        q = self._find_query.casefold()
        if not q or self.doc is None:
            return
        for r in range(self.doc.row_count()):
            for c, (tag, _, _, _) in enumerate(COLUMNS):
                if tag.startswith('_'):
                    continue
                text = self.doc.get_row_field(r, tag)
                if text and q in text.casefold():
                    self._find_matches.append((r, c))

    def _update_find_count(self) -> None:
        n = len(self._find_matches)
        if n == 0:
            self.find_bar.set_count_text(
                'geen' if self._find_query else ''
            )
        else:
            self.find_bar.set_count_text(
                f'{self._find_active + 1} van {n}'
            )

    def _find_advance(self) -> None:
        if not self._find_matches:
            return
        self._find_active = (self._find_active + 1) % len(self._find_matches)
        self._update_find_count()
        self._apply_find_highlights()
        self._scroll_to_active_match()

    def _find_back(self) -> None:
        if not self._find_matches:
            return
        self._find_active = (
            self._find_active - 1
        ) % len(self._find_matches)
        self._update_find_count()
        self._apply_find_highlights()
        self._scroll_to_active_match()

    def _scroll_to_active_match(self) -> None:
        if 0 <= self._find_active < len(self._find_matches):
            r, c = self._find_matches[self._find_active]
            self.table.setCurrentCell(r, c)
            item = self.table.item(r, c)
            if item is not None:
                self.table.scrollToItem(item)

    def _apply_find_highlights(self) -> None:
        """Voeg gele achtergrond toe aan match-cellen; haal weg als geen
        find-state actief. Wordt na elke recompute opnieuw aangeroepen.
        """
        if not self.doc:
            return
        match_set = {
            (r, c) for (r, c) in self._find_matches
        }
        active_cell = (
            self._find_matches[self._find_active]
            if 0 <= self._find_active < len(self._find_matches) else None
        )
        self.table.blockSignals(True)
        try:
            for r in range(self.doc.row_count()):
                # Rebuild row styling first, dan eventueel highlight overschrijven
                s_code = self.doc.get_row_field(r, 's').strip()
                self._apply_row_style(r, s_code)
                for c in range(len(COLUMNS)):
                    if (r, c) not in match_set:
                        continue
                    item = self.table.item(r, c)
                    if item is None:
                        continue
                    if (r, c) == active_cell:
                        item.setBackground(QBrush(QColor('#ffe066')))
                    else:
                        item.setBackground(QBrush(QColor('#fff5cc')))
        finally:
            self.table.blockSignals(False)

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
        b.addAction(self.act_bruto)
        b.addAction(self.act_fill_column)
        b.addAction(self.act_index)
        b.addSeparator()
        b.addAction(self.act_find)
        b.addAction(self.act_find_next)
        b.addAction(self.act_find_prev)
        b.addSeparator()
        b.addAction(self.act_collapse)
        b.addAction(self.act_collapse_level)

        # Beeld-menu
        v = m.addMenu('&Beeld')
        v.addAction(self.act_toggle_inspector)
        v.addSeparator()
        self._cols_menu = v.addMenu('Kolommen')
        self._build_columns_menu(self._cols_menu)

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
        # Bouwkosten subtiel; eindtotaal vetgedrukt rechts ervan.
        self._lbl_bouwkosten = QLabel('Geen bestand geopend')
        self._lbl_bouwkosten.setStyleSheet('color: palette(mid);')
        self._lbl_eindtotaal = QLabel('')
        f = self._lbl_eindtotaal.font(); f.setBold(True)
        self._lbl_eindtotaal.setFont(f)
        # Compatibiliteit met oudere code: alias
        self._lbl_totaal = self._lbl_bouwkosten
        sb.addPermanentWidget(self._lbl_bouwkosten)
        sb.addPermanentWidget(self._lbl_eindtotaal)

    # ── Titelstatus + actie-enabled ───────────────────────────────────────────
    @property
    def _dirty(self) -> bool:
        return not self.undo_stack.isClean()

    def _update_title(self) -> None:
        """Native macOS-titel via setWindowFilePath + setWindowModified.
        Het [*] is een placeholder die Qt vervangt door een puntje in de
        close-knop wanneer het document modified is.
        """
        if self.doc and self.doc.path:
            self.setWindowFilePath(self.doc.path)
            self.setWindowTitle(f'{Path(self.doc.path).name}[*]')
        else:
            self.setWindowFilePath('')
            self.setWindowTitle('CalcMacApp')
        self.setWindowModified(self._dirty)

    def _update_action_state(self) -> None:
        has_doc = self.doc is not None
        self.act_save.setEnabled(has_doc and self._dirty)
        self.act_save_as.setEnabled(has_doc)
        # Rij-acties alleen bij geopend document
        for a in (
            self.act_row_add_below, self.act_row_add_above,
            self.act_row_delete,    self.act_row_dup,
            self.act_cell_dup_above,
            self.act_fill_column,   self.act_index, self.act_bruto,
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
        if path:
            self.load_path(path)

    def load_path(self, path: str) -> None:
        """Open een bestand op pad zonder dialoog. Wordt gebruikt door:
        - on_open (na het kiezen van een pad)
        - sys.argv[1] bij opstarten
        - Finder-FileOpen events op macOS (dubbelklik in Finder)
        """
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
    def _format_cell_value(
        self, tag: str, raw: str, col_editable: bool,
        allowed_tags: frozenset[str] | None,
    ) -> str:
        """Bepaal de te tonen tekst voor een cel.

        Numerieke kolommen krijgen altijd 2 decimalen. Lege cellen waar
        het regeltype WEL invoer toelaat, krijgen '0,00' zodat de tabel
        visueel uniform is. Niet-bewerkbare cellen blijven leeg.
        """
        if tag not in NUMBER_TAGS:
            return raw
        cell_editable = col_editable and (
            allowed_tags is None or tag in allowed_tags
        )
        v = parse_nl_number(raw)
        if v is None:
            return format_nl(0.0, 2) if cell_editable else ''
        return format_nl(v, 2)

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
                allowed = _editable_tags_for_s_code(s_code)
                for c, (tag, _, _, editable) in enumerate(COLUMNS):
                    if tag.startswith('_'):
                        value = ''
                    else:
                        raw = self.doc.get_row_field(r, tag)
                        value = self._format_cell_value(
                            tag, raw, editable, allowed,
                        )
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

        editable_tags = _editable_tags_for_s_code(s_code)

        for c, (tag, _, _, col_editable) in enumerate(COLUMNS):
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

            # Bewerkbaarheid op basis van regeltype:
            # - berekende kolommen blijven altijd read-only
            # - kolom uit COLUMNS niet als bewerkbaar gemarkeerd → read-only
            # - rij-type beperkt verder welke kolommen bewerkbaar zijn
            cell_editable = col_editable and not is_calc
            if cell_editable and editable_tags is not None \
                    and tag not in editable_tags:
                cell_editable = False

            flags = item.flags()
            if cell_editable:
                flags |= Qt.ItemFlag.ItemIsEditable
            else:
                flags &= ~Qt.ItemFlag.ItemIsEditable
            item.setFlags(flags)

            # Subtiel "disabled" voor cellen die wel een waarde HEBBEN maar
            # voor dit regeltype niet bewerkt mogen worden — alleen als de
            # rij geen eigen tekstkleur heeft (titels hebben dat al).
            is_locked = (
                editable_tags is not None
                and tag not in editable_tags
                and not is_calc
                and col_editable
            )
            if is_locked and style['fg'] is None:
                item.setForeground(QBrush(QColor('#a0a0a4')))
            else:
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
            '_toturen': 'toturen',
            '_tot_arb': 'tot_arb',
            '_tot_maa': 'tot_maa',
            '_tot_mee': 'tot_mee',
            '_tot_ond': 'tot_ond',
            '_totaal':  'totaal',
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

        bouwkosten = totaal_begroting(results, rows_in)
        self._lbl_bouwkosten.setText(
            f'Bouwkosten: € {format_nl(bouwkosten)}'
        )
        eindtotaal = eindtotaal_begroting(results, rows_in)
        if eindtotaal is not None:
            self._lbl_eindtotaal.setText(
                f'Eindtotaal: € {format_nl(eindtotaal)}'
            )
            self._lbl_eindtotaal.setVisible(True)
        else:
            self._lbl_eindtotaal.setText('')
            self._lbl_eindtotaal.setVisible(False)

    # ── Celwijzigingen ───────────────────────────────────────────────────────
    def _on_project_edit(self) -> None:
        if not self.doc:
            return
        for fld, tag in (
            (self.f_kop, 'kop'), (self.f_r1, 'r1'),
            (self.f_r2,  'r2'),  (self.f_r4, 'r4'),
        ):
            old = self.doc.get_project_field(tag)
            new = fld.text()
            if old != new:
                self.undo_stack.push(
                    SetProjectFieldCommand(self, tag, old, new)
                )

    def sync_project_field(self, tag: str) -> None:
        """Update een QLineEdit na een undo/redo van een project-veld."""
        fld = {
            'kop': self.f_kop, 'r1': self.f_r1,
            'r2':  self.f_r2,  'r4': self.f_r4,
        }.get(tag)
        if fld is None or self.doc is None:
            return
        fld.blockSignals(True)
        fld.setText(self.doc.get_project_field(tag))
        fld.blockSignals(False)

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

        # Numerieke kolommen normaliseren naar canonieke NL-notatie met
        # 2 decimalen, zodat de XML schoon blijft en weergave consistent.
        if tag in NUMBER_TAGS:
            v = parse_nl_number(new_value)
            new_value = format_nl(v, 2) if v is not None else ''

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
        oms = self.doc.get_row_field(idx, 'oms').strip()
        if oms:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle('Rij verwijderen')
            box.setText(f'Verwijder regel “{oms[:60]}”?')
            box.setInformativeText('Deze actie kun je ongedaan maken met ⌘Z.')
            btn_cancel = box.addButton(
                'Annuleren', QMessageBox.ButtonRole.RejectRole
            )
            btn_delete = box.addButton(
                'Verwijderen', QMessageBox.ButtonRole.DestructiveRole
            )
            box.setDefaultButton(btn_cancel)
            box.setWindowModality(Qt.WindowModality.WindowModal)
            box.exec()
            if box.clickedButton() is not btn_delete:
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

    # ── Cel(en) wissen via Delete / Backspace ────────────────────────────────
    def on_clear_cells(self) -> None:
        """Wis de inhoud van de actieve kolom op alle geselecteerde rijen.

        - Alleen bewerkbare cellen (niet berekend, niet structureel
          read-only voor het regeltype) worden gewist.
        - Lege cellen worden overgeslagen.
        - Eén ⌘Z draait alles tegelijk terug.
        """
        if not self.doc:
            return
        col = self.table.currentColumn()
        if col < 0:
            return
        tag, _label, _w, col_editable = COLUMNS[col]
        if not col_editable or tag.startswith('_'):
            return  # berekende of read-only kolom
        sel = self._selected_row_indices()
        rows = sel if sel else [self._current_row()]
        affected: list[tuple[int, str]] = []
        for r in rows:
            s_code = self.doc.get_row_field(r, 's').strip()
            allowed = _editable_tags_for_s_code(s_code)
            if allowed is not None and tag not in allowed:
                continue
            old = self.doc.get_row_field(r, tag)
            if old:
                affected.append((r, old))
        if not affected:
            return
        if len(affected) == 1:
            r, old = affected[0]
            self.undo_stack.push(SetCellCommand(self, r, tag, old, ''))
        else:
            self.undo_stack.beginMacro(
                f'Cellen wissen ({len(affected)})'
            )
            try:
                for r, old in affected:
                    self.undo_stack.push(
                        SetCellCommand(self, r, tag, old, '')
                    )
            finally:
                self.undo_stack.endMacro()

    # ── Kolom vullen ─────────────────────────────────────────────────────────
    def _editable_columns_for_dialog(self) -> list[tuple[str, str]]:
        """Geef (tag, label) voor kolommen die je via 'Kolom vullen' mag
        bewerken — alleen XML-velden, geen berekende of structurele kolommen.
        """
        skip = {'nr', 's', 'oms'}  # nr is auto, s is structurele code, oms is per regel
        return [
            (tag, label)
            for tag, label, _w, editable in COLUMNS
            if editable and not tag.startswith('_') and tag not in skip
        ]

    def _selected_row_indices(self) -> list[int]:
        rows: set[int] = set()
        for idx in self.table.selectionModel().selectedIndexes():
            rows.add(idx.row())
        return sorted(rows)

    def on_fill_column(self, prefill_tag: str | None = None) -> None:
        if not self.doc:
            return
        editable = self._editable_columns_for_dialog()
        if not editable:
            return
        sel_rows = self._selected_row_indices()
        dlg = FillColumnDialog(
            self, editable,
            prefill_tag=prefill_tag,
            has_selection=bool(sel_rows),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        tag = dlg.selected_tag
        value = dlg.selected_value
        candidate_rows = sel_rows if dlg.use_selection else list(range(
            self.doc.row_count()
        ))
        # Sla rijen over waar dit veld niet bewerkbaar is voor het regeltype
        # (bv. titels en staart-rijen voor een Uurloon-vulling).
        rows: list[int] = []
        for r in candidate_rows:
            s_code = self.doc.get_row_field(r, 's').strip()
            allowed = _editable_tags_for_s_code(s_code)
            if allowed is None or tag in allowed:
                rows.append(r)
        if not rows:
            QMessageBox.information(
                self, 'Kolom vullen',
                'Geen rijen om in te vullen — alle kandidaten zijn titels '
                'of staart-rijen waar dit veld niet relevant is.',
            )
            return
        skipped = len(candidate_rows) - len(rows)
        self.undo_stack.push(FillColumnCommand(self, tag, value, rows))
        if skipped:
            self.statusBar().showMessage(
                f'Kolom gevuld op {len(rows)} regels — '
                f'{skipped} titel/staart-rijen overgeslagen.', 4000,
            )

    # ── Indexeren ────────────────────────────────────────────────────────────
    def on_index_column(self, prefill_tag: str | None = None) -> None:
        if not self.doc:
            return
        sel = self._selected_row_indices()
        dlg = IndexColumnDialog(
            self, prefill_tag=prefill_tag, has_selection=bool(sel),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        pct = dlg.percentage
        if pct is None:
            QMessageBox.warning(
                self, 'Indexeren', 'Geef een geldig percentage op.',
            )
            return
        tag = dlg.selected_tag
        candidate = sel if dlg.use_selection else list(range(
            self.doc.row_count()
        ))
        # Filter naar bewerkbare-kolom-voor-regeltype
        rows: list[int] = []
        for r in candidate:
            s_code = self.doc.get_row_field(r, 's').strip()
            allowed = _editable_tags_for_s_code(s_code)
            if allowed is not None and tag not in allowed:
                continue
            if self.doc.get_row_field(r, tag).strip():
                rows.append(r)
        if not rows:
            QMessageBox.information(
                self, 'Indexeren',
                'Geen rijen om te indexeren — er zijn geen ingevulde '
                f'waarden in de kolom voor de geselecteerde kostensoort.',
            )
            return
        self.undo_stack.push(IndexColumnCommand(self, tag, pct, rows))
        self.statusBar().showMessage(
            f'Geïndexeerd met {pct:+g}% op {len(rows)} regels.', 4000,
        )

    # ── Bruto-invoer ─────────────────────────────────────────────────────────
    def on_bruto_invoeren(self) -> None:
        if not self.doc or self.doc.row_count() == 0:
            return
        row = self._current_row()
        s_code = self.doc.get_row_field(row, 's').strip()
        # Alleen begrotingsregels (geen titels, geen staart)
        if s_code in ('1', '2', '3', '/', '%', '&', '=', '+', '-', 'a', 'b', 'c'):
            QMessageBox.information(
                self, 'Bruto invoeren',
                'Bruto-invoer werkt alleen op een begrotingsregel.',
            )
            return
        hvh = parse_nl_number(self.doc.get_row_field(row, 'hvh')) or 0.0
        if hvh <= 0:
            QMessageBox.information(
                self, 'Bruto invoeren',
                'Vul eerst een hoeveelheid groter dan 0 in.',
            )
            return
        ul = parse_nl_number(self.doc.get_row_field(row, 'uurloon'))
        if ul is None or ul == 0:
            ul = parse_nl_number(self.doc.get_project_field('ul')) or 45.0
        prod = parse_nl_number(self.doc.get_row_field(row, 'productie')) or 0.0
        enh = self.doc.get_row_field(row, 'enh')

        dlg = BrutoInputDialog(self, hvh, enh, ul, prod)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        updates = dlg.values_to_apply()
        if not updates:
            return
        # Eén undo-macro voor alles
        self.undo_stack.beginMacro('Bruto invoer')
        try:
            for tag, new_value in updates.items():
                old_value = self.doc.get_row_field(row, tag)
                if old_value != new_value:
                    self.undo_stack.push(
                        SetCellCommand(self, row, tag, old_value, new_value)
                    )
        finally:
            self.undo_stack.endMacro()

    def _on_header_context_menu(self, pos) -> None:
        """Rechtermuisklik op een kolomkop → contextmenu met
        'Vul kolom…', 'Indexeer kolom…', 'Verplaats links/rechts',
        'Verberg', en submenu 'Kolommen…'.
        """
        hh = self.table.horizontalHeader()
        col = hh.logicalIndexAt(pos)
        if col < 0 or col >= len(COLUMNS):
            return
        tag, label, _w, editable = COLUMNS[col]
        is_calc = tag.startswith('_')
        is_structural = tag in ('nr', 's', 'oms')
        index_eligible = tag in ('arb', 'maa', 'mee', 'ond', 'uurloon')

        menu = QMenu(self)
        act_fill = act_index = act_left = act_right = act_hide = None

        if self.doc and editable and not is_calc:
            act_fill = menu.addAction(f'Vul "{label}" met waarde…')
        if self.doc and index_eligible:
            act_index = menu.addAction(f'Indexeer "{label}" met %…')
        if act_fill or act_index:
            menu.addSeparator()

        # Verplaats kolom — werkt altijd, ongeacht macOS-stijl
        visual = hh.visualIndex(col)
        if visual > 0:
            act_left = menu.addAction(f'Verplaats "{label}" naar links')
        if visual < hh.count() - 1:
            act_right = menu.addAction(f'Verplaats "{label}" naar rechts')
        if act_left or act_right:
            menu.addSeparator()

        if not is_structural:
            act_hide = menu.addAction(f'Verberg "{label}"')

        sub = menu.addMenu('Kolommen…')
        for col_i, action in self._col_actions.items():
            sub.addAction(action)

        chosen = menu.exec(hh.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_fill:
            self.on_fill_column(prefill_tag=tag)
        elif chosen is act_index:
            self.on_index_column(prefill_tag=tag)
        elif chosen is act_left:
            hh.moveSection(visual, visual - 1)
        elif chosen is act_right:
            hh.moveSection(visual, visual + 1)
        elif chosen is act_hide:
            self._set_column_visible(col, False)

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
        # Sla instellingen ALTIJD op — ook als het document niet dirty is
        self._save_settings()
        if not self._dirty:
            event.accept()
            return
        name = (
            Path(self.doc.path).name if self.doc and self.doc.path
            else 'dit document'
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle('Niet-opgeslagen wijzigingen')
        box.setText(f'Wil je de wijzigingen in “{name}” bewaren?')
        box.setInformativeText(
            'Als je niet bewaart, gaan je wijzigingen verloren.'
        )
        btn_save    = box.addButton(
            'Bewaren', QMessageBox.ButtonRole.AcceptRole
        )
        btn_discard = box.addButton(
            'Niet bewaren', QMessageBox.ButtonRole.DestructiveRole
        )
        btn_cancel  = box.addButton(
            'Annuleren', QMessageBox.ButtonRole.RejectRole
        )
        box.setDefaultButton(btn_save)
        box.setWindowModality(Qt.WindowModality.WindowModal)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_save:
            self.on_save()
            event.accept() if not self._dirty else event.ignore()
        elif clicked is btn_discard:
            event.accept()
        else:
            event.ignore()


class _CalcApplication(QApplication):
    """QApplication die FileOpen-events (Finder dubbelklik op .c4y) doorgeeft.

    Op macOS stuurt het systeem een QEvent.Type.FileOpen wanneer een
    geassocieerd document met de app wordt geopend — ook na de start.
    Wij vangen die op en sturen het pad naar de actieve MainWindow.
    """

    fileOpenRequested = pyqtSignal(str)

    def event(self, ev) -> bool:
        if ev.type() == QEvent.Type.FileOpen:
            try:
                self.fileOpenRequested.emit(ev.file())
            except Exception:
                pass
            return True
        return super().event(ev)


def main() -> None:
    app = _CalcApplication(sys.argv)
    app.setApplicationName('CalcMacApp')
    app.setOrganizationName('CalcMacApp')

    # macOS: toolbar samenvoegen met titelbar (unified look)
    if sys.platform == 'darwin':
        app.setAttribute(
            Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True
        )

    win = MainWindow()
    if sys.platform == 'darwin':
        win.setUnifiedTitleAndToolBarOnMac(True)
    win.show()

    # Open een bestand uit sys.argv[1] (bv. via 'open foo.c4y' of CalcMacApp.app)
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1])
        if candidate.exists():
            win.load_path(str(candidate))

    # Daarna ook nog binnenkomende FileOpen-events afhandelen
    app.fileOpenRequested.connect(win.load_path)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
