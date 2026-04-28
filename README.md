# CalcMacApp

Mac (en straks Windows) applicatie voor het bekijken en bewerken van Calc4You
`.c4y` bestanden.

## Wat doet de app

- Opent een `.c4y` bestand
- Toont projectkop (nummer, naam, adres, omschrijving) en alle begrotingsregels
  in een tabel
- Laat je velden bewerken (omschrijving, hoeveelheid, eenheid, normen,
  onderaanneming, codes)
- Slaat het bestand terug op als geldige Calc4You-XML met Nederlands getalformaat

## Tech stack

Python 3.11+ met **PyQt6**. Eén codebase voor Mac en Windows — pakken voor de
respectievelijke platforms gebeurt later met `pyinstaller` of `briefcase`.

De I/O-module `app/c4y_io.py` is puur Python (`xml.etree.ElementTree`) en kan
los van de GUI gebruikt worden.

## Installeren en starten

```bash
python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 -m app.main
```

## Voorbeeldbestand

In `samples/` staat `voorbeeld.json` (invoer voor de `c4y-writer` skill) en
kan je `voorbeeld.c4y` regenereren met:

```bash
python3 c4y-writer/scripts/schrijf_c4y.py \
  --invoer samples/voorbeeld.json \
  --uitvoer samples/voorbeeld.c4y
```

## Skill: c4y-writer

In `c4y-writer/` staat de SKILL die het `.c4y` formaat documenteert en een
schrijver biedt vanuit gestructureerde JSON. De viewer/editor in `app/` werkt
direct op de XML en hergebruikt deze documentatie als referentie.
