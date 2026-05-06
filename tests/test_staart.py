"""Tests voor de staart-rekenfunctionaliteit en validatie.

Pure-Python tests — geen Qt-afhankelijkheid. Draaibaar met `pytest tests/`
vanuit de repo-root.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Zorg dat `app` als top-level package vindbaar is, ongeacht vanwaar
# pytest gestart wordt.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.c4y_io import parse_nl_number  # noqa: E402
from app.calc import (  # noqa: E402
    eindtotaal_begroting,
    recompute,
    validate_staart,
)


def make_row(**kwargs) -> dict:
    base = {k: '' for k in (
        's', 'hvh', 'arb', 'maa', 'mee', 'ond', 'uurloon', 'productie',
    )}
    base.update(kwargs)
    return base


# ── Reken-cases ───────────────────────────────────────────────────────────────
def test_staart_basis_pct_btw():
    rows = [
        make_row(maa='100', hvh='1'),    # directe kosten = 100
        make_row(s='/', hvh=''),
        make_row(s='%', hvh='5'),         # +5
        make_row(s='='),                  # 105
        make_row(s='a', hvh='21'),        # +22.05
        make_row(s='='),                  # 127.05
    ]
    res = recompute(rows)
    assert eindtotaal_begroting(res, rows) == pytest.approx(127.05)


def test_btw_default_geen_hvh():
    rows = [
        make_row(maa='100', hvh='1'),
        make_row(s='/'),
        make_row(s='a'),                  # leeg → 21% default
        make_row(s='='),
    ]
    res = recompute(rows)
    assert eindtotaal_begroting(res, rows) == pytest.approx(121.0)
    # Warning moet gerapporteerd zijn op de a-rij (index 2)
    assert any('Default 21%' in w for w in res[2]['warnings'])


def test_x_post_telt_in_staart():
    rows = [
        make_row(maa='100', hvh='1'),       # DK = 100
        make_row(s='X', maa='50', hvh='1'),  # X-post: 50, BUITEN DK
        make_row(s='/'),
        make_row(s='='),                     # = 100 (alleen DK)
        make_row(s='X'),                     # +50
        make_row(s='='),                     # = 150
    ]
    res = recompute(rows)
    assert parse_nl_number(res[3]['totaal']) == pytest.approx(100.0)
    assert parse_nl_number(res[5]['totaal']) == pytest.approx(150.0)


def test_svg_alleen_tonen():
    rows = [
        make_row(s='S', maa='200', hvh='1'),  # stelpost in DK
        make_row(s='/'),
        make_row(s='='),                       # = 200
        make_row(s='S'),                       # toont 200 maar telt niet bij running
        make_row(s='='),                       # nog steeds 200
    ]
    res = recompute(rows)
    assert parse_nl_number(res[2]['totaal']) == pytest.approx(200.0)
    assert parse_nl_number(res[4]['totaal']) == pytest.approx(200.0)


def test_pct_zero_warning():
    rows = [
        make_row(maa='100', hvh='1'),
        make_row(s='/'),
        make_row(s='%', hvh='0'),
        make_row(s='='),
    ]
    res = recompute(rows)
    assert any('Percentage 0' in w for w in res[2]['warnings'])


def test_minus_rij():
    rows = [
        make_row(maa='100', hvh='1'),
        make_row(s='/'),
        make_row(s='-', hvh='10'),
        make_row(s='='),
    ]
    res = recompute(rows)
    assert eindtotaal_begroting(res, rows) == pytest.approx(90.0)


def test_eindtotaal_na_btw_niet_laatste_eq():
    """Calc4You-conventie: een = na BTW + dan S/V/G + extra =. Eindtotaal
    moet de waarde direct na BTW oppikken (de laatste = is hier identiek
    omdat S/V/G running niet verandert, dus we testen ook de keuze)."""
    rows = [
        make_row(maa='100', hvh='1'),
        make_row(s='/'),
        make_row(s='a', hvh='21'),
        make_row(s='='),                  # 121 (na BTW)
        make_row(s='S'),                   # toont 0
        make_row(s='='),                   # 121 herhaald
    ]
    res = recompute(rows)
    assert eindtotaal_begroting(res, rows) == pytest.approx(121.0)


def test_eindtotaal_zonder_btw_valt_terug_op_laatste_eq():
    rows = [
        make_row(maa='100', hvh='1'),
        make_row(s='/'),
        make_row(s='%', hvh='10'),
        make_row(s='='),                  # 110, eindtotaal
    ]
    res = recompute(rows)
    assert eindtotaal_begroting(res, rows) == pytest.approx(110.0)


def test_eindtotaal_geen_staart():
    rows = [make_row(maa='100', hvh='1')]
    res = recompute(rows)
    assert eindtotaal_begroting(res, rows) is None


# ── Validate-cases ────────────────────────────────────────────────────────────
def test_validate_geen_slash_met_staart_codes():
    rows = [make_row(s='%', hvh='5')]
    issues = validate_staart(rows)
    assert any(i.code == 'orphan_staart' for i in issues)


def test_validate_geen_staart_geen_issues():
    rows = [make_row(maa='100', hvh='1')]
    assert validate_staart(rows) == []


def test_validate_btw_default_warning():
    rows = [make_row(s='/'), make_row(s='a'), make_row(s='=')]
    issues = validate_staart(rows)
    assert any(i.code == 'btw_default' for i in issues)


def test_validate_pct_zero_warning():
    rows = [make_row(s='/'), make_row(s='%', hvh='0'), make_row(s='=')]
    issues = validate_staart(rows)
    assert any(i.code == 'pct_zero' for i in issues)


def test_validate_geen_eindtotaal():
    rows = [make_row(s='/'), make_row(s='%', hvh='5')]
    issues = validate_staart(rows)
    assert any(i.code == 'no_total' for i in issues)


def test_validate_dubbele_slash():
    rows = [make_row(s='/'), make_row(s='%', hvh='5'), make_row(s='/')]
    issues = validate_staart(rows)
    assert any(i.code == 'duplicate_slash' for i in issues)


def test_validate_x_in_staart_zonder_bron():
    rows = [
        make_row(maa='100', hvh='1'),
        make_row(s='/'),
        make_row(s='X'),
        make_row(s='='),
    ]
    issues = validate_staart(rows)
    assert any(i.code == 'x_in_staart_no_source' for i in issues)


# ── parse_nl_number ───────────────────────────────────────────────────────────
def test_parse_nl_number_pct_input():
    assert parse_nl_number('21%') == 21.0
    assert parse_nl_number('21 %') == 21.0
    assert parse_nl_number('5,5%') == 5.5
    assert parse_nl_number('1.234,56') == pytest.approx(1234.56)
    assert parse_nl_number('') is None


# ── End-to-end op echte sample bestanden ──────────────────────────────────────
def _load_rows(path: Path) -> list[dict]:
    from app.c4y_io import C4YDocument
    doc = C4YDocument.load(str(path))
    fields = ('s', 'hvh', 'arb', 'maa', 'mee', 'ond', 'uurloon', 'productie')
    return [
        {t: doc.get_row_field(i, t) for t in fields}
        for i in range(doc.row_count())
    ]


def test_sample_kostprijsbegroting_eindtotaal():
    """End-to-end op een echt Calc4You-bestand met volledige staart.

    De staart eindigt op:
      idx 62  a  21%   (BTW hoog)
      idx 63  b   9%   (BTW laag)
      idx 64  =        ← echte eindtotaal (laatste = na BTW)
      idx 65  S
      idx 66  V
      idx 67  G
      idx 68  =        ← herhaling, MOET NIET gekozen worden (na S/V/G)

    We asserteren dat eindtotaal_begroting de waarde van idx 64 oppikt, niet
    idx 68 — dat is de hele bedoeling van de "laatste = na BTW"-heuristiek.
    De exacte numerieke waarde wordt NIET vergeleken met Calc4You's
    opgeslagen totaal omdat de directe-kosten-berekening tussen CalcMacApp
    en Calc4You licht verschilt (bekende, al bestaande discrepantie buiten
    scope van deze test).
    """
    p = ROOT / 'ondersteunend' / '20267.00322 - Kostbprijs begroting.c4y'
    if not p.exists():
        pytest.skip(f'Sample bestand niet gevonden: {p}')
    rows = _load_rows(p)
    res = recompute(rows)
    et = eindtotaal_begroting(res, rows)
    assert et is not None
    # Vind index 64 (eerste = na BTW-rijen) en bevestig dat eindtotaal die rij oppikt
    btw_idxs = [i for i, r in enumerate(rows)
                if (r.get('s') or '').strip() in ('a', 'b', 'c')]
    assert btw_idxs, 'verwacht ten minste één BTW-rij in sample'
    eq_after_btw = next(
        i for i in range(max(btw_idxs) + 1, len(rows))
        if (rows[i].get('s') or '').strip() == '='
    )
    assert et == pytest.approx(parse_nl_number(res[eq_after_btw]['totaal']))
    # De LAATSTE = is een andere index dan onze keuze (S/V/G + extra =)
    last_eq = max(
        i for i, r in enumerate(rows)
        if (r.get('s') or '').strip() == '='
    )
    assert last_eq != eq_after_btw, (
        'Sample mist de extra =-rij na S/V/G; test-aanname klopt niet meer'
    )


def test_sample_voorbeeld_geen_staart():
    p = ROOT / 'samples' / 'voorbeeld.c4y'
    if not p.exists():
        pytest.skip(f'Sample bestand niet gevonden: {p}')
    rows = _load_rows(p)
    res = recompute(rows)
    assert eindtotaal_begroting(res, rows) is None
