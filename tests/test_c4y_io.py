"""Unit-tests voor app.c4y_io — getalformaat en XML-mutaties."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.c4y_io import (
    BEGROTING_TAG_ORDER,
    C4YDocument,
    _clean_xml,
    format_nl,
    format_nl_hvh,
    parse_nl_number,
)


SAMPLE = Path(__file__).resolve().parent.parent / 'samples' / 'voorbeeld.c4y'


# ── parse_nl_number ───────────────────────────────────────────────────────────
@pytest.mark.parametrize('s, expected', [
    ('1.234,56', 1234.56),
    ('0,00',     0.0),
    ('-1.500,5', -1500.5),
    ('21%',      21.0),
    (' 21 % ',   21.0),
    ('',         None),
    (None,       None),
    ('abc',      None),
])
def test_parse_nl_number(s, expected):
    assert parse_nl_number(s) == expected


# ── format_nl ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('v, dec, expected', [
    (1234.56,    2, '1.234,56'),
    (0,          2, '0,00'),
    (0.0,        0, '0'),
    (-1500.5,    2, '-1.500,50'),
    (1234567.89, 2, '1.234.567,89'),
])
def test_format_nl(v, dec, expected):
    assert format_nl(v, dec) == expected


def test_format_nl_hvh_whole():
    assert format_nl_hvh(576) == '576'


def test_format_nl_hvh_fractional():
    assert format_nl_hvh(130.4) == '130,40'


# ── _clean_xml ────────────────────────────────────────────────────────────────
def test_clean_xml_removes_invalid_refs():
    text = 'foo &#x0; bar &#x1B; baz &#x9; tab'
    cleaned = _clean_xml(text)
    assert '&#x0;' not in cleaned
    assert '&#x1B;' not in cleaned
    assert '&#x9;' in cleaned
    assert 'foo' in cleaned and 'bar' in cleaned


# ── C4YDocument: load + structural mutations ──────────────────────────────────
@pytest.mark.skipif(not SAMPLE.exists(), reason='sample.c4y ontbreekt')
def test_load_sample():
    d = C4YDocument.load(SAMPLE)
    assert d.row_count() == 6
    assert d.get_row_field(0, 's') == '1'


@pytest.mark.skipif(not SAMPLE.exists(), reason='sample.c4y ontbreekt')
def test_insert_row_keeps_tag_order():
    d = C4YDocument.load(SAMPLE)
    orig_tags = [c.tag for c in d.begrotingen[2]]
    d.insert_row(3)
    d.renumber()
    new_tags = [c.tag for c in d.begrotingen[3]]
    assert orig_tags == new_tags


@pytest.mark.skipif(not SAMPLE.exists(), reason='sample.c4y ontbreekt')
def test_renumber_increments():
    d = C4YDocument.load(SAMPLE)
    d.insert_row(0)
    d.renumber()
    assert d.get_row_field(0, 'nr') == '00001'
    assert d.get_row_field(d.row_count() - 1, 'nr') == \
        f'{d.row_count():05d}'


@pytest.mark.skipif(not SAMPLE.exists(), reason='sample.c4y ontbreekt')
def test_move_block_titel_takes_children():
    d = C4YDocument.load(SAMPLE)
    src = 1                             # S=2 "Gevel Entree Zijde"
    count = d.block_size(src)            # 4 — titel + 2 kindrijen + 1 ?
    assert count >= 2
    target = d.row_count() - count       # einde
    d.move_block(src, count, target)
    d.renumber()
    # Eerste S=2 staat nu op een andere positie
    assert d.get_row_field(target, 's') == '2'


def test_begroting_tag_order_complete():
    """Verify all expected Calc4You tags zijn in BEGROTING_TAG_ORDER."""
    must_have = {
        'nr', 'code', 's', 'oms', 'hvh', 'enh',
        'arb', 'maa', 'mee', 'ond',
        'totaal', 'toturen', 'prijspe',
        'code1', 'code2', 'code3', 'code4',
        'uurloon', 'btw', 'productie', 'althv',
    }
    assert must_have.issubset(set(BEGROTING_TAG_ORDER))
