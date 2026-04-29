# CalcMacApp — Beknopte handleiding

Een snelstart voor het werken met `.c4y` begrotingen in CalcMacApp.

## Snel starten op Mac

Twee manieren:

1. **Dubbelklik op `CalcMacApp.command`** in Finder. De eerste keer
   installeert het script automatisch de benodigde Python-pakketten.
2. **Vanuit Terminal**: `python3 -m app.main` (na `pip install -r
   requirements.txt`).

## In één minuut

1. Open een bestand: **⌘O**
2. Selecteer een cel, **typ** of **F2** om te bewerken
3. **⌅ Return** of **Tab** om naar de volgende cel/rij te gaan
4. **F9** voor een nieuwe rij eronder, **F11** om te verwijderen
5. **⌘B** om een totaalbedrag terug te rekenen naar prijs per eenheid
6. **⌘S** om te bewaren

## Overzicht van het venster

- **Toolbar** bovenaan: Open, Bewaren, Bewaren als, Ongedaan, Opnieuw,
  Rij toevoegen, Rij verwijderen
- **Tabel** (centraal): de volledige begroting met alle kolommen
- **Inspector rechts** (⌘I): projectgegevens (Nummer, Naam, Adres,
  Omschrijving)
- **Statusbalk onderaan**: begrotingstotaal van alle hoofdstukken (S=1)

## Sneltoetsen

### Bestand
| Combinatie | Actie |
|------------|-------|
| ⌘O | Openen |
| ⌘S | Bewaren |
| ⇧⌘S | Bewaren als |
| ⌘Q | Afsluiten |

### Bewerken
| Combinatie | Actie |
|------------|-------|
| ⌘Z / ⇧⌘Z | Ongedaan / Opnieuw |
| F9 / ⇧F9 | Rij toevoegen onder / boven |
| F11 | Rij verwijderen (met bevestiging bij data) |
| ⇧F4 | Rij dupliceren onder |
| F4 | Cel uit rij erboven kopiëren |
| ⌘B | Bruto invoeren (totaal → per eenheid) |
| ⇧⌘F | Kolom met waarde vullen |

### Navigatie
| Combinatie | Actie |
|------------|-------|
| Tab / ⇧Tab | Volgende / vorige cel |
| ⌅ Return | Volgende rij in dezelfde kolom (commit + omlaag) |
| ⇧⌅ Return | Hetzelfde als ↩ |
| F2 | Cel bewerken zonder overschrijven |
| typen | Direct beginnen te typen overschrijft cel |

### Hoofdstukken & weergave
| Combinatie | Actie |
|------------|-------|
| F8 | Hoofdstuk in/uitklappen |
| ⇧F8 | Alle hoofdstukken op dit niveau in/uitklappen |
| ⌘I | Inspector-zijbalk tonen / verbergen |
| Beeld → Kolommen | Kolommen tonen / verbergen via vinkjes |

### Zoeken
| Combinatie | Actie |
|------------|-------|
| ⌘F | Zoekbalk openen |
| ⌘G | Volgende match |
| ⇧⌘G | Vorige match |
| Esc | Zoekbalk sluiten |

## Cel-bewerking

- **Klik op een cel** → cel geselecteerd
- **Klik nog een keer** of **typ een teken** → bewerk-modus
- **F2** → bewerk-modus zonder de tekst te wissen
- **Tab** of **⌅** commit en navigeert (rechts of omlaag)
- **Esc** annuleert de bewerking

Berekende kolommen (Prijs/eenheid, Tot. uren, Tot. arbeid, Tot. materiaal,
Tot. materieel, Tot. onderaan., Regeltotaal) zijn altijd lichtgrijs en niet
bewerkbaar — die rekent de app zelf uit.

### Wat is wel/niet bewerkbaar per regeltype?

| Regeltype | Bewerkbare kolommen |
|-----------|---------------------|
| **Hoofdstuk / werksoort / locatie** (S = 1/2/3) | Alleen Code, S, Omschrijving |
| **Begrotingsregel** (S leeg, S, V, G, ?, X) | Alle invoervelden |
| **Staart** (`/`, `%`, `&`, `=`, `+`, `-`, `a`, `b`, `c`) | Code, S, Omschrijving, Hvh, Enh |
| **Berekende kolommen** | Nooit |

Niet-bewerkbare cellen op een titelrij zijn lichter gekleurd. Wijzigt
de S-code? Dan worden de bewerkbare velden direct opnieuw bepaald.

### Actieve cel zichtbaar

De cel waar je in staat heeft een **systemBlue rand** rondom — ook als de
hele rij geselecteerd is. Zo zie je altijd waar je intypt.

### Kolommen tonen / verbergen / **verplaatsen**

Drie plekken:

1. **Beeld → Kolommen** — submenu met een vinkje per kolom
2. **Rechtermuisknop op een kolomkop** → "Verberg deze kolom" of submenu
   "Kolommen…"
3. **Sleep een kolomkop links of rechts** om de volgorde aan te passen

Je instellingen (kolombreedtes, kolomvolgorde, welke kolommen verborgen
zijn, venstergrootte, Inspector aan/uit) worden bij het afsluiten
bewaard en weer hersteld als je de app opnieuw opent.

### Bruto invoeren (⌘B)

Als je een offerte van een onderaannemer hebt waarin een **totaalbedrag**
staat (bv. "Steiger 576 m² = € 5.616"), maar de tabel verwacht een prijs
per eenheid, gebruik dan **⌘B**:

1. Zorg dat de **hoeveelheid** op de regel klopt (576 in dit voorbeeld)
2. Druk **⌘B** of kies **Bewerken → Bruto invoeren…**
3. Vul "Totaal onderaan." in met `5616`
4. Onder het veld zie je live "→ € 9,75 per m²"
5. Klik **Toepassen** → de Onderaan.-kolom wordt op **9,75** gezet

Werkt voor alle vier kostensoorten (Arbeid, Materiaal, Materieel,
Onderaanneming). Lege velden worden niet aangeraakt. Eén ⌘Z draait alle
wijzigingen ineens terug.

### Begrotingstotalen onderaan

De statusbalk toont twee bedragen:

- **Bouwkosten**: som van alle hoofdstukken (S=1)
- **Eindtotaal**: het laatste `=` in de staart, dus inclusief BTW en
  alle staart-opslagen. Verschijnt alleen als er een staart is.

## Stuurcodes (S-kolom)

| Code | Type | Kleur |
|------|------|-------|
| `1` | Hoofdstuk | Donkerblauw, witte tekst |
| `2` | Werksoort | Lichtblauw |
| `3` | Locatie | Heel licht blauw |
| (leeg) | Begrotingsregel | Wit |
| `S` | Stelpost | Lichtgeel |
| `V` | Verrekenpost | Lichtoranje |
| `G` | Geschatte post | Lichtgroen |
| `?` | Aandachtpost | Lichtpaars |
| `X` | X-post (buiten directe kosten) | Oranje + cursief |

### Staart (na een `/`-rij)

| Code | Werking |
|------|---------|
| `/` | Start staart — toont som directe kosten |
| `%` | Procentuele opslag op lopend totaal |
| `&` | Opslag (vereenvoudigd: zoals %) |
| `=` | Tussentotaal (toont lopend totaal) |
| `+` / `-` | Handmatig bedrag erbij / eraf |
| `a` | BTW hoog (default 21 %, of vul percentage in Hvh) |
| `b` | BTW laag (default 9 %) |
| `c` | BTW verlegd (default 0 %) |
| `S`/`V`/`G`/`X` | Doorgetelde subtotalen van post-type |

## Drag & drop

Sleep een rij naar boven of beneden om hem te verplaatsen.

**Belangrijk:** als je een **titelrij (S=1/2/3)** sleept, gaat de hele
onderliggende structuur (alle child-rijen tot de volgende titel van gelijk
of hoger niveau) automatisch mee. Eén ⌘Z herstelt het hele blok.

## Kolom met waarde vullen

Twee manieren:

1. **Menu Bewerken → Kolom vullen met waarde…** (⇧⌘F)
2. **Rechtermuisklik op een kolomkop** → "Vul kolom 'Uurloon' met waarde…"

In de dialog kies je de kolom, vult een waarde, en kiest het bereik:
*alle rijen* of *alleen geselecteerde rijen*. Eén ⌘Z draait alle gewijzigde
cellen tegelijk terug.

Handig voor:
- **Uurloon** in één keer instellen op alle regels
- **Factor** uniform op 25 % zetten
- **Code4** (bestek/offerte) overal "OHD 03" maken

## Inspector-zijbalk (⌘I)

Rechts van de tabel staan de projectgegevens (Nummer, Naam, Adres,
Omschrijving). Sluit hem als je meer ruimte wil voor de tabel — de state
wordt onthouden tussen sessies.

## Zoeken (⌘F)

De zoekbalk schuift uit boven de tabel:

- **Live**: tijdens het typen worden matchende cellen geel gemarkeerd
- **Pijltjes** of **⌘G/⇧⌘G** om door de matches te navigeren
- **Esc** sluit de balk en haalt de markering weg

Doorzoekt alle XML-velden van begrotingsregels (niet de berekende kolommen).

## Compatibiliteit

Bestanden bewaard met CalcMacApp openen 1-op-1 in de originele
Calc4You-software op Windows. Je collega kan dezelfde `.c4y` bewerken,
bewaren en weer in CalcMacApp openen — geen formaat-verlies.

## Probleemoplossing

**"Reference to invalid character number" bij openen**
> Het bestand bevat onzichtbare stuurcodes uit Word/RTF. CalcMacApp
> repareert dit automatisch door ongeldige tekenverwijzingen te strippen.
> Bewaar het bestand opnieuw met ⌘S.

**Berekende totalen kloppen niet**
> Controleer de Factor-kolom. Een lege Factor wordt als 0 % beschouwd
> (geen opslag). Vul 25 in voor een opslag van 25 % over de hele regel.

**Drag & drop pakt te veel rijen**
> Als je per ongeluk een titelrij oppakt, sleept de hele subboom mee. Dat
> is bedoeld. Gebruik ⌘Z om het terug te draaien.

**Bestand sluit met onopgeslagen wijzigingen**
> Je krijgt een sheet met "Bewaren / Niet bewaren / Annuleren". De
> close-knop toont een puntje wanneer er wijzigingen zijn.
