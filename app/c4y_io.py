"""Lezen en schrijven van Calc4You .c4y bestanden.

Het .c4y formaat is UTF-8 XML met root <calc4you>, een <alginfo> kop,
meerdere <begroting> blokken en sluit-secties <versie>, <toelichting>, <offerte>.

Getalvelden gebruiken Nederlandse notatie (komma als decimaalscheider,
punt als duizendtalscheider).
"""

from __future__ import annotations

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
    """'1.234,56' → 1234.56. Lege string → None."""
    if value is None:
        return None
    s = str(value).strip()
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


# ── Document ──────────────────────────────────────────────────────────────────
class C4YDocument:
    """Een geladen .c4y bestand met directe edit-toegang tot de XML-tree."""

    PROJECT_FIELDS = ('kop', 'r1', 'r2', 'r3', 'r4', 'r5', 'ul')
    ROW_FIELDS = (
        'nr', 'code', 's', 'oms', 'hvh', 'enh',
        'arb', 'maa', 'ond',
        'code1', 'code2', 'code3', 'code4',
        'uurloon', 'productie',
    )

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
