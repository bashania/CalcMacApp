"""Rekenmodule voor de begrotingstabel.

Fase 1 — begrotingsregels: prijspe, toturen, regeltotaal.
Fase 2 — titel-rollup: S=1/2/3 koppen sommeren onderliggende regels.
Fase 3 — staart: `/`-rij detecteert het begin, daarna `%`, `+`, `-`,
          `=`, `a`, `b`, `c`, `&`, `S`, `G`, `V`, `X`.

Berekende velden worden NIET in het .c4y bestand geschreven — Calc4You
vult die zelf in bij het openen. Deze module dient uitsluitend de viewer-UI.
"""

from __future__ import annotations

from typing import Iterable

from app.c4y_io import format_nl, format_nl_hvh, parse_nl_number


# ── S-code classificatie ──────────────────────────────────────────────────────
TITEL_NIVEAUS      = frozenset({'1', '2', '3'})
BEGROTING_S_CODES  = frozenset({'', 'S', 'V', 'G', '?', 'X'})
STAART_S_CODES     = frozenset({'/', '%', '&', '=', '+', '-', 'a', 'b', 'c'})

# Standaard BTW-percentages als hvh leeg is
BTW_DEFAULTS: dict[str, float] = {'a': 21.0, 'b': 9.0, 'c': 0.0}


def _num(value) -> float:
    parsed = parse_nl_number(value)
    return parsed if parsed is not None else 0.0


def _bereken_regel(row: dict) -> tuple[float, float, float]:
    """(prijspe, toturen, totaal) voor een gewone begrotingsregel."""
    arb       = _num(row.get('arb'))
    maa       = _num(row.get('maa'))
    mee       = _num(row.get('mee'))
    ond       = _num(row.get('ond'))
    hvh       = _num(row.get('hvh'))
    uurloon   = _num(row.get('uurloon'))
    productie = _num(row.get('productie'))

    prijspe = arb * uurloon * (1.0 + productie / 100.0) + maa + mee + ond
    return prijspe, hvh * arb, hvh * prijspe


def recompute(rows: Iterable[dict]) -> list[dict]:
    """Bereken per rij (prijspe, toturen, totaal, is_staart).

    Argumenten
    ----------
    rows : iterabel van dicts met keys
        s, hvh, arb, maa, mee, ond, uurloon, productie
        Waarden zijn strings in Nederlands getalformaat of leeg.

    Resultaat
    ---------
    list van dicts met:
        prijspe  : str  (leeg voor titels en staart)
        toturen  : str  (leeg voor titels bij 0 uren, leeg voor staart)
        totaal   : str
        is_staart: bool (True voor rijen op of na de '/')
    """
    rows = list(rows)
    n = len(rows)
    raw_totaal  = [0.0] * n
    raw_toturen = [0.0] * n
    raw_prijspe = [0.0] * n
    is_titel    = [False] * n
    is_staart   = [False] * n

    # Zoek de staartscheiding ('/')
    staart_idx: int | None = None
    for i, r in enumerate(rows):
        if (r.get('s') or '').strip() == '/':
            staart_idx = i
            break

    # ── Fase 1: begrotingsregels ──────────────────────────────────────────────
    for i, r in enumerate(rows):
        s = (r.get('s') or '').strip()
        if staart_idx is not None and i >= staart_idx:
            is_staart[i] = True
            continue
        if s in TITEL_NIVEAUS:
            is_titel[i] = True
        elif s in BEGROTING_S_CODES:
            p, t, tot = _bereken_regel(r)
            raw_prijspe[i], raw_toturen[i], raw_totaal[i] = p, t, tot

    # ── Fase 2: titel-rollup (S=1/2/3) ───────────────────────────────────────
    for i in range(n):
        if not is_titel[i]:
            continue
        niveau = int((rows[i].get('s') or '').strip())
        som_tot = som_uren = 0.0
        for j in range(i + 1, n):
            if is_staart[j]:
                break
            s_j = (rows[j].get('s') or '').strip()
            if s_j in TITEL_NIVEAUS and int(s_j) <= niveau:
                break
            som_tot  += raw_totaal[j]
            som_uren += raw_toturen[j]
        raw_totaal[i]  = som_tot
        raw_toturen[i] = som_uren

    # ── Fase 3: staart ────────────────────────────────────────────────────────
    if staart_idx is not None:
        # Directe kosten: som van begrotingsregels, X-posten NIET meegeteld.
        directe_kosten = sum(
            raw_totaal[i] for i in range(staart_idx)
            if not is_titel[i] and (rows[i].get('s') or '').strip() != 'X'
        )
        # Subtotalen per post-type voor gebruik in staart
        _sub = {
            code: sum(raw_totaal[i] for i in range(staart_idx)
                      if (rows[i].get('s') or '').strip() == code)
            for code in ('S', 'V', 'G', 'X')
        }

        running = directe_kosten
        raw_totaal[staart_idx] = directe_kosten  # '/' rij

        for i in range(staart_idx + 1, n):
            s   = (rows[i].get('s') or '').strip()
            hvh = _num(rows[i].get('hvh'))

            if s == '%':
                delta = running * hvh / 100.0
                raw_totaal[i] = delta
                running += delta
            elif s == '+':
                raw_totaal[i] = hvh
                running += hvh
            elif s == '-':
                raw_totaal[i] = -hvh
                running -= hvh
            elif s == '=':
                raw_totaal[i] = running   # toont lopend totaal, reset niet
            elif s in ('a', 'b', 'c'):
                pct = hvh if hvh != 0 else BTW_DEFAULTS.get(s, 0.0)
                delta = running * pct / 100.0
                raw_totaal[i] = delta
                running += delta
            elif s in ('S', 'V', 'G', 'X'):
                raw_totaal[i] = _sub.get(s, 0.0)
            elif s == '&':
                # Vereenvoudigd: behandel als %-opslag
                delta = running * hvh / 100.0
                raw_totaal[i] = delta
                running += delta

    # ── Uitvoer ───────────────────────────────────────────────────────────────
    out: list[dict] = []
    for i in range(n):
        t  = raw_totaal[i]
        tu = raw_toturen[i]
        pp = raw_prijspe[i]
        st = is_staart[i]

        if is_titel[i]:
            out.append({
                'prijspe':  '',
                'toturen':  format_nl_hvh(tu) if tu else '',
                'totaal':   format_nl(t),
                'is_staart': False,
            })
        elif st:
            out.append({
                'prijspe':  '',
                'toturen':  '',
                'totaal':   format_nl(t) if t != 0 else '',
                'is_staart': True,
            })
        else:
            out.append({
                'prijspe':  format_nl(pp) if pp else '',
                'toturen':  format_nl_hvh(tu) if tu else '',
                'totaal':   format_nl(t)  if t  else '',
                'is_staart': False,
            })
    return out


def totaal_begroting(calc_rows: list[dict], rows: list[dict]) -> float:
    """Som van alle S=1 rijen — voor de statusbalk (excl. staart)."""
    return sum(
        _num(c['totaal'])
        for c, r in zip(calc_rows, rows)
        if (r.get('s') or '').strip() == '1'
    )
