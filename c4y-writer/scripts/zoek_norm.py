#!/usr/bin/env python3
"""
zoek_norm.py — Zoek een norm op in de Everts normbibliotheek.

Gebruik:
    python3 zoek_norm.py --code OHD03-khB
    python3 zoek_norm.py --zoek "kozijn" --systeem OHD03
    python3 zoek_norm.py --lijst OHD03

De normbibliotheek staat in:
    /tmp/skills/c4y-writer/references/normen.json
"""

import argparse
import json
import sys
import os

NORMEN_PAD = os.path.join(
    os.path.dirname(__file__), '..', 'references', 'normen.json'
)


def laad_normen():
    pad = os.path.normpath(NORMEN_PAD)
    if not os.path.exists(pad):
        # Fallback: zoek ook in /tmp/skills/
        pad = '/tmp/skills/c4y-writer/references/normen.json'
    with open(pad, encoding='utf-8') as f:
        return json.load(f)


def toon_norm(n):
    arb = n['arb'] if n['arb'] is not None else '-'
    maa = n['maa'] if n['maa'] is not None else '-'
    print(f"  {n['code']:25} arb={arb:<6}  maa={maa:<8}  {n['oms']}")


def main():
    parser = argparse.ArgumentParser(description='Zoek norm in bibliotheek.')
    parser.add_argument('--code',    help='Exacte normcode (bv. OHD03-khB)')
    parser.add_argument('--zoek',    help='Zoekterm in omschrijving')
    parser.add_argument('--systeem', help='Filter op systeem (bv. OHD03, OMS03)')
    parser.add_argument('--lijst',   help='Toon alle normen voor een systeem')
    args = parser.parse_args()

    normen = laad_normen()

    if args.code:
        n = normen.get(args.code)
        if n:
            toon_norm(n)
        else:
            print(f"Niet gevonden: {args.code}")
            # Suggesties
            sugg = [k for k in normen if args.code.lower() in k.lower()][:5]
            if sugg:
                print("Bedoelt u misschien:")
                for s in sugg:
                    toon_norm(normen[s])
        return

    if args.lijst:
        sys_filter = args.lijst.upper()
        resultaten = [n for n in normen.values()
                      if (n['systeem'] or '').upper() == sys_filter
                      or n['code'].upper().startswith(sys_filter)]
        print(f"Normen voor systeem {sys_filter} ({len(resultaten)} stuks):")
        for n in resultaten:
            toon_norm(n)
        return

    if args.zoek:
        zoek = args.zoek.lower()
        resultaten = [n for n in normen.values()
                      if zoek in n['oms'].lower() or zoek in n['code'].lower()]
        if args.systeem:
            resultaten = [n for n in resultaten
                          if args.systeem.upper() in n['code'].upper()]
        print(f"{len(resultaten)} resultaten voor '{args.zoek}':")
        for n in resultaten[:30]:
            toon_norm(n)
        if len(resultaten) > 30:
            print(f"  ... en {len(resultaten)-30} meer. Verfijn met --systeem.")
        return

    parser.print_help()


if __name__ == '__main__':
    main()
