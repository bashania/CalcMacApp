"""Rekenmodule voor de begrotingstabel.

Berekent eenheidsprijs, totale uren en regeltotaal per begrotingsregel,
en telt deze op naar bovenliggende titelrijen (S=1/2/3).

Berekende velden worden NIET in het .c4y bestand geschreven — Calc4You
vult die zelf in bij het openen. Deze module dient alleen om de viewer
direct te tonen wat het bestand straks oplevert.
"""

from __future__ import annotations

from typing import Iterable

from app.c4y_io import format_nl, format_nl_hvh, parse_nl_number


# S-codes die in titelrijen voorkomen (cumulatief)
TITEL_NIVEAUS = {'1', '2', '3'}

# Begrotingsregel-stuurcodes (tellen mee in bovenliggende titel)
# Lege string = standaard begrotingsregel.
BEGROTING_S_CODES = {'', 'S', 'V', 'G', '?', 'X'}


def _num(value) -> float:
    """Parse NL-getal naar float, lege/onleesbare waarden → 0."""
    parsed = parse_nl_number(value)
    return parsed if parsed is not None else 0.0


def _bereken_regel(row: dict) -> tuple[float, float, float]:
    """(prijspe, toturen, totaal) voor één begrotingsregel."""
    arb       = _num(row.get('arb'))
    maa       = _num(row.get('maa'))
    mee       = _num(row.get('mee'))
    ond       = _num(row.get('ond'))
    hvh       = _num(row.get('hvh'))
    uurloon   = _num(row.get('uurloon'))
    productie = _num(row.get('productie'))

    prijspe = arb * uurloon * (1.0 + productie / 100.0) + maa + mee + ond
    toturen = hvh * arb
    totaal  = hvh * prijspe
    return prijspe, toturen, totaal


def recompute(rows: Iterable[dict]) -> list[dict]:
    """Bereken per rij (prijspe, toturen, totaal).

    Argumenten
    ----------
    rows : iterabel van dicts met (mogelijk) keys
        s, hvh, arb, maa, mee, ond, uurloon, productie
        Waarden zijn strings in Nederlands getalformaat ('1.234,56') of leeg.

    Resultaat
    ---------
    list met per rij ``{'prijspe': str, 'toturen': str, 'totaal': str}``
    in Nederlandse opmaak. Voor titelrijen (S=1/2/3) is ``prijspe`` leeg
    en bevatten ``toturen`` en ``totaal`` de som van alle onderliggende
    begrotingsregels tot de volgende titel van gelijk of hoger niveau.
    """
    rows = list(rows)
    n = len(rows)
    raw_totaal  = [0.0] * n  # numerieke waarden voor doorrekenen
    raw_toturen = [0.0] * n
    raw_prijspe = [0.0] * n  # alleen relevant voor begrotingsregels

    is_titel = [False] * n
    for i, r in enumerate(rows):
        s = (r.get('s') or '').strip()
        if s in TITEL_NIVEAUS:
            is_titel[i] = True
        elif s in BEGROTING_S_CODES:
            p, t, tot = _bereken_regel(r)
            raw_prijspe[i] = p
            raw_toturen[i] = t
            raw_totaal[i]  = tot
        # Onbekende S-code → laten staan op 0; veiliger dan crashen.

    # Roll-up van titelrijen: voor elke titel-i, sommeer de begrotingsregels
    # tot de volgende titel met s_niveau ≤ huidig niveau.
    for i in range(n):
        if not is_titel[i]:
            continue
        niveau = int((rows[i].get('s') or '').strip())
        som_tot = 0.0
        som_uren = 0.0
        for j in range(i + 1, n):
            s_j = (rows[j].get('s') or '').strip()
            if s_j in TITEL_NIVEAUS and int(s_j) <= niveau:
                break
            som_tot  += raw_totaal[j]
            som_uren += raw_toturen[j]
        raw_totaal[i]  = som_tot
        raw_toturen[i] = som_uren

    out: list[dict] = []
    for i in range(n):
        if is_titel[i]:
            out.append({
                'prijspe': '',
                'toturen': format_nl_hvh(raw_toturen[i]) if raw_toturen[i] else '',
                'totaal':  format_nl(raw_totaal[i]),
            })
        else:
            out.append({
                'prijspe': format_nl(raw_prijspe[i]) if raw_prijspe[i] else '',
                'toturen': format_nl_hvh(raw_toturen[i]) if raw_toturen[i] else '',
                'totaal':  format_nl(raw_totaal[i]) if raw_totaal[i] else '',
            })
    return out


def totaal_begroting(calc_rows: list[dict], rows: list[dict]) -> float:
    """Totaal van alle S=1 rijen — voor de statusbalk."""
    totaal = 0.0
    for c, r in zip(calc_rows, rows):
        if (r.get('s') or '').strip() == '1':
            totaal += _num(c.get('totaal'))
    return totaal
