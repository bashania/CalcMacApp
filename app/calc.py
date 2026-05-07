"""Rekenmodule voor de begrotingstabel.

Fase 1 — begrotingsregels: prijspe, toturen, regeltotaal.
Fase 2 — titel-rollup: S=1/2/3 koppen sommeren onderliggende regels.
Fase 3 — staart: `/`-rij detecteert het begin, daarna `%`, `+`, `-`,
          `=`, `a`, `b`, `c`, `&`, `S`, `G`, `V`, `X`.

Berekende velden worden NIET in het .c4y bestand geschreven — Calc4You
vult die zelf in bij het openen. Deze module dient uitsluitend de viewer-UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.c4y_io import format_nl, format_nl_hvh, parse_nl_number  # noqa: F401


# ── S-code classificatie ──────────────────────────────────────────────────────
TITEL_NIVEAUS      = frozenset({'1', '2', '3'})
BEGROTING_S_CODES  = frozenset({'', 'S', 'V', 'G', '?', 'X'})
STAART_S_CODES     = frozenset({'/', '%', '&', '=', '+', '-', 'a', 'b', 'c'})

# Standaard BTW-percentages als hvh leeg is
BTW_DEFAULTS: dict[str, float] = {'a': 21.0, 'b': 9.0, 'c': 0.0}

# BTW-kenmerken op begrotingsregels: 'h' = hoog, 'l' = laag, 'v' = verlegd.
# Leeg of onbekend wordt als 'h' (hoog) behandeld. Map a/b/c-staartcodes
# naar hun bijbehorende kenmerk.
BTW_KENMERKEN = ('h', 'l', 'v')
ABC_NAAR_KENMERK: dict[str, str] = {'a': 'h', 'b': 'l', 'c': 'v'}

# Velden die `recompute` uit elke rij leest. Centraal hier zodat main.py
# (die rows uit het XML-document opbouwt) niet stilletjes kan vergeten een
# veld door te geven — wat tot subtiele bugs leidt zoals btw=leeg-default.
RECOMPUTE_INPUT_TAGS: tuple[str, ...] = (
    's', 'hvh', 'arb', 'maa', 'mee', 'ond', 'uurloon', 'productie', 'btw',
)


def _btw_kenmerk(row: dict) -> str:
    """Geef het BTW-kenmerk van een begrotingsregel terug ('h'|'l'|'v').

    Leeg, onbekend of een afwijkende waarde valt terug op 'h' (hoog) —
    de Nederlandse standaard voor goederen en diensten.
    """
    raw = (row.get('btw') or '').strip().lower()
    return raw if raw in BTW_KENMERKEN else 'h'


def _num(value) -> float:
    parsed = parse_nl_number(value)
    return parsed if parsed is not None else 0.0


def _bereken_regel(row: dict) -> dict:
    """Bereken alle afgeleide bedragen voor één begrotingsregel.

    De Factor (productie) is een percentage opslag dat over de hele regel
    wordt gezet — niet alleen op arbeid. Resulteert in:

        basis_pe   = arb * uurloon + maa + mee + ond
        prijspe    = basis_pe * (1 + factor/100)
        tot_arb    = hvh * arb * uurloon * (1 + factor/100)
        tot_maa    = hvh * maa            * (1 + factor/100)
        tot_mee    = hvh * mee            * (1 + factor/100)
        tot_ond    = hvh * ond            * (1 + factor/100)
        toturen    = hvh * arb            (uren tellen niet mee in de opslag)
        totaal     = hvh * prijspe        (= som van tot_arb..tot_ond)
    """
    arb       = _num(row.get('arb'))
    maa       = _num(row.get('maa'))
    mee       = _num(row.get('mee'))
    ond       = _num(row.get('ond'))
    hvh       = _num(row.get('hvh'))
    uurloon   = _num(row.get('uurloon'))
    productie = _num(row.get('productie'))
    fac       = 1.0 + productie / 100.0

    basis_pe = arb * uurloon + maa + mee + ond
    prijspe  = basis_pe * fac
    return {
        'prijspe': prijspe,
        'toturen': hvh * arb,
        'totaal':  hvh * prijspe,
        'tot_arb': hvh * arb * uurloon * fac,
        'tot_maa': hvh * maa * fac,
        'tot_mee': hvh * mee * fac,
        'tot_ond': hvh * ond * fac,
    }


def recompute(
    rows: Iterable[dict],
    btw_defaults: dict[str, float] | None = None,
) -> list[dict]:
    """Bereken per rij (prijspe, toturen, totaal, is_staart).

    Argumenten
    ----------
    rows : iterabel van dicts met keys
        s, hvh, arb, maa, mee, ond, uurloon, productie, btw
        Waarden zijn strings in Nederlands getalformaat of leeg.
    btw_defaults : optioneel
        Override op de module-constante `BTW_DEFAULTS` (a/b/c → percentage).
        Bedoeld voor app-instellingen die de overheidstarieven volgen.
        Ontbrekende keys vallen terug op `BTW_DEFAULTS`.

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
    raw_arb     = [0.0] * n   # totaal arbeid €
    raw_maa     = [0.0] * n   # totaal materiaal €
    raw_mee     = [0.0] * n   # totaal materieel €
    raw_ond     = [0.0] * n   # totaal onderaanneming €
    is_titel    = [False] * n
    is_staart   = [False] * n
    raw_warnings: list[list[str]] = [[] for _ in range(n)]

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
            res = _bereken_regel(r)
            raw_prijspe[i] = res['prijspe']
            raw_toturen[i] = res['toturen']
            raw_totaal[i]  = res['totaal']
            raw_arb[i]     = res['tot_arb']
            raw_maa[i]     = res['tot_maa']
            raw_mee[i]     = res['tot_mee']
            raw_ond[i]     = res['tot_ond']

    # ── Fase 2: titel-rollup (S=1/2/3) ───────────────────────────────────────
    for i in range(n):
        if not is_titel[i]:
            continue
        niveau = int((rows[i].get('s') or '').strip())
        som_tot = som_uren = 0.0
        som_arb = som_maa = som_mee = som_ond = 0.0
        for j in range(i + 1, n):
            if is_staart[j]:
                break
            s_j = (rows[j].get('s') or '').strip()
            if s_j in TITEL_NIVEAUS and int(s_j) <= niveau:
                break
            som_tot  += raw_totaal[j]
            som_uren += raw_toturen[j]
            som_arb  += raw_arb[j]
            som_maa  += raw_maa[j]
            som_mee  += raw_mee[j]
            som_ond  += raw_ond[j]
        raw_totaal[i]  = som_tot
        raw_toturen[i] = som_uren
        raw_arb[i]     = som_arb
        raw_maa[i]     = som_maa
        raw_mee[i]     = som_mee
        raw_ond[i]     = som_ond

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
        # Subtotalen per BTW-kenmerk: directe kosten gesplitst in h/l/v.
        # X-posten en titels uitgesloten, identiek aan directe_kosten.
        _btw_sub = {
            cat: sum(
                raw_totaal[i] for i in range(staart_idx)
                if not is_titel[i]
                and (rows[i].get('s') or '').strip() != 'X'
                and _btw_kenmerk(rows[i]) == cat
            )
            for cat in BTW_KENMERKEN
        }

        # Overheid-percentages (uit settings) of module-defaults
        btw_pcts = dict(BTW_DEFAULTS)
        if btw_defaults:
            btw_pcts.update(btw_defaults)

        running = directe_kosten
        raw_totaal[staart_idx] = directe_kosten  # '/' rij
        # Snapshot van running op het moment dat de eerste a/b/c-rij langskomt;
        # alle a/b/c-rijen delen dezelfde grondslag-scaling zodat een eerdere
        # BTW-rij niet de grondslag van een latere ophoogt.
        btw_anchor: float | None = None

        for i in range(staart_idx + 1, n):
            s   = (rows[i].get('s') or '').strip()
            hvh = _num(rows[i].get('hvh'))

            if s == '%':
                if hvh == 0:
                    raw_warnings[i].append('Percentage 0 — geen opslag')
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
                hvh_raw = (rows[i].get('hvh') or '').strip()
                if hvh == 0 or not hvh_raw:
                    pct = btw_pcts.get(s, 0.0)
                    raw_warnings[i].append(
                        f'Default {pct:g}% gebruikt — geen percentage in Hvh'
                    )
                else:
                    pct = hvh
                # Grondslag = directe-kosten-subset met dit BTW-kenmerk,
                # proportioneel meegeschaald met de cumulatieve groei tot
                # vóór de eerste BTW-rij (zodat Onvoorzien/AK/W&R doortikken
                # maar a en b dezelfde "ex BTW"-grondslag delen).
                if btw_anchor is None:
                    btw_anchor = running
                cat = ABC_NAAR_KENMERK[s]
                kenmerk_subset = _btw_sub.get(cat, 0.0)
                scale = (btw_anchor / directe_kosten) if directe_kosten else 1.0
                grondslag = kenmerk_subset * scale
                delta = grondslag * pct / 100.0
                raw_totaal[i] = delta
                running += delta
            elif s in ('S', 'V', 'G'):
                # Stelposten/verrekenposten/geschatte posten zitten al in
                # directe kosten — alleen tonen, niet nogmaals optellen.
                raw_totaal[i] = _sub.get(s, 0.0)
            elif s == 'X':
                # X-posten zijn juist BUITEN directe kosten — nu wel optellen.
                delta = _sub.get('X', 0.0)
                if delta == 0:
                    raw_warnings[i].append(
                        'Geen X-posten in begroting — rij heeft geen effect'
                    )
                raw_totaal[i] = delta
                running += delta
            elif s == '&':
                # Vereenvoudigd: behandel als %-opslag
                if hvh == 0:
                    raw_warnings[i].append('Percentage 0 — geen opslag')
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

        ar = raw_arb[i]
        ma = raw_maa[i]
        me = raw_mee[i]
        on = raw_ond[i]

        if is_titel[i]:
            out.append({
                'prijspe':  '',
                'toturen':  format_nl_hvh(tu) if tu else '',
                'totaal':   format_nl(t),
                'tot_arb':  format_nl(ar) if ar else '',
                'tot_maa':  format_nl(ma) if ma else '',
                'tot_mee':  format_nl(me) if me else '',
                'tot_ond':  format_nl(on) if on else '',
                'is_staart': False,
                'warnings': list(raw_warnings[i]),
            })
        elif st:
            out.append({
                'prijspe':  '',
                'toturen':  '',
                'totaal':   format_nl(t) if t != 0 else '',
                'tot_arb':  '',
                'tot_maa':  '',
                'tot_mee':  '',
                'tot_ond':  '',
                'is_staart': True,
                'warnings': list(raw_warnings[i]),
            })
        else:
            out.append({
                'prijspe':  format_nl(pp) if pp else '',
                'toturen':  format_nl_hvh(tu) if tu else '',
                'totaal':   format_nl(t)  if t  else '',
                'tot_arb':  format_nl(ar) if ar else '',
                'tot_maa':  format_nl(ma) if ma else '',
                'tot_mee':  format_nl(me) if me else '',
                'tot_ond':  format_nl(on) if on else '',
                'is_staart': False,
                'warnings': list(raw_warnings[i]),
            })
    return out


def totaal_begroting(calc_rows: list[dict], rows: list[dict]) -> float:
    """Som van alle S=1 rijen — voor de statusbalk (excl. staart)."""
    return sum(
        _num(c['totaal'])
        for c, r in zip(calc_rows, rows)
        if (r.get('s') or '').strip() == '1'
    )


def eindtotaal_begroting(
    calc_rows: list[dict], rows: list[dict],
) -> float | None:
    """Eindbedrag van de begroting incl. BTW.

    Convention: de laatste '=' rij die op of NA de laatste BTW-rij (a/b/c)
    voorkomt. Vallen we terug op de laatste '=' als er geen BTW-rij is.
    Geeft None als er geen '=' in de staart staat.

    Reden: Calc4You-bestanden herhalen na S/V/G-tonen vaak nog een '=' met
    hetzelfde eindbedrag; "laatste =" zou dan toevallig kloppen, maar als een
    gebruiker per ongeluk een tussentotaal toevoegt na de echte eindrij,
    veranderde het label onbedoeld. Door 'na BTW' als anker te nemen blijven
    we robuust zonder van Calc4You's gedrag af te wijken.
    """
    last_btw_idx = -1
    last_eq_idx = -1
    last_eq_after_btw_idx = -1
    for i, r in enumerate(rows):
        s = (r.get('s') or '').strip()
        if s in ('a', 'b', 'c'):
            last_btw_idx = i
        elif s == '=':
            last_eq_idx = i
            if i >= last_btw_idx:
                last_eq_after_btw_idx = i
    chosen = last_eq_after_btw_idx if last_eq_after_btw_idx >= 0 else last_eq_idx
    if chosen < 0:
        return None
    return parse_nl_number(calc_rows[chosen]['totaal'])


# ── Staart-validatie ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class StaartIssue:
    """Een gedetecteerde inconsistentie of waarschuwing in de staart.

    row      : index in `rows` waar het issue zit, of None voor staart-niveau.
    severity : 'error' (eindtotaal niet betrouwbaar), 'warning' (uitkomst kan
               afwijken van bedoeling), 'info' (puur observatie).
    code     : machine-leesbare identifier, voor UI-styling/i18n.
    message  : Nederlandse tekst, geschikt om in tooltip/dialoog te tonen.
    """
    row: int | None
    severity: str
    code: str
    message: str


def validate_staart(rows: list[dict]) -> list[StaartIssue]:
    """Detecteer problemen in de staart-structuur.

    Geeft een lege lijst terug als er geen staart is en ook geen losstaande
    staart-codes voorkomen — een begroting zonder staart is geldig.
    """
    issues: list[StaartIssue] = []

    staart_idx = next(
        (i for i, r in enumerate(rows)
         if (r.get('s') or '').strip() == '/'),
        None,
    )

    # E1: staart-codes zonder /-rij
    if staart_idx is None:
        if any((r.get('s') or '').strip() in (STAART_S_CODES - {'/'})
               for r in rows):
            issues.append(StaartIssue(
                None, 'error', 'orphan_staart',
                'Staart-rijen aanwezig zonder /-startrij',
            ))
        return issues

    # E5: dubbele /-rij
    second_slash = next(
        (i for i in range(staart_idx + 1, len(rows))
         if (rows[i].get('s') or '').strip() == '/'),
        None,
    )
    if second_slash is not None:
        issues.append(StaartIssue(
            second_slash, 'error', 'duplicate_slash',
            'Tweede /-rij — alleen één staartstart toegestaan',
        ))

    # E2: X-rij in staart maar geen X-posten in begroting boven /
    has_x_above = any(
        (r.get('s') or '').strip() == 'X'
        for r in rows[:staart_idx]
    )
    has_x_in_staart = any(
        (rows[i].get('s') or '').strip() == 'X'
        for i in range(staart_idx + 1, len(rows))
    )
    if has_x_in_staart and not has_x_above:
        issues.append(StaartIssue(
            None, 'warning', 'x_in_staart_no_source',
            'X-rij in staart maar geen X-posten in de begroting',
        ))

    # E3: per-rij waarschuwingen voor lege/0 hvh
    for i in range(staart_idx + 1, len(rows)):
        s = (rows[i].get('s') or '').strip()
        hvh_raw = (rows[i].get('hvh') or '').strip()
        hvh_num = parse_nl_number(hvh_raw)
        if s in ('a', 'b', 'c'):
            if not hvh_raw or hvh_num in (None, 0):
                pct = BTW_DEFAULTS.get(s, 0.0)
                issues.append(StaartIssue(
                    i, 'warning', 'btw_default',
                    f'Default {pct:g}% gebruikt — vul Hvh om te overschrijven',
                ))
        elif s in ('%', '&'):
            if hvh_num is None or hvh_num == 0:
                issues.append(StaartIssue(
                    i, 'warning', 'pct_zero',
                    'Percentage 0 — geen opslag',
                ))
        elif s in ('+', '-'):
            if hvh_num is None or hvh_num == 0:
                issues.append(StaartIssue(
                    i, 'info', 'plusminus_zero',
                    'Bedrag is 0 — rij heeft geen effect',
                ))

    # E4: geen '=' in staart -> geen eindtotaal bepaalbaar
    has_eq = any(
        (rows[i].get('s') or '').strip() == '='
        for i in range(staart_idx + 1, len(rows))
    )
    if not has_eq:
        issues.append(StaartIssue(
            staart_idx, 'warning', 'no_total',
            'Geen =-rij in staart — eindtotaal niet bepaalbaar',
        ))

    return issues
