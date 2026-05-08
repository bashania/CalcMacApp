# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

CalcMacApp is een PyQt6-applicatie (Mac-first, ook Windows) voor het bekijken
en bewerken van Calc4You-`.c4y` begrotingen. Bestanden moeten **uitwisselbaar
blijven** met de originele Calc4You-software op Windows.

## Werken in deze repo

### Stream-timeout-preventie (eigen richtlijn)
1. Schrijf bestanden in stukken van maximaal 150 regels per tool call.
2. Gebruik append/edit-passes voor langere bestanden — nooit alles in één keer.
3. Bevestig na elke stap dat het gelukt is voor je verdergaat.
4. Start een nieuwe sessie als het gesprek langer dan 20 tool calls duurt.

### Branch-policy
Een nieuwe taak begint op een **nieuwe branch** vanuit `main`. Niet doorwerken
op een eerder gemerged branch.

## Commands

```bash
# App starten (na pip install -r requirements.txt in venv)
python3 -m app.main

# Snel starten op Mac via launcher (maakt zo nodig venv aan)
./CalcMacApp.command

# Tests
python3 -m pytest tests/ -q
python3 -m pytest tests/test_calc.py::test_kophoeveelheid_nested -v   # losse test

# Syntax-check zonder GUI
python3 -m py_compile app/*.py tests/*.py runapp.py setup.py

# .app-bundel bouwen (alleen op macOS)
pip install py2app
python3 setup.py py2app

# App-icoon (.icns) bouwen vanuit SVG
./make_icon.sh

# Sample .c4y regenereren vanuit JSON via de meegeleverde skill
python3 c4y-writer/scripts/schrijf_c4y.py \
    --invoer samples/voorbeeld.json --uitvoer samples/voorbeeld.c4y
```

## Architectuur

### Lagen

```
app/
├── c4y_io.py       Documentlaag — pure stdlib, los van GUI bruikbaar
├── calc.py         Rekenmotor — pure stdlib, geen Qt-imports
├── validations.py  Logboek-regels — pure stdlib
├── commands.py     QUndoCommand-subclasses (Qt, geen GUI)
├── find_bar.py     Find-bar widget
└── main.py         Hoofdvenster, delegates, handlers, app-entry
```

`c4y_io.py`, `calc.py` en `validations.py` zijn **bewust pure Python**: alle
tests draaien zonder Qt-display, en de modules zijn los herbruikbaar.

### Documentmodel — `C4YDocument` (`app/c4y_io.py`)

- Wraps een `xml.etree.ElementTree.ElementTree`. Eén document = één tree.
- `BEGROTING_TAG_ORDER` is **leidend voor compatibiliteit**: nieuwe rijen
  krijgen exact dezelfde sub-tags in dezelfde volgorde als Calc4You schrijft.
  De referentie staat in `c4y-writer/scripts/schrijf_c4y.py`. Wijken hiervan
  af breekt de uitwisselbaarheid met de originele Calc4You.
- `_clean_xml()` strip ongeldige tekenverwij­zingen (zoals `&#x0;`) bij
  laden — Calc4You-bestanden uit Word/RTF kunnen die bevatten.
- Structurele helpers: `insert_row`, `delete_row`, `restore_row`,
  `move_block`, `duplicate_row`, `renumber`, `block_size`,
  `children_indices`. **Berekende velden (`<totaal>`, `<toturen>`,
  `<prijspe>`, …) blijven leeg bij opslaan** — Calc4You vult die zelf
  bij het openen. Dit is waarom de XML compatibel blijft.

### Rekenmotor — `app/calc.py`

Drie fasen in `recompute(rows)`:
1. **Per-regel**: `prijspe = (arb·uurloon + maa + mee + ond) × (1 + factor/100)`,
   plus `tot_arb`/`tot_maa`/`tot_mee`/`tot_ond`. **Factor wordt over de hele
   regel toegepast**, niet alleen op arbeid.
2. **Titel-rollup** (S=1/2/3) — **bottom-up**, zodat geneste kop-hoeveelheden
   correct doorvermenigvuldigen. Een titel met `hvh > 1` is een
   "kop­hoeveelheid": de som van onderliggende regels wordt × N. Skipt
   descendants van child-titels om dubbeltelling te voorkomen.
3. **Staart** (rijen op/na `/`) — running total met BTW-codes (a/b/c),
   procent-opslagen (%/&), `=`-tussentotaal, X-post die optelt bij
   directe kosten in de staart.

### UI — `app/main.py` (~2800 regels)

- `MainWindow` met `QUndoStack` als bron van waarheid voor dirty-state
  (`isClean()` ↔ `setWindowModified()`).
- `DnDTableWidget` (subclass `QTableWidget`): blok-bewuste drag & drop
  (titelrij sleept descendants mee), klik op disclosure-driehoekje voor
  in/uitklap, Delete/Backspace voor cel-wis. Drag-mode is `DragDrop`
  (niet `InternalMove`) en de daadwerkelijke verplaatsing wordt
  **gedeferred met `QTimer.singleShot(0)`** zodat Qt's drop-event
  volledig is afgerond voordat we de tabel hervullen — anders crasht de
  app.
- `CellFocusDelegate`: tekent een witte cel met dikke macOS-blauwe rand
  voor de actieve cel + gekleurde dot in de Nr-kolom voor logboek-issues.
  Levert ook `createEditor()` voor autocomplete (Omschrijving) en
  inline validatie (numerieke kolommen).
- `_ReturnNextRowFilter`: app-event-filter voor Numbers-stijl navigatie
  tijdens cel-edit (Return = volgende rij; pijltjes = navigeren mét
  commit). Wordt geïnstalleerd op `QApplication.instance()` zodat ook
  cel-editors de toetsen niet "opslokken".
- `_CalcApplication`: vangt `QEvent.Type.FileOpen` op (Finder dubbelklik
  op een geassocieerd .c4y) en routeert naar `MainWindow.load_path()`.

### Undo/Redo — `app/commands.py`

Alle mutaties gaan via `QUndoCommand`-subclasses zodat één Ctrl/Cmd-Z het
correct terugdraait. `MainWindow` is de "host" met de attributen `doc` en
`refresh()`/`select_row()`. Voor bulk-acties wordt
`undo_stack.beginMacro()/endMacro()` gebruikt.

### Bewerkbaarheid per regeltype

`_editable_tags_for_s_code()` bepaalt per S-code welke kolommen bewerkbaar
zijn (bv. titels: alleen Code/S/Omschrijving + Hoeveelheid/Eenheid voor
kophoeveelheid; staart: Code/S/Oms/Hvh/Enh; berekende kolommen nooit). De
`_apply_row_style()` zet hierop de `Qt.ItemFlag.ItemIsEditable`-vlag en
een lichte "disabled"-tint.

### Persistente instellingen — `QSettings('CalcMacApp', 'CalcMacApp')`

- `window/geometry` + `window/state` (incl. dock-widgets)
- `table/header` (kolombreedtes, volgorde, verborgen kolommen)
- `window/inspectorVisible`
- `recent/paths` (LRU, JSON-list, max 10)
- `prefs/uurloon`, `prefs/productie`, `prefs/btw` (Voorkeuren-venster)

## Compatibiliteits-randvoorwaarde

Door onze app opgeslagen `.c4y` bestanden moeten ongewijzigd openen in
Calc4You op Windows. Concreet:

- **Tag-volgorde** in `<begroting>` blokken volgt `BEGROTING_TAG_ORDER`.
- **Berekende velden blijven leeg** bij save — Calc4You berekent die zelf.
- **`<nr>` is 5-cijferig zero-padded** (`00001`, …) via `renumber()`.
- **NL-getalformaat** via `format_nl()` (`1.234,56`).
- **XML-declaratie** `<?xml version="1.0" standalone="yes"?>` blijft de
  eerste regel.
- **UTF-8** met fallback naar latin-1 bij oudere Windows-bestanden.

## Ondersteunende referentie

- `c4y-writer/SKILL.md` — XML-formaat van `.c4y`, S-codes (1/2/3 titels,
  S/V/G/?/X stelposten, /%&=+-/abc staart) en veldmapping.
- `c4y-writer/scripts/schrijf_c4y.py` — referentie voor tag-volgorde en
  default-waarden voor nieuwe rijen.
- `ondersteunend/Handleiding Calc4You v66.pdf` — originele Calc4You-handleiding.
- `HANDLEIDING.md` — beknopte gebruikershandleiding (sneltoetsen, flows).
