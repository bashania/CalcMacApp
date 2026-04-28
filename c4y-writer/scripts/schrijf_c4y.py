#!/usr/bin/env python3
"""
schrijf_c4y.py — Genereer een Calc4You .c4y bestand vanuit JSON-invoer.

Gebruik:
    python3 schrijf_c4y.py --invoer <pad naar invoer.json> --uitvoer <pad naar .c4y>

Zie de c4y-writer SKILL.md voor het invoer JSON-formaat.
"""

import argparse
import json


# ── Constanten ────────────────────────────────────────────────────────────────
DEFAULT_UURLOON = 45.0
DEFAULT_FACTOR  = 25.0

LOGO = (r"C:\Users\bas\OneDrive - Everts Groep\Management Team - Logo's Everts"
        r"\_Logo als JPG of PNG\240311 EVE logo 5 cm.jpg")

RTF = (r"{\rtf1\ansi\ansicpg1252\deff0\deflang1043"
       r"{\fonttbl{\f0\fnil\fcharset0 Microsoft Sans Serif;}}"
       "\n" r"{\colortbl ;\red14\green14\blue14;}"
       "\n" r"\viewkind4\uc1\pard\cf1\f0\fs17\par"
       "\n}")


# ── Getalopmaak (Nederlands: komma decimaal, punt duizendtallen) ──────────────
def nl(val, dec=2):
    """Formatteer getal naar Nederlandse notatie."""
    if val is None or val == '':
        return ''
    v = float(val)
    if v == 0 and dec > 0:
        return '0,' + '0' * dec
    negatief  = v < 0
    v         = abs(v)
    int_deel  = int(v)
    dec_deel  = v - int_deel
    int_str   = f"{int_deel:,}".replace(',', '.')
    if dec > 0:
        dec_str = f"{round(dec_deel, dec):.{dec}f}"[2:]
        return ('-' if negatief else '') + f"{int_str},{dec_str}"
    return ('-' if negatief else '') + int_str


def nl_hvh(val):
    """Hoeveelheid: geen decimalen als het een geheel getal is."""
    v = round(float(val), 2)
    if v == int(v):
        return nl(int(v), 0)
    return nl(v, 2)


# ── Volgnummer teller ──────────────────────────────────────────────────────────
_nr = [0]


def nxt():
    _nr[0] += 1
    return f"{_nr[0]:05d}"


def reset_nr():
    _nr[0] = 0


# ── XML-escaping ───────────────────────────────────────────────────────────────
def xml_esc(tekst: str) -> str:
    """Escape speciale XML-tekens in tekstvelden."""
    return (tekst
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))


# ── Begroting-blok bouwen ──────────────────────────────────────────────────────
def begroting(code, s, oms, hvh='', enh='', arb=None, maa=None, ond='',
              code1='', code2='', code3='', code4='',
              uurloon=None, productie=None):
    """Bouw een <begroting> XML-blok.

    Berekende velden (totaal, toturen, aard, totarbeid, prijspe, althv)
    worden NIET ingevuld — Calc4You berekent deze zelf.
    """
    arb_s  = nl(arb, 2)  if arb is not None and float(arb) != 0 else ''
    maa_s  = nl(maa, 2)  if maa is not None and float(maa) != 0 else ''
    ond_s  = nl(ond, 2)  if ond != '' and ond is not None else ''
    ul_s   = nl(uurloon or DEFAULT_UURLOON) if arb else ''
    prod_s = nl(productie or DEFAULT_FACTOR, 2) if arb else ''
    hvh_s  = nl_hvh(hvh) if hvh != '' else ''
    s_tag  = f"<s>{s}</s>" if s else "<s />"
    oms_e  = xml_esc(str(oms))

    return (
        f"  <begroting>\n"
        f"    <nr>{nxt()}</nr>\n"
        f"    <code>{code}</code>\n"
        f"    {s_tag}\n"
        f"    <oms>{oms_e}</oms>\n"
        f"    <hvh>{hvh_s}</hvh>\n"
        f"    <enh>{enh}</enh>\n"
        f"    <arb>{arb_s}</arb>\n"
        f"    <maa>{maa_s}</maa>\n"
        f"    <mee />\n"
        f"    <ond>{ond_s}</ond>\n"
        f"    <totaal />\n"
        f"    <toturen />\n"
        f"    <prijspe />\n"
        f"    <bestekc />\n"
        f"    <admi />\n"
        f"    <admi_ar />\n"
        f"    <admi_ma />\n"
        f"    <admi_me />\n"
        f"    <admi_oa>0</admi_oa>\n"
        f"    <meet />\n"
        f"    <totarbeid />\n"
        f"    <totuur />\n"
        f"    <code1>{code1}</code1>\n"
        f"    <code2>{code2}</code2>\n"
        f"    <code3>{code3}</code3>\n"
        f"    <code4>{code4}</code4>\n"
        f"    <uurloon>{ul_s}</uurloon>\n"
        f"    <mnr />\n"
        f"    <btw />\n"
        f"    <rsu />\n"
        f"    <aard />\n"
        f"    <productie>{prod_s}</productie>\n"
        f"    <ouder />\n"
        f"    <althv />\n"
        f"    <startjr />\n"
        f"    <cyclus />\n"
        f"    <stopjr />\n"
        f"    <prioriteit />\n"
        f"    <dccode />\n"
        f"    <dcbedrag />\n"
        f"    <link />\n"
        f"  </begroting>"
    )


# ── alginfo sectie ─────────────────────────────────────────────────────────────
def maak_alginfo(project, uurloon):
    """Projectkoptekst zonder berekende totalen — app vult deze zelf in."""
    return (
        f"  <alginfo>\n"
        f"    <type>E</type>\n"
        f"    <kop>{xml_esc(project.get('nummer', ''))}</kop>\n"
        f"    <r1>{xml_esc(project.get('naam', ''))}</r1>\n"
        f"    <r2>{xml_esc(project.get('adres', ''))}</r2>\n"
        f"    <r3 />\n"
        f"    <r4>{xml_esc(project.get('omschrijving', ''))}</r4>\n"
        f"    <r5 />\n"
        f"    <arbeid />\n"
        f"    <materiaal />\n"
        f"    <materieel />\n"
        f"    <onderaan />\n"
        f"    <totaal />\n"
        f"    <datum1 /><datum2 /><bv /><bo /><to /><bg /><ng />\n"
        f"    <an>Everts Onderhoud &amp; Renovatie</an>\n"
        f"    <ac /><cs /><og /><ad /><ih /><uren />\n"
        f"    <logo>{LOGO}</logo>\n"
        f"    <ul>{nl(uurloon)}</ul>\n"
        f"    <pb /><rg>-1</rg><ms>0</ms><calculator />\n"
        f"    <versie>v1</versie><gecontroleerd /><overig />\n"
        f"    <rawraw /><rawfco /><rawmax /><rawver /><rawloc />\n"
        f"    <rawin1 /><rawin2 /><rawin3 />\n"
        f"    <deelbest /><deelcalc />\n"
        f"    <mjob>False</mjob>\n"
        f"  </alginfo>"
    )


# ── Hoofdfunctie: JSON -> .c4y ────────────────────────────────────────────────
def genereer_c4y(invoer: dict, uurloon=None, factor=None) -> str:
    """Converteer een invoer-dict naar een .c4y XML-string."""
    reset_nr()

    ul  = float(uurloon or invoer.get('uurloon', DEFAULT_UURLOON))
    fac = float(factor  or invoer.get('factor',  DEFAULT_FACTOR))

    blocks = []

    for hfst in invoer.get('hoofdstukken', []):
        # S=1 hoofdstuk (titel, geen kosten)
        blocks.append(begroting(
            hfst['code'], hfst.get('s', '1'), hfst['oms'],
            hvh='1', enh=''
        ))

        for seg in hfst.get('segmenten', []):
            # S=2 segment (titel, geen kosten)
            blocks.append(begroting(
                seg['code'], seg.get('s', '2'), seg['oms'],
                hvh='1', enh=''
            ))

            for noemer in seg.get('noemers', []):
                # Begrotingsregel: S leeg (of G/S/V/? voor speciale posten)
                # Hier staan hoeveelheid, eenheid en kosten per eenheid
                s_code = noemer.get('s_override', '')  # leeg = normale regel
                blocks.append(begroting(
                    noemer['code'],
                    s_code,
                    noemer['oms'],
                    hvh=noemer.get('hvh', ''),
                    enh=noemer.get('enh', ''),
                    arb=noemer.get('arb'),
                    maa=noemer.get('maa'),
                    ond=noemer.get('ond', ''),
                    code1=noemer.get('code1', ''),
                    code2=noemer.get('code2', ''),
                    code3=noemer.get('code3', ''),
                    code4=noemer.get('code4', ''),
                    uurloon=ul,
                    productie=fac,
                ))

    project = invoer.get('project', {})
    alginfo = maak_alginfo(project, ul)

    delen = [
        '<?xml version="1.0" standalone="yes"?>',
        '<calc4you>',
        alginfo,
        '\n'.join(blocks),
        '  <versie>\n    <nummer>66</nummer>\n    <assembly>6.6.0.10</assembly>\n  </versie>',
        f'  <toelichting>\n    <tekst>{RTF}\n</tekst>\n  </toelichting>',
        ('  <offerte>\n    <aan /><adres /><plaats /><offertedatum />'
         '<offerteeinddatum />\n    <offertenummer /><email /><telefoon />'
         '<btw /><brief />\n  </offerte>'),
        '</calc4you>',
    ]
    return '\n'.join(delen)


def main():
    parser = argparse.ArgumentParser(description='Genereer een Calc4You .c4y bestand.')
    parser.add_argument('--invoer',  required=True, help='Pad naar invoer JSON-bestand')
    parser.add_argument('--uitvoer', required=True, help='Pad naar uitvoer .c4y bestand')
    args = parser.parse_args()

    with open(args.invoer, encoding='utf-8') as f:
        data = json.load(f)

    xml_inhoud = genereer_c4y(data)

    with open(args.uitvoer, 'w', encoding='utf-8') as f:
        f.write(xml_inhoud)

    print(f"Opgeslagen: {args.uitvoer}")


if __name__ == '__main__':
    main()
