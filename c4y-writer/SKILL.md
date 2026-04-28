---
name: c4y-writer
description: >
  Genereer een geldig Calc4You-bestand (.c4y) vanuit gestructureerde
  begrotingsdata. Gebruik deze skill altijd wanneer een gebruiker een
  begroting wil wegschrijven naar Calc4You, een .c4y bestand wil maken
  of aanmaken, of hoeveelheden en normen wil omzetten naar een
  calculatiebestand. Triggers: c4y, Calc4You, begroting aanmaken,
  wegschrijven naar Calc4You, begroting genereren, calculatiebestand maken.
---

# C4Y-Writer

Deze skill genereert een geldig `.c4y` bestand voor het calculatieprogramma
Calc4You. Ze vertaalt gestructureerde begrotingsdata (locaties, onderdelen,
hoeveelheden, normen) naar de juiste XML-structuur. Berekende velden worden
leeg gelaten - Calc4You berekent deze zelf bij het openen van het bestand.

## Wanneer gebruiken

Gebruik deze skill wanneer:
- Een gebruiker een begroting wil opslaan als Calc4You-bestand
- Hoeveelheden uit een meetstaat (bv. via meetstaat-lezer skill) omgezet
  moeten worden naar een .c4y bestand
- Een bestaand .c4y bestand opnieuw gegenereerd of bijgewerkt moet worden

## Bestandsformaat: .c4y

Een `.c4y` bestand is gewone UTF-8 XML met de volgende structuur:

```xml
<?xml version="1.0" standalone="yes"?>
<calc4you>
  <alginfo>...</alginfo>
  <begroting>...</begroting>
  <begroting>...</begroting>
  ...
  <versie>...</versie>
  <toelichting>...</toelichting>
  <offerte>...</offerte>
</calc4you>
```

## S-codes (stuurcodes)

Elke `<begroting>` heeft een `<s>` veld dat de rol in de hiërarchie bepaalt.

### Standaard projectstructuur (vier niveaus)

```
S=1  Werkzaamheden                          ← hoofdstuk
S=2    Buitenschilderwerk                   ← werksoort
S=3      Voorgevel                          ← locatie
(leeg)     Hout - Kozijn  130m1  0,14       ← begrotingsregel
S          Aankoop tegelwerk (materiaal)    ← stelpost tussen regels
S=3      Achtergevel
(leeg)     Hout - Kozijn   80m1  0,14
S=2    Metsel- en voegwerk
S=2    Loodgieterswerk

S=1  Algemeen
S=2    Bouwplaatskosten
(leeg)   Steiger voorkant 576m2
S=2    Bereikbaarheidskosten

S=1  Stelposten                             ← aparte sectie voor vaste stelposten
S=2    Vergunningen
S        Omgevingsvergunning
S=2    Houtrotherstel
V        Houtrotherstel verrekenbaar
```

| S-code | Type | Gebruik |
|--------|------|---------|
| `1` | Titel - Hoofdstuk | Bovenste niveau (Werkzaamheden, Algemeen, Stelposten) |
| `2` | Titel - Werksoort | Buitenschilderwerk, Bouwplaatskosten etc. |
| `3` | Titel - Locatie | Voorgevel, Achtergevel, per gevel of onderdeel |
| `` (leeg) | Begrotingsregel | Kostenregel met hvh, arb, maa of ond |
| `G` | Begrotingsregel - Geschat | Schatpost |
| `S` | Begrotingsregel - Stelpost | Stelpost |
| `V` | Begrotingsregel - Verrekenpost | Verrekenpost |
| `?` | Begrotingsregel - Vraagpost | Nader te bepalen |

**Structuurregels:**
- S=1, S=2 en S=3 zijn **uitsluitend titels**: `hvh=1`, `eenheid` leeg,
  NOOIT kosten, normen of onderaannemingsbedragen.
- **Begrotingsregels hebben S leeg** (of G/S/V/?). Hier staan hoeveelheid,
  eenheid en alle kosten per eenheid (arb, maa, ond).
- S=3 is optioneel: gebruik het als een werksoort meerdere locaties heeft
  (bv. Buitenschilderwerk > Voorgevel / Achtergevel). Is er maar één locatie,
  dan gaan de begrotingsregels direct onder S=2.
- Stelposten (S/V/G/?) zijn **begrotingsregels**, geen titels. Ze kunnen
  overal in de begroting staan — ook gemengd tussen gewone kostenregels.
  Gebruik een aparte S=1 / S=2 sectie (bv. "Stelposten") alleen voor posten
  die los van een werksoort staan, zoals vergunningen of houtrotherstel.
- Nooit kosten op een titelregel, ook niet als de omschrijving een
  hoeveelheid suggereert (bv. "Steiger voorkant 576m2").

**S=2 organisatieprincipe — adres vs. werksoort:**
- **Één adres**: organiseer S=2 per werksoort (bv. "Buitenschilderwerk hout",
  "Metselwerk", "Loodgieterswerk").
- **Meerdere adressen of gebouwen**: organiseer S=2 per adres/gebouw
  (bv. "Voorstraat 8-12", "Minderbroerstraat 33"). De werksoort is dan
  niet langer zichtbaar op S=2 niveau, maar herkenbaar via de ondergrond-prefix
  in de `oms` van de begrotingsregel ("Hout - ...", "Metaal - ...", "Steen - ...").
- **Metaalwerk, pleister- en sauswerk als schilderonderdelen** horen altijd
  bij de locatie (S=3) waar ze fysiek zitten — nooit als aparte S=2 werksoort.
  Dit geldt wanneer deze werkzaamheden onderdeel zijn van het schilderwerk
  (= het schilderen of behandelen van metalen of stenen onderdelen). De
  ondergrond-prefix in `oms` maakt het onderscheid al zichtbaar binnen de locatie.

## Veldmapping

| XML-veld | Betekenis | Invullen bij |
|----------|-----------|-------------|
| `<nr>` | Volgnummer (00001, 00002, ...) | Altijd |
| `<code>` | Positiecode (bv. 46.01.3) | Altijd |
| `<s>` | Stuurcode | Altijd |
| `<oms>` | Omschrijving van de werkzaamheden | Altijd - XML-escape < en >! Nooit naam onderaannemer hier |
| `<hvh>` | Hoeveelheid | Begrotingsregel: werkelijke hvh; titel S=1/2/3: 1 |
| `<enh>` | Eenheid (m1, m2, st) | Begrotingsregel: eenheid; titel: leeg |
| `<arb>` | Norm in uren per eenheid | Begrotingsregel met eigen arbeid |
| `<maa>` | Materiaalprijs per eenheid (euro) | Begrotingsregel met materiaal |
| `<ond>` | Onderaanneming per eenheid (euro) | Begrotingsregel met onderaannemer; naam NOOIT in oms |
| `<code1>` | Naam onderaannemer | Altijd invullen als ond > 0 |
| `<code2>` | Vrij veld | Optioneel |
| `<code3>` | Vrij veld | Optioneel |
| `<code4>` | Bestek- of offertenummer | Bv. "OHD 03" of "Offerte 127" |
| `<uurloon>` | Uurloon (default 45) | Begrotingsregel met arb |
| `<productie>` | Factor/opslag % (default 25) | Begrotingsregel met arb |
| `<toturen>` t/m `<althv>` | Berekende velden | **Leeg laten - Calc4You berekent deze zelf** |

## Onderaanneming - verplichte werkwijze

Bij ingehuurde partijen (steiger, specialistisch werk e.d.):

- `<oms>`: omschrijving van de werkzaamheden, letterlijk overgenomen uit de
  offerte van de onderaannemer. **NOOIT de naam van de onderaannemer hier.**
- `<code1>`: naam van de onderaannemer (bv. "DMB Steigerverhuur B.V.")
- `<code4>`: offertenummer (bv. "Offerte 127")
- `<ond>`: prijs per eenheid uit de offerte

**Voorbeeld:** offerte vermeldt "Montage/Demontage 576 m2 a 9,75"

```
oms   = "Montage/Demontage"
code1 = "DMB Steigerverhuur B.V."
code4 = "Offerte 127"
hvh   = 576, enh = "m2", ond = 9.75
```

## Normbibliotheek

De Everts normbibliotheek staat in:
```
/tmp/skills/c4y-writer/references/normen.json
```

880 normen voor hout (OHD/OHT/OHV), kunststof (OKD), metaal (OMA/OMS/OMV),
steen (OSD) en overige onderhoudswerkzaamheden (HR).

**Gebruik altijd de bibliotheek** voor arb en maa — nooit zelf inschatten.

### Norm opzoeken

```bash
# Exacte code
python3 /tmp/skills/c4y-writer/scripts/zoek_norm.py --code OHD03-khB

# Zoek op omschrijving binnen systeem
python3 /tmp/skills/c4y-writer/scripts/zoek_norm.py --zoek "kozijn" --systeem OHD03

# Alle normen voor een systeem
python3 /tmp/skills/c4y-writer/scripts/zoek_norm.py --lijst OHD03
```

### Veelgebruikte codes (OHD 03 buitenschilderwerk)

| Onderdeel | Code | Enh | Arb | Maa |
|-----------|------|-----|-----|-----|
| Kozijn 10-20 cm | OHD03-khB | m1 | 0,14 | 1,81 |
| Kozijn normaal profiel | OHD03-khn-m¹ | m1 | 0,17 | 1,64 |
| Raam hout | OHD03-rh-m¹ | m1 | 0,12 | 1,30 |
| Deur vlak | OHD03-dhv-m² | m2 | 0,51 | 10,13 |
| Deur 1 ruit | OHD03-dhB | m2 | 0,52 | 9,07 |
| Deur meerdere ruiten | OHD03-dhE | m2 | 0,91 | 9,07 |
| Paneel >30 cm | OHD03-phD | m2 | 0,33 | 10,02 |
| Boeiboord hout | OHD03-ghF | m1 | 0,16 | 1,77 |
| Goot/lijstwerk boeiboord | OHD03-glb-m² | m2 | 0,86 | 10,58 |
| Leuning staal | OMS03-stleu-m¹ | m1 | 0,43 | 4,60 |

### Werkwijze bij een meetstaat-import

1. Stel het te gebruiken systeem vast op basis van het bestek (bv. OHD 03)
2. Zoek per onderdeel de bijbehorende normcode op in de bibliotheek
3. Gebruik code4 in de begroting om het systeem te vermelden (bv. "OHD 03")
4. Vraag de gebruiker om bevestiging als een onderdeel niet eenduidig te
   koppelen is aan een normcode

## XML-escaping - kritisch

Omschrijvingen (`<oms>`) mogen geen ruwe `<` of `>` bevatten.
Dit veroorzaakt een parsefout in Calc4You ("Naam kan niet beginnen met...").

Altijd escapen in oms-velden:
- `&` -> `&amp;`
- `<` -> `&lt;`
- `>` -> `&gt;`

## Nederlands getalformaat

Calc4You verwacht komma als decimaalscheider en punt als duizendtalscheider:
- `1234.56` -> `1.234,56`
- `0.41` -> `0,41`

## Werkwijze - altijd preview tonen voor wegschrijven

Genereer het bestand **nooit direct**. Toon eerst een overzicht en wacht op goedkeuring.

### Stap 1 - Toon preview als tekst-tabel

Presenteer de geplande begrotingsstructuur als een overzichtelijke tabel in de chat.
Gebruik inspringing om de hierarchie (S=1 -> S=2 -> S=3) zichtbaar te maken,
en toon per noemer de hoeveelheid, eenheid en berekend totaal:

```
Omschrijving                              Hvh     Enh    Arb    Maa      Totaal
------------------------------------------------------------------------------
46  Schilderwerk hout
  46.01  Gevel Entree Zijde
    46.01.1  Kozijn                      130,40   m1    0,14   1,81    EUR 1.234
    46.01.2  Raam                         51,20   m1    0,14   1,30    EUR   567
  46.02  Gevel Speelplein Zijde
    46.02.1  Boeiboord >30               24,18   m2    0,41  10,58    EUR 1.890
------------------------------------------------------------------------------
Totaal arbeid:     EUR  22.618
Totaal materiaal:  EUR   8.754
Totaal excl. BTW:  EUR  31.372
```

Vermeld ook het uitvoerpad waar het bestand naartoe zou worden geschreven.

### Stap 2 - Vraag bevestiging

Sluit de preview af met een korte vraag, bijvoorbeeld:

> "Klopt deze structuur? Dan schrijf ik het bestand weg naar [pad]."

Wacht op goedkeuring van de gebruiker. De gebruiker kan ook correcties aangeven
(bv. een onderdeel toevoegen, hoeveelheid aanpassen) - verwerk die eerst en toon
een nieuwe preview als de wijziging substantieel is.

### Stap 3 - Genereer het .c4y bestand

Gebruik het meegeleverde script pas na bevestiging.

---

## Script gebruiken

Het meegeleverde script verzorgt alle opmaak, berekeningen en XML-escaping:

```
/tmp/skills/c4y-writer/scripts/schrijf_c4y.py
```

Invoer: JSON-bestand met projectinfo + begroting-regels + normen.
Uitvoer: `.c4y` bestand.

```bash
python3 /tmp/skills/c4y-writer/scripts/schrijf_c4y.py \
  --invoer <pad naar invoer.json> \
  --uitvoer <pad naar output.c4y>
```

## Invoer JSON-formaat

```json
{
  "project": {
    "nummer": "20261.00260",
    "naam": "IKC de Triangel",
    "adres": "Vlasakker 33, Zoetermeer",
    "omschrijving": "Buitenschilderwerk"
  },
  "uurloon": 45,
  "factor": 25,
  "hoofdstukken": [
    {
      "code": "46",
      "s": "1",
      "oms": "Schilderwerk hout",
      "segmenten": [
        {
          "code": "46.01",
          "s": "2",
          "oms": "Gevel Entree Zijde",
          "noemers": [
            {
              "code": "46.01.1",
              "oms": "Hout - Kozijn",
              "hvh": 130.40,
              "enh": "m1",
              "arb": 0.14,
              "maa": 1.81,
              "code4": "OHD 03"
            }
          ]
        },
        {
          "code": "46.02",
          "s": "2",
          "oms": "Steiger voorkant 576m2",
          "noemers": [
            {
              "code": "46.02.1",
              "oms": "Montage/Demontage",
              "hvh": 576.00,
              "enh": "m2",
              "arb": 0,
              "maa": 0,
              "ond": 9.75,
              "code1": "DMB Steigerverhuur B.V.",
              "code4": "Offerte 127"
            }
          ]
        }
      ]
    }
  ]
}
```

## Koppeling met meetstaat-lezer

Bij import vanuit de meetstaat-lezer skill bevat elk item al een `oms` veld
met de ondergrond als prefix (bv. `"Hout - Kozijn"`). Gebruik dit veld direct
als omschrijving op de begrotingsregel - niet handmatig samenstellen.

**De ondergrond begint altijd met een hoofdletter.** Controleer dit altijd,
ook als de meetstaat de ondergrond in kleine letters aanlevert. Dus `Hout - Kozijn`
en `Steen - Pleisterwerk`, nooit `hout - kozijn` of `steen - pleisterwerk`.

```
meetstaat-item.oms  →  noemer.oms   (bv. "Hout - Kozijn")
meetstaat-item.begroot  →  noemer.hvh
meetstaat-item.eenheid  →  noemer.enh
```

## alginfo - projectkoptekst

De `<alginfo>` sectie bevat projectgegevens. Totaalvelden (arbeid, materiaal,
totaal) leeg laten — Calc4You berekent en vult deze zelf in bij openen.

```xml
<alginfo>
  <type>E</type>
  <kop>20261.00260</kop>   <!-- projectnummer -->
  <r1>Projectnaam</r1>
  <r2>Adres</r2>
  <r4>Omschrijving</r4>
  <arbeid />               <!-- leeg laten -->
  <materiaal />            <!-- leeg laten -->
  <totaal />               <!-- leeg laten -->
  <ul>45,00</ul>           <!-- uurloon wel invullen -->
</alginfo>
```
