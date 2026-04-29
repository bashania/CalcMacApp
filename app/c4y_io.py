"""Lezen en schrijven van Calc4You .c4y bestanden.

Het .c4y formaat is UTF-8 XML met root <calc4you>, een <alginfo> kop,
meerdere <begroting> blokken en sluit-secties <versie>, <toelichting>, <offerte>.

Getalvelden gebruiken Nederlandse notatie (komma als decimaalscheider,
punt als duizendtalscheider).
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


# ── XML-opschoning ────────────────────────────────────────────────────────────
# XML 1.0 staat alleen toe: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD]
# Calc4You-bestanden kunnen soms ongeldige tekenverwij­zingen bevatten
# (bv. &#x0; &#x1B;) doordat tekst vanuit Word of RTF is gekopieerd.

_CHAR_REF = re.compile(r'&#(?:x([0-9a-fA-F]+)|([0-9]+));')
_INVALID_RAW = re.compile(
    r'[^\x09\x0A\x0D\x20-퟿-�\U00010000-\U0010FFFF]'
)


def _valid_xml_codepoint(code: int) -> bool:
    return (
        code in (0x9, 0xA, 0xD)
        or 0x20 <= code <= 0xD7FF
        or 0xE000 <= code <= 0xFFFD
        or 0x10000 <= code <= 0x10FFFF
    )


def _clean_xml(text: str) -> str:
    """Verwijder ongeldig tekens en ongeldi­ge tekenverwij­zingen uit XML."""
    def _fix_ref(m: re.Match) -> str:
        code = int(m.group(1), 16) if m.group(1) else int(m.group(2))
        return m.group(0) if _valid_xml_codepoint(code) else ''

    text = _CHAR_REF.sub(_fix_ref, text)
    text = _INVALID_RAW.sub('', text)
    return text


# ── Getalconversie NL ↔ float ─────────────────────────────────────────────────
def parse_nl_number(value: Optional[str]) -> Optional[float]:
    """'1.234,56' → 1234.56. Lege string → None.

    Tolerant voor `%`-teken (bv. '21%' of '21 %' uit een BTW-rij) en
    omringende whitespace. Niet-numerieke input geeft None.
    """
    if value is None:
        return None
    s = str(value).strip().rstrip('%').strip()
    if not s:
        return None
    cleaned = s.replace('.', '').replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return None


def format_nl(value, dec: int = 2) -> str:
    """Float → '1.234,56'. None of '' → ''."""
    if value is None or value == '':
        return ''
    v = float(value)
    if v == 0 and dec > 0:
        return '0,' + '0' * dec
    sign = '-' if v < 0 else ''
    v = abs(v)
    int_deel = int(v)
    dec_deel = v - int_deel
    int_str = f"{int_deel:,}".replace(',', '.')
    if dec > 0:
        dec_str = f"{round(dec_deel, dec):.{dec}f}"[2:]
        return f"{sign}{int_str},{dec_str}"
    return f"{sign}{int_str}"


def format_nl_hvh(value) -> str:
    """Hoeveelheid: geen decimalen voor gehele getallen."""
    if value is None or value == '':
        return ''
    v = round(float(value), 2)
    if v == int(v):
        return format_nl(int(v), 0)
    return format_nl(v, 2)


# ── Begroting-element layout ──────────────────────────────────────────────────
# Volgorde van sub-tags in een <begroting>. Identiek aan
# c4y-writer/scripts/schrijf_c4y.py:96-140 zodat door onze app aangemaakte
# bestanden compatibel blijven met de originele Calc4You-software.
BEGROTING_TAG_ORDER: tuple[str, ...] = (
    'nr', 'code', 's', 'oms', 'hvh', 'enh',
    'arb', 'maa', 'mee', 'ond',
    'totaal', 'toturen', 'prijspe',
    'bestekc',
    'admi', 'admi_ar', 'admi_ma', 'admi_me', 'admi_oa',
    'meet', 'totarbeid', 'totuur',
    'code1', 'code2', 'code3', 'code4',
    'uurloon', 'mnr', 'btw', 'rsu', 'aard',
    'productie', 'ouder', 'althv',
    'startjr', 'cyclus', 'stopjr', 'prioriteit',
    'dccode', 'dcbedrag', 'link',
)

# Vaste defaults die Calc4You ook altijd schrijft.
BEGROTING_FIXED_DEFAULTS: dict[str, str] = {
    'admi_oa': '0',
}

TITEL_NIVEAUS: frozenset[str] = frozenset({'1', '2', '3'})


# ── Document ──────────────────────────────────────────────────────────────────
class C4YDocument:
    """Een geladen .c4y bestand met directe edit-toegang tot de XML-tree."""

    PROJECT_FIELDS = ('kop', 'r1', 'r2', 'r3', 'r4', 'r5', 'ul')
    ROW_FIELDS = BEGROTING_TAG_ORDER

    def __init__(self, tree: ET.ElementTree, path: Optional[str] = None):
        self.tree = tree
        self.path: Optional[str] = path

    # ── Laden ────────────────────────────────────────────────────────────────
    @classmethod
    def load(cls, path: str | Path) -> "C4YDocument":
        raw = Path(path).read_bytes()
        # Probeer UTF-8; val terug op latin-1 (Windows-bestanden)
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
        text = _clean_xml(text)
        root = ET.fromstring(text)
        return cls(ET.ElementTree(root), str(path))

    # ── Eigenschappen ────────────────────────────────────────────────────────
    @property
    def root(self) -> ET.Element:
        return self.tree.getroot()

    @property
    def alginfo(self) -> Optional[ET.Element]:
        return self.root.find('alginfo')

    @property
    def begrotingen(self) -> list[ET.Element]:
        return self.root.findall('begroting')

    # ── Project (alginfo) ────────────────────────────────────────────────────
    def get_project_field(self, tag: str) -> str:
        el = self.alginfo
        if el is None:
            return ''
        child = el.find(tag)
        return (child.text or '') if child is not None else ''

    def set_project_field(self, tag: str, value: str) -> None:
        el = self.alginfo
        if el is None:
            return
        child = el.find(tag)
        if child is None:
            child = ET.SubElement(el, tag)
        child.text = value if value else None

    # ── Begroting-regels ─────────────────────────────────────────────────────
    def row_count(self) -> int:
        return len(self.begrotingen)

    def get_row_field(self, idx: int, tag: str) -> str:
        b = self.begrotingen[idx]
        child = b.find(tag)
        return (child.text or '') if child is not None else ''

    def set_row_field(self, idx: int, tag: str, value: str) -> None:
        b = self.begrotingen[idx]
        child = b.find(tag)
        if child is None:
            child = ET.SubElement(b, tag)
        child.text = value if value else None

    # ── Structurele mutaties ─────────────────────────────────────────────────
    def _root_index_of(self, element: ET.Element) -> int:
        """Geef de positie van `element` binnen self.root."""
        for i, child in enumerate(self.root):
            if child is element:
                return i
        raise ValueError("element niet gevonden in root")

    def _root_anchor_for(self, idx: int) -> int:
        """Bepaal de root-positie waar een nieuwe begroting op begroting-index
        `idx` ingevoegd zou moeten worden.

        Als er nog geen begrotingen zijn, val terug op direct na <alginfo>.
        """
        n = self.row_count()
        if idx < n:
            return self._root_index_of(self.begrotingen[idx])
        if n > 0:
            return self._root_index_of(self.begrotingen[n - 1]) + 1
        # Geen bestaande begrotingen: na alginfo (positie 0 of 1)
        ai = self.alginfo
        return (self._root_index_of(ai) + 1) if ai is not None else 0

    def make_empty_begroting(
        self, defaults: Optional[dict[str, str]] = None
    ) -> ET.Element:
        """Maak een nieuw <begroting> met alle Calc4You sub-tags in volgorde.

        Velden zijn leeg tenzij in `defaults` of in BEGROTING_FIXED_DEFAULTS.
        """
        el = ET.Element('begroting')
        defaults = defaults or {}
        for tag in BEGROTING_TAG_ORDER:
            child = ET.SubElement(el, tag)
            value = defaults.get(tag, BEGROTING_FIXED_DEFAULTS.get(tag))
            if value:
                child.text = value
        return el

    def insert_row(
        self, idx: int, defaults: Optional[dict[str, str]] = None,
    ) -> ET.Element:
        """Voeg een nieuwe lege rij in op begroting-positie `idx`.

        Geeft het nieuw aangemaakte element terug. Roep `renumber()` aan
        nadat alle structurele mutaties klaar zijn.
        """
        n = self.row_count()
        if not 0 <= idx <= n:
            raise IndexError(f"insert_row idx={idx} buiten bereik 0..{n}")
        el = self.make_empty_begroting(defaults)
        self.root.insert(self._root_anchor_for(idx), el)
        return el

    def delete_row(self, idx: int) -> ET.Element:
        """Verwijder rij `idx` en geef het verwijderde element terug.

        Het teruggegeven element kan via `restore_row` weer ingevoegd worden
        (bv. voor undo).
        """
        el = self.begrotingen[idx]
        self.root.remove(el)
        return el

    def restore_row(self, idx: int, element: ET.Element) -> None:
        """Plaats een eerder verwijderd element terug op positie `idx`."""
        n = self.row_count()
        if not 0 <= idx <= n:
            raise IndexError(f"restore_row idx={idx} buiten bereik 0..{n}")
        self.root.insert(self._root_anchor_for(idx), element)

    def duplicate_row(self, idx: int) -> ET.Element:
        """Maak een diepe kopie van rij `idx` en plaats hem direct eronder."""
        src = self.begrotingen[idx]
        copy_el = copy.deepcopy(src)
        nr_el = copy_el.find('nr')
        if nr_el is not None:
            nr_el.text = None      # renumber vult dit later
        self.root.insert(self._root_index_of(src) + 1, copy_el)
        return copy_el

    def move_block(self, src: int, count: int, dst: int) -> None:
        """Verplaats `count` opeenvolgende rijen vanaf `src` naar `dst`.

        `dst` is de doelpositie *ná* verwijdering van het blok — dus geldt
        0 ≤ dst ≤ row_count() − count.
        """
        if count < 1 or src == dst:
            return
        n = self.row_count()
        if not (0 <= src < n and src + count <= n):
            raise IndexError(f"move_block src={src} count={count} buiten bereik")
        if not 0 <= dst <= n - count:
            raise IndexError(f"move_block dst={dst} buiten bereik")

        # Snapshot van de te verplaatsen elementen
        block = [self.begrotingen[src + i] for i in range(count)]
        for el in block:
            self.root.remove(el)

        # Bepaal anchor in root op basis van begroting-index na verwijdering
        anchor = self._root_anchor_for(dst)
        for i, el in enumerate(block):
            self.root.insert(anchor + i, el)

    def renumber(self) -> None:
        """Hernummert <nr> in document-volgorde (00001, 00002, …)."""
        for i, el in enumerate(self.begrotingen):
            nr_el = el.find('nr')
            if nr_el is None:
                # Maak in juiste positie aan (eerste sub-tag)
                nr_el = ET.Element('nr')
                el.insert(0, nr_el)
            nr_el.text = f"{i + 1:05d}"

    def block_size(self, idx: int) -> int:
        """Aantal rijen in het 'blok' beginnend bij `idx`.

        Voor titelrijen (S=1/2/3): titel + alle children tot de volgende
        titel van gelijk of hoger niveau (of '/' of einde).
        Voor alle andere rijen: 1.
        """
        rows = self.begrotingen
        n = len(rows)
        if not 0 <= idx < n:
            return 0
        s = (rows[idx].findtext('s') or '').strip()
        if s not in TITEL_NIVEAUS:
            return 1
        niveau = int(s)
        cnt = 1
        for j in range(idx + 1, n):
            s_j = (rows[j].findtext('s') or '').strip()
            if s_j == '/':
                break
            if s_j in TITEL_NIVEAUS and int(s_j) <= niveau:
                break
            cnt += 1
        return cnt

    def children_indices(self, idx: int) -> list[int]:
        """Indices van direct-onderliggende rijen voor titel `idx`."""
        cnt = self.block_size(idx)
        return list(range(idx + 1, idx + cnt)) if cnt > 1 else []

    # ── Opslaan ──────────────────────────────────────────────────────────────
    def save(self, path: Optional[str | Path] = None) -> None:
        target = str(path) if path else self.path
        if target is None:
            raise ValueError("Geen pad opgegeven om naar op te slaan.")

        xml_bytes = ET.tostring(self.root, encoding='utf-8')
        with open(target, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" standalone="yes"?>\n')
            f.write(xml_bytes.decode('utf-8'))

        self.path = target
