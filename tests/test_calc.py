"""Unit-tests voor app.calc — rij-, titel- en staartrekenen."""

from __future__ import annotations

import pytest

from app.c4y_io import parse_nl_number
from app.calc import (
    eindtotaal_begroting,
    recompute,
    totaal_begroting,
)


def make_row(s='', hvh='', arb='', maa='', mee='', ond='',
             uurloon='', productie=''):
    return {
        's': s, 'hvh': hvh, 'arb': arb, 'maa': maa, 'mee': mee,
        'ond': ond, 'uurloon': uurloon, 'productie': productie,
    }


# ── factor over hele regel ────────────────────────────────────────────────────
def test_factor_applies_to_whole_row():
    r = make_row(hvh='100', arb='0,1', maa='2', uurloon='45', productie='25')
    out = recompute([r])[0]
    # arb*uurloon + maa = 0,1*45 + 2 = 6,5; * 1,25 = 8,125; * 100 = 812,50
    assert parse_nl_number(out['totaal']) == pytest.approx(812.50, abs=0.01)


def test_per_kostensoort_totalen():
    r = make_row(hvh='10', arb='0,5', maa='3', mee='1', ond='2',
                 uurloon='40', productie='25')
    out = recompute([r])[0]
    # arb tot = 10*0,5*40*1,25 = 250
    # maa tot = 10*3*1,25 = 37,5
    # mee tot = 10*1*1,25 = 12,5
    # ond tot = 10*2*1,25 = 25
    assert parse_nl_number(out['tot_arb']) == pytest.approx(250, abs=0.01)
    assert parse_nl_number(out['tot_maa']) == pytest.approx(37.5, abs=0.01)
    assert parse_nl_number(out['tot_mee']) == pytest.approx(12.5, abs=0.01)
    assert parse_nl_number(out['tot_ond']) == pytest.approx(25, abs=0.01)


# ── titel-rollup ──────────────────────────────────────────────────────────────
def test_titel_rollup_simple():
    rows = [
        make_row(s='1', hvh='1'),
        make_row(s='2', hvh='1'),
        make_row(hvh='10', arb='0,1', uurloon='40', productie='25'),
        make_row(hvh='5',  arb='0,2', uurloon='40', productie='25'),
    ]
    out = recompute(rows)
    # leaf 1: 10 * 0,1 * 40 * 1,25 = 50
    # leaf 2: 5  * 0,2 * 40 * 1,25 = 50
    # S=2: 100
    # S=1: 100
    assert parse_nl_number(out[1]['totaal']) == pytest.approx(100, abs=0.01)
    assert parse_nl_number(out[0]['totaal']) == pytest.approx(100, abs=0.01)


def test_kophoeveelheid_multiplies_children():
    """Titel met hvh=2 dubbelt onderliggende totalen."""
    rows = [
        make_row(s='1', hvh='2'),
        make_row(s='2', hvh='1'),
        make_row(hvh='10', arb='0,1', uurloon='40', productie='25'),
    ]
    out = recompute(rows)
    # leaf: 10 * 0,1 * 40 * 1,25 = 50
    # S=2: 50
    # S=1: 50 * 2 = 100
    assert parse_nl_number(out[2]['totaal']) == pytest.approx(50,  abs=0.01)
    assert parse_nl_number(out[1]['totaal']) == pytest.approx(50,  abs=0.01)
    assert parse_nl_number(out[0]['totaal']) == pytest.approx(100, abs=0.01)


def test_kophoeveelheid_nested():
    """Geneste hvh's vermenigvuldigen elkaar."""
    rows = [
        make_row(s='1', hvh='2'),
        make_row(s='2', hvh='3'),
        make_row(hvh='10', arb='0,1', uurloon='40', productie='25'),
    ]
    out = recompute(rows)
    # leaf: 50; S=2: 50*3=150; S=1: 150*2=300
    assert parse_nl_number(out[1]['totaal']) == pytest.approx(150, abs=0.01)
    assert parse_nl_number(out[0]['totaal']) == pytest.approx(300, abs=0.01)


# ── staart ────────────────────────────────────────────────────────────────────
def test_staart_btw_hoog():
    rows = [
        make_row(s='1', hvh='1'),
        make_row(hvh='100', maa='1', productie='0'),  # 100 directe kosten
        make_row(s='/'),
        make_row(s='a', hvh='21'),
        make_row(s='='),
    ]
    out = recompute(rows)
    # / = 100
    # a = 100 * 0,21 = 21
    # = = 121
    assert parse_nl_number(out[3]['totaal']) == pytest.approx(21,  abs=0.01)
    assert parse_nl_number(out[4]['totaal']) == pytest.approx(121, abs=0.01)


def test_staart_x_post_optelt():
    rows = [
        make_row(s='1', hvh='1'),
        make_row(s='X', hvh='1', ond='100'),
        make_row(s='/'),
        make_row(s='X'),
        make_row(s='='),
    ]
    out = recompute(rows)
    # X-post in directe kosten: 100; / = 0 (X niet in directe kosten);
    # X in staart telt 100 op; = 100
    assert parse_nl_number(out[4]['totaal']) == pytest.approx(100, abs=0.01)


def test_eindtotaal_helper():
    rows = [
        make_row(s='1', hvh='1'),
        make_row(hvh='100', maa='1', productie='0'),
        make_row(s='/'),
        make_row(s='='),
    ]
    out = recompute(rows)
    assert eindtotaal_begroting(out, rows) == pytest.approx(100, abs=0.01)


def test_no_staart_eindtotaal_is_none():
    rows = [
        make_row(s='1', hvh='1'),
        make_row(hvh='1', maa='1', productie='0'),
    ]
    out = recompute(rows)
    assert eindtotaal_begroting(out, rows) is None


def test_totaal_begroting_telt_alleen_s1():
    rows = [
        make_row(s='1', hvh='1'),
        make_row(s='2', hvh='1'),
        make_row(hvh='1', maa='10', productie='0'),
        make_row(s='1', hvh='1'),
        make_row(hvh='1', maa='5',  productie='0'),
    ]
    out = recompute(rows)
    # S=1 #1: 10; S=1 #2: 5; samen 15
    assert totaal_begroting(out, rows) == pytest.approx(15, abs=0.01)
