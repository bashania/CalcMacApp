#!/bin/bash
# Dubbel-klikbare launcher voor CalcMacApp op macOS.
#
# Werking: ga naar de map waarin dit script staat, maak (indien nog niet
# aanwezig) een Python virtual environment .venv aan met de juiste
# dependencies, en start de app.
#
# Gebruik: dubbelklik in Finder. Als macOS klaagt dat het script niet
# uitvoerbaar is, draai eenmalig in Terminal:
#     chmod +x CalcMacApp.command

set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "→ Eerste start: virtuele omgeving en dependencies installeren…"
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
fi

exec .venv/bin/python -m app.main
