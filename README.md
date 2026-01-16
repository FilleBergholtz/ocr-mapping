# OCR PDF - Fakturaextraktion

En Windows desktop-applikation byggd med Python och PySide6 (Qt 6) för automatisk extraktion av strukturerad data från fakturor i PDF-format.

## Funktioner

- **Automatisk Klustering**: Grupperar liknande PDF:er med maskininlärning (TF-IDF + Agglomerative Clustering)
- **Smart Referensval**: Väljer automatiskt den mest kompletta PDF:en i varje kluster som referens
- **Flexibel Mappning**: 
  - Mappa fält med värde-rubrik-metod
  - Mappa tabeller med kolumn- och radidentifiering
  - Stöd för återkommande och unika värden
- **OCR-stöd**: Hanterar både textbaserade PDF:er och skannade dokument via Tesseract OCR
- **Granskning och Korrigering**: Granska extraherad data och korrigera fel med automatisk matchning av liknande dokument
- **Export**: Exportera data till Excel (.xlsx), CSV (.csv) eller JSON (.json)

## Installation

**Se [SETUP.md](SETUP.md) för detaljerade installationsinstruktioner.**

### Snabbstart

1. **Förutsättningar:**
   - Python 3.8 eller senare
   - Tesseract OCR (se [SETUP.md](SETUP.md) för installationsinstruktioner)
   - Poppler (för PDF-till-bild konvertering, se [SETUP.md](SETUP.md))

2. **Installera Python-dependencies:**
```bash
pip install -r requirements.txt
```

3. **Kör applikationen:**
```bash
python main.py
```

**För fullständig installationsguide med felsökning, se [SETUP.md](SETUP.md).**

## Användning

### Steg 1: Ladda upp PDF:er

1. Öppna applikationen
2. Gå till fliken "📄 Document Types"
3. Klicka på "➕ Lägg till PDF:er"
4. Välj PDF-filer från din dator
5. Klicka "🔍 Skanna" för att börja analysera dokumenten

Systemet kommer att:
- Extrahera text från varje PDF (använder OCR om nödvändigt)
- Skapa ett "fingeravtryck" för varje PDF
- Gruppera PDF:erna i kluster baserat på likhet

### Steg 2: Mappa Fält

1. Dubbelklicka på ett kluster i "Document Types"-fliken
2. Systemet öppnar automatiskt "Mapping"-fliken med referens-PDF:en
3. För fält (inte tabeller):
   - Välj ett fält i listan
   - Klicka "✏️ Markera Värde"
   - **Markera VÄRDET** (inte rubriken) i PDF:en
   - Bekräfta eller markera rubriken
   - Välj om värdet är återkommande eller unikt
4. För tabeller:
   - Klicka "📍 Mappa Tabell"
   - Markera tabellområdet i PDF:en
   - Systemet identifierar automatiskt kolumner och rader

### Steg 3: Testa och Applicera

1. Klicka "🧪 Testa Extraktion" för att verifiera mappningen
2. Om resultatet ser bra ut, klicka "🚀 Mappa Alla i Klustret"
3. Systemet applicerar mallen på alla PDF:er i klustret

### Steg 4: Granska och Korrigera

1. Gå till "👁️ Review"-fliken
2. Granska extraherade data
3. Om fel hittas:
   - Dubbelklicka på dokumentet eller klicka "🔧 Korrigera"
   - Korrigera mappningen i "Mapping"-fliken
   - Systemet hittar automatiskt liknande PDF:er och frågar om rematchning

### Steg 5: Exportera

1. Gå till "📦 Extract & Export"-fliken
2. Välj kluster att exportera
3. Välj format (Excel, CSV, JSON)
4. Klicka "Exportera"

## Projektstruktur

```
OCR MAPPNING/
├── main.py                 # Huvudentrypunkt
├── requirements.txt        # Python-dependencies
├── src/
│   ├── main_window.py      # Huvudfönster
│   ├── core/               # Kärnmoduler
│   │   ├── document_manager.py    # Hanterar PDF-dokument
│   │   ├── clustering_engine.py   # Klustering med ML
│   │   ├── template_manager.py    # Mappningsmallar
│   │   ├── pdf_processor.py       # PDF-läsning och OCR
│   │   └── extraction_engine.py   # Dataextraktion
│   └── tabs/               # GUI-flikar
│       ├── document_types_tab.py  # PDF-uppladdning och klustering
│       ├── mapping_tab.py         # Fält- och tabellmappning
│       ├── review_tab.py          # Granskning och korrigering
│       └── export_tab.py           # Export-funktionalitet
├── data/                   # Sparad dokumentdata (skapas automatiskt)
└── templates/              # Sparade mappningsmallar (skapas automatiskt)
```

## Tekniska Detaljer

### Klustering
- **Metod**: Agglomerative Clustering med TF-IDF vektorisering
- **Likhetsmetod**: Cosine similarity
- **Adaptivt**: Antal kluster anpassas automatiskt baserat på dokumentmängd

### OCR
- **Tesseract OCR**: Används när PDF:er saknar text-lager
- **Multi-språk**: Stöd för svenska och engelska
- **Förbehandling**: Grayscale-konvertering för bättre resultat

### Koordinathantering
- **Normaliserade koordinater**: 0.0-1.0 (oavsett PDF-storlek)
- **Koordinatsystem**: Hanterar både PDF-koordinater (points) och bild-koordinater (pixels)

## Tips och Best Practices

1. **Börja med den mest kompletta PDF:en** - Systemet väljer den automatiskt
2. **Mappa alla viktiga fält först** - Fakturanummer, Datum, Totalt är viktigast
3. **För fält: Markera värdet först, sedan rubriken** - Detta säkerställer korrekt mappning
4. **Testa innan "Mappa Alla"** - Använd "Testa Extraktion" för att verifiera
5. **Granska alltid resultaten** - Särskilt första gången med ett nytt kluster
6. **Spara mallar ofta** - Klicka "💾 Spara Mall" för att spara framsteg

## Felsökning

### Tesseract hittas inte
- Kontrollera att Tesseract är installerat
- Om Tesseract är installerad på en annan plats, uppdatera `PDFProcessor.__init__()` med rätt sökväg

### PDF:er kan inte läsas
- Kontrollera att PDF:erna inte är lösenordsskyddade
- Försök med OCR-läge om PDF:en är skannad

### Klustering ger för många/få kluster
- Detta är normalt - systemet anpassar sig automatiskt
- Du kan manuellt justera kluster efter mappning

## Roadmap

Se [ROADMAP.md](ROADMAP.md) för detaljerad utvecklingsplan och framtida funktioner.

**Kommande funktioner:**
- Förbättrad tabellmappning med avancerad kolumnidentifiering
- AI-assisterad fältdetektering
- Mallbibliotek för återanvändning
- API för automation
- Cloud-integration

## Licens

MIT

## Support

För frågor eller problem, skapa ett issue i projektets repository.

## Relaterade Dokument

- [SETUP.md](SETUP.md) - Detaljerad installationsguide
- [REQUIREMENTS.md](REQUIREMENTS.md) - Komplett requirements-specifikation
- [ROADMAP.md](ROADMAP.md) - Utvecklingsroadmap och framtida funktioner
