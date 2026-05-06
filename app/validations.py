"""Logboek-validaties voor een geladen begroting.

Levert per rij een lijst Issue-objecten op. De UI gebruikt deze om
inline waarschuwingen te tonen (gele/rode dotjes) en in de Inspector
een lijst.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.c4y_io import C4YDocument, parse_nl_number


SEVERITY_ERROR   = 'error'
SEVERITY_WARNING = 'warning'
SEVERITY_INFO    = 'info'

TITEL_S_CODES   = ('1', '2', '3')
STAART_S_CODES  = ('/', '%', '&', '=', '+', '-', 'a', 'b', 'c')
BEGROTING_S     = ('', 'S', 'V', 'G', '?', 'X')


@dataclass(frozen=True)
class Issue:
    row_idx: int
    severity: str
    message: str


def _num(v: str) -> float | None:
    return parse_nl_number(v)


def validate(doc: C4YDocument) -> list[Issue]:
    """Geeft alle gevonden issues terug, geordend per rij-index."""
    issues: list[Issue] = []
    rows = doc.begrotingen
    n = len(rows)
    if n == 0:
        return issues

    has_staart = False
    last_staart_is_eq = False
    has_x_post = False

    for i, el in enumerate(rows):
        s = (el.findtext('s') or '').strip()
        oms = (el.findtext('oms') or '').strip()
        hvh = _num(el.findtext('hvh') or '')
        arb = _num(el.findtext('arb') or '')
        maa = _num(el.findtext('maa') or '')
        mee = _num(el.findtext('mee') or '')
        ond = _num(el.findtext('ond') or '')
        code1 = (el.findtext('code1') or '').strip()

        if s in TITEL_S_CODES:
            # Titels mogen een kophoeveelheid > 1 hebben (Calc4You: bij
            # bv. "2 dezelfde gevels"). Negatief is wel een fout.
            if hvh is not None and hvh < 0:
                issues.append(Issue(
                    i, SEVERITY_ERROR,
                    'Titel heeft negatieve hoeveelheid.',
                ))
            if hvh is not None and hvh > 1:
                issues.append(Issue(
                    i, SEVERITY_INFO,
                    f'Titel ({s}) heeft kophoeveelheid '
                    f'{el.findtext("hvh")} — onderliggende totalen '
                    f'worden hiermee vermenigvuldigd.',
                ))
            # Geen prijzen op een titel
            if any(v is not None and v != 0
                   for v in (arb, maa, mee, ond)):
                issues.append(Issue(
                    i, SEVERITY_WARNING,
                    'Titel heeft prijsinvoer (arb/maa/mee/ond) — '
                    'die hoort op een begrotingsregel te staan.',
                ))
        elif s in STAART_S_CODES:
            has_staart = True
            last_staart_is_eq = (s == '=')
        else:
            # Begrotingsregel
            heeft_prijs = any(
                v is not None and v != 0 for v in (arb, maa, mee, ond)
            )
            heeft_hvh = hvh is not None and hvh != 0

            if not heeft_hvh:
                issues.append(Issue(
                    i, SEVERITY_WARNING,
                    'Regel zonder hoeveelheid.',
                ))
            if not heeft_prijs:
                issues.append(Issue(
                    i, SEVERITY_WARNING,
                    'Regel zonder prijs (arb/maa/mee/ond allemaal leeg).',
                ))
            if ond is not None and ond > 0 and not code1:
                issues.append(Issue(
                    i, SEVERITY_INFO,
                    'Onderaanneming ingevuld maar geen Code1 '
                    '(naam onderaannemer).',
                ))
            if hvh is not None and hvh < 0:
                issues.append(Issue(
                    i, SEVERITY_WARNING,
                    'Negatieve hoeveelheid.',
                ))
            if not oms:
                issues.append(Issue(
                    i, SEVERITY_INFO,
                    'Regel zonder omschrijving.',
                ))
            if s == 'X':
                has_x_post = True

    # Staart-checks na de loop
    if has_staart and not last_staart_is_eq:
        # Zoek de laatste staart-rij
        last_idx = max(
            i for i, el in enumerate(rows)
            if (el.findtext('s') or '').strip() in STAART_S_CODES
        )
        issues.append(Issue(
            last_idx, SEVERITY_WARNING,
            "Staart eindigt niet met '=' (totaalregel). "
            'Calc4You verwacht een afsluitend = teken.',
        ))

    # X-post-check: als er X-rijen zijn, moet er ook een 'X' in de staart staan
    if has_x_post and has_staart:
        x_in_staart = False
        for el in rows:
            s = (el.findtext('s') or '').strip()
            if s in STAART_S_CODES and s == 'X':
                x_in_staart = True
                break
        # 'X' als staart-code wordt afzonderlijk behandeld als X-totaal
        # Hier is het iets impliciets — wij zouden het info-niveau geven
        if not x_in_staart:
            # Markeer eerste X-post om niet te lawaaierig te zijn
            for i, el in enumerate(rows):
                if (el.findtext('s') or '').strip() == 'X':
                    issues.append(Issue(
                        i, SEVERITY_INFO,
                        'X-post aanwezig maar niet doorgeteld in '
                        'de staart (geen X-rij in staart).',
                    ))
                    break

    issues.sort(key=lambda x: (x.row_idx, x.severity))
    return issues


def issues_by_row(issues: list[Issue]) -> dict[int, list[Issue]]:
    """Groepeer issues per rij voor de inline-rendering."""
    out: dict[int, list[Issue]] = {}
    for it in issues:
        out.setdefault(it.row_idx, []).append(it)
    return out


def severity_rank(severity: str) -> int:
    return {'error': 2, 'warning': 1, 'info': 0}.get(severity, 0)


def worst_severity(items: list[Issue]) -> str | None:
    if not items:
        return None
    return max(items, key=lambda x: severity_rank(x.severity)).severity
