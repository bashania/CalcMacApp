"""Unit-tests voor app.validations."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.c4y_io import C4YDocument
from app.validations import validate, worst_severity


def _doc_from_rows(rows: list[dict]) -> C4YDocument:
    """Bouw een minimaal C4YDocument vanuit een lijst dicts."""
    root = ET.Element('calc4you')
    ET.SubElement(root, 'alginfo')
    for r in rows:
        b = ET.SubElement(root, 'begroting')
        for tag, val in r.items():
            ET.SubElement(b, tag).text = val
    return C4YDocument(ET.ElementTree(root))


def test_no_issues_on_valid_simple_doc():
    d = _doc_from_rows([
        {'s': '1', 'hvh': '1', 'oms': 'Hoofd'},
        {'s': '',  'hvh': '5', 'oms': 'Werk', 'arb': '0,1', 'maa': '2'},
    ])
    issues = validate(d)
    # mag info-meldingen hebben maar geen errors of warnings
    severities = [i.severity for i in issues]
    assert 'error' not in severities
    assert 'warning' not in severities


def test_warning_titel_negatieve_hvh():
    d = _doc_from_rows([
        {'s': '1', 'hvh': '-1', 'oms': 'Slecht'},
    ])
    issues = validate(d)
    assert any(i.severity == 'error' for i in issues)


def test_warning_regel_zonder_hvh():
    d = _doc_from_rows([
        {'s': '1', 'hvh': '1'},
        {'s': '',  'hvh': '0', 'arb': '0,1'},
    ])
    issues = validate(d)
    assert any('hoeveelheid' in i.message.lower() for i in issues)


def test_warning_regel_zonder_prijs():
    d = _doc_from_rows([
        {'s': '1', 'hvh': '1'},
        {'s': '',  'hvh': '5', 'oms': 'Iets'},
    ])
    issues = validate(d)
    assert any('prijs' in i.message.lower() for i in issues)


def test_info_kophoeveelheid_groter_dan_1():
    d = _doc_from_rows([
        {'s': '1', 'hvh': '2', 'oms': 'Twee gevels'},
        {'s': '',  'hvh': '5', 'arb': '0,1', 'maa': '1'},
    ])
    issues = validate(d)
    assert any(
        i.severity == 'info' and 'kophoeveelheid' in i.message.lower()
        for i in issues
    )


def test_warning_staart_zonder_eq():
    d = _doc_from_rows([
        {'s': '1', 'hvh': '1'},
        {'s': '',  'hvh': '5', 'arb': '0,1', 'maa': '1'},
        {'s': '/'},
        {'s': '%', 'hvh': '5'},
    ])
    issues = validate(d)
    assert any(
        i.severity == 'warning' and '=' in i.message for i in issues
    )


def test_worst_severity_priority():
    from app.validations import Issue
    items = [
        Issue(0, 'info',    'i'),
        Issue(0, 'warning', 'w'),
        Issue(0, 'error',   'e'),
    ]
    assert worst_severity(items) == 'error'
