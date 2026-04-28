"""QUndoCommand subclasses voor de begrotingstabel.

Elke commando capt zijn eigen voor- en na-staat zodat undo/redo
deterministisch werkt zonder dat MainWindow staat hoeft te onthouden.

Alle commando's roepen `host.refresh()` aan na een wijziging — die hook is
de centrale plek waar MainWindow de tabel herrendert, herrekent en
zichtbaarheid van rijen herevalueert.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional, Protocol

from PyQt6.QtGui import QUndoCommand

from app.c4y_io import C4YDocument


class _Host(Protocol):
    """Minimale interface die MainWindow aan commando's aanbiedt."""

    doc: Optional[C4YDocument]

    def refresh(self) -> None: ...
    def select_row(self, idx: int) -> None: ...


# ── Cel-edit ──────────────────────────────────────────────────────────────────
class SetCellCommand(QUndoCommand):
    """Wijzig één veld op één rij."""

    def __init__(
        self, host: _Host, row_idx: int, tag: str, old: str, new: str,
    ) -> None:
        super().__init__(f"{tag} → {new[:30]}")
        self.host = host
        self.row_idx = row_idx
        self.tag = tag
        self.old = old
        self.new = new

    def redo(self) -> None:
        if self.host.doc is None:
            return
        self.host.doc.set_row_field(self.row_idx, self.tag, self.new)
        self.host.refresh()

    def undo(self) -> None:
        if self.host.doc is None:
            return
        self.host.doc.set_row_field(self.row_idx, self.tag, self.old)
        self.host.refresh()


# ── Rij invoegen ──────────────────────────────────────────────────────────────
class InsertRowCommand(QUndoCommand):
    """Voeg een lege rij in op `idx`."""

    def __init__(
        self, host: _Host, idx: int,
        defaults: Optional[dict[str, str]] = None,
        text: str = 'Rij toevoegen',
    ) -> None:
        super().__init__(text)
        self.host = host
        self.idx = idx
        self.defaults = defaults
        self._element: Optional[ET.Element] = None

    def redo(self) -> None:
        if self.host.doc is None:
            return
        if self._element is None:
            self._element = self.host.doc.insert_row(self.idx, self.defaults)
        else:
            self.host.doc.restore_row(self.idx, self._element)
        self.host.doc.renumber()
        self.host.refresh()
        self.host.select_row(self.idx)

    def undo(self) -> None:
        if self.host.doc is None:
            return
        self._element = self.host.doc.delete_row(self.idx)
        self.host.doc.renumber()
        self.host.refresh()


# ── Rij verwijderen ───────────────────────────────────────────────────────────
class DeleteRowCommand(QUndoCommand):
    """Verwijder een rij; undo plaatst hem precies terug."""

    def __init__(self, host: _Host, idx: int) -> None:
        super().__init__('Rij verwijderen')
        self.host = host
        self.idx = idx
        self._element: Optional[ET.Element] = None

    def redo(self) -> None:
        if self.host.doc is None:
            return
        self._element = self.host.doc.delete_row(self.idx)
        self.host.doc.renumber()
        self.host.refresh()

    def undo(self) -> None:
        if self.host.doc is None or self._element is None:
            return
        self.host.doc.restore_row(self.idx, self._element)
        self.host.doc.renumber()
        self.host.refresh()
        self.host.select_row(self.idx)


# ── Rij dupliceren ────────────────────────────────────────────────────────────
class DuplicateRowCommand(QUndoCommand):
    """Plaats een diepe kopie van rij `src` direct eronder."""

    def __init__(self, host: _Host, src: int) -> None:
        super().__init__('Rij kopiëren')
        self.host = host
        self.src = src
        self._element: Optional[ET.Element] = None

    def redo(self) -> None:
        if self.host.doc is None:
            return
        if self._element is None:
            self._element = self.host.doc.duplicate_row(self.src)
        else:
            # Re-redo na undo: plaats hetzelfde element op src+1
            self.host.doc.restore_row(self.src + 1, self._element)
        self.host.doc.renumber()
        self.host.refresh()
        self.host.select_row(self.src + 1)

    def undo(self) -> None:
        if self.host.doc is None:
            return
        self._element = self.host.doc.delete_row(self.src + 1)
        self.host.doc.renumber()
        self.host.refresh()
        self.host.select_row(self.src)


# ── Blok verplaatsen (drag & drop) ────────────────────────────────────────────
class MoveBlockCommand(QUndoCommand):
    """Verplaats `count` opeenvolgende rijen vanaf `src` naar `dst`.

    `dst` is de doelpositie ná verwijdering van het blok (zoals
    `C4YDocument.move_block` verwacht).
    """

    def __init__(
        self, host: _Host, src: int, count: int, dst: int,
    ) -> None:
        if count == 1:
            super().__init__('Rij verplaatsen')
        else:
            super().__init__(f'Blok verplaatsen ({count} rijen)')
        self.host = host
        self.src = src
        self.count = count
        self.dst = dst

    def redo(self) -> None:
        if self.host.doc is None:
            return
        self.host.doc.move_block(self.src, self.count, self.dst)
        self.host.doc.renumber()
        self.host.refresh()
        self.host.select_row(self.dst)

    def undo(self) -> None:
        if self.host.doc is None:
            return
        # Inverse: het blok zit nu op `dst` en moet terug naar `src`.
        self.host.doc.move_block(self.dst, self.count, self.src)
        self.host.doc.renumber()
        self.host.refresh()
        self.host.select_row(self.src)
