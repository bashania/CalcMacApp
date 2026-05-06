# CalcMacApp

Native macOS-applicatie (Mac eerst, Windows later) voor het bekijken en
bewerken van Calc4You-`.c4y` begrotingen. Bestanden blijven 100 % uitwisselbaar
met de originele Calc4You-software op Windows.

## Wat doet de app

- **Open & bewerk** `.c4y` bestanden — alle gangbare velden inclusief
  onderaanneming en codes
- **Live rekenen** per regel: prijs/eenheid, totaal arbeid, materiaal,
  materieel, onderaanneming en regeltotaal — met factor over de hele regel
- **Titel-rollup**: S=1 / S=2 / S=3 koppen tellen onderliggende regels op
- **Volledige staart**: `/`, `%`, `&`, `=`, `+`, `-`, `a` (BTW hoog), `b`
  (BTW laag), `c` (BTW verlegd), `S`/`V`/`G`/`X`-totalen
- **Visueel onderscheid** per regeltype (hoofdstuk, locatie, stelpost,
  verrekenpost, X-post, BTW, …)
- **Hoofdstukken in/uitklappen** in-grid met disclosure-driehoekje
- **Drag & drop** met blok-versleping: sleep een titel → de hele
  onderliggende structuur verhuist mee
- **Undo / Redo** voor alles (cel, rij, blok, kolom-vullen, projectvelden)
- **Find** (Safari-stijl ⌘F slide-down) met live highlighting
- **Inspector-zijbalk** voor projectgegevens (toggle ⌘I)
- **Apple HIG-conform**: sheets i.p.v. modale dialogen, native
  modified-state in close-knop, named action-knoppen

## Tech stack

Python 3.11+ met **PyQt6**. Eén codebase voor Mac en Windows. De I/O-module
`app/c4y_io.py` is puur Python (`xml.etree.ElementTree`) en kan los van de
GUI gebruikt worden — handig voor scripts.

## Installeren en starten

### macOS — snelste manier

Dubbelklik op **`CalcMacApp.command`** in Finder. Bij de eerste start
maakt het script automatisch een virtuele omgeving aan en installeert
het de dependencies.

### Vanuit Terminal (Mac of Windows)

```bash
python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 -m app.main
```

### Echte `.app` bundel + `.c4y` koppelen aan de app

```bash
pip install py2app
python3 setup.py py2app
```

`dist/CalcMacApp.app` kan je naar `/Applications` slepen. `.c4y`-bestanden
zijn daarna te koppelen via Finder → Open With → CalcMacApp (Always Open
With). Zie `HANDLEIDING.md` voor details.

## Documentatie

- **`HANDLEIDING.md`** — beknopte handleiding voor gebruikers (sneltoetsen,
  bewerkingen, tips)
- **`c4y-writer/SKILL.md`** — XML-formaatspecificatie van `.c4y`
- **`ondersteunend/Handleiding Calc4You v66.pdf`** — originele
  Calc4You-handleiding (referentie)

## Modulestructuur

```
app/
├── main.py        Hoofdvenster, toolbar, menu, drag & drop
├── c4y_io.py      .c4y XML lezen/schrijven, NL-getalformaat,
│                  insert/delete/move_block/duplicate/renumber
├── calc.py        Rekenmotor (rij, titel-rollup, staart)
├── commands.py    QUndoCommand-subclasses (cel, rij, blok, kolom-vul)
└── find_bar.py    Safari-stijl slide-down zoekbalk
```

## Voorbeeldbestand

In `samples/` staat een `voorbeeld.c4y` om de app mee te leren kennen.
Regenereren vanuit `voorbeeld.json` kan met de meegeleverde skill:

```bash
python3 c4y-writer/scripts/schrijf_c4y.py \
  --invoer samples/voorbeeld.json \
  --uitvoer samples/voorbeeld.c4y
```

## Skill: c4y-writer

In `c4y-writer/` staat de SKILL die het `.c4y` XML-formaat documenteert en
een schrijver biedt vanuit gestructureerde JSON. De viewer/editor in `app/`
werkt rechtstreeks op de XML en hergebruikt dezelfde tag-volgorde zodat
opgeslagen bestanden compatibel blijven met de originele Calc4You-software.

## Compatibiliteit met Calc4You

Door onze app aangemaakte `.c4y` bestanden bevatten exact dezelfde
sub-tags in dezelfde volgorde als Calc4You schrijft. Berekende velden
(`<totaal>`, `<toturen>`, `<prijspe>` enz.) blijven leeg — Calc4You
berekent die zelf bij het openen. Een collega op Windows kan een door
ons opgeslagen bestand zonder problemen openen, bewerken en bewaren.
