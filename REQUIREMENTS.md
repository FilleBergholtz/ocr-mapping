# Requirements Specification

## Översikt

Detta dokument specificerar alla krav och dependencies för OCR PDF-applikationen.

## Systemkrav

### Operativsystem
- **Windows 10** eller senare (primärt målplattform)
- Alternativt: Linux eller macOS (kräver anpassningar)

### Python
- **Python 3.8** eller senare
- Rekommenderat: Python 3.10 eller 3.11

### Minne och Lagring
- **Minst 4 GB RAM** (rekommenderas 8 GB för större PDF-filer)
- **Minst 500 MB** ledigt diskutrymme för installation

## Python Dependencies

### Kärndependencies (requirements.txt)

#### GUI Framework
- **PySide6** (>=6.6.0, <7.0.0)
  - Qt 6-bindningar för Python
  - Används för: Alla GUI-komponenter, huvudfönster, flikar

#### PDF Processing
- **PyPDF2** (>=3.0.0, <4.0.0)
  - PDF-läsning och textextraktion
  - Används för: Extrahera text från textbaserade PDF:er

- **pdf2image** (>=1.16.3, <2.0.0)
  - Konverterar PDF-sidor till bilder
  - Används för: OCR-förbehandling, PDF-visualisering
  - **Kräver Poppler** (se Systemverktyg nedan)

#### OCR (Optical Character Recognition)
- **pytesseract** (>=0.3.10, <1.0.0)
  - Python-wrapper för Tesseract OCR
  - Används för: Textextraktion från skannade PDF:er
  - **Kräver Tesseract OCR** (se Systemverktyg nedan)

#### Image Processing
- **Pillow** (>=10.0.0, <11.0.0)
  - Bildmanipulation och förbehandling
  - Används för: OCR-förbehandling, bildhantering

#### Machine Learning & Data Processing
- **numpy** (>=1.24.0, <2.0.0)
  - Numeriska beräkningar
  - Används för: Bildförbehandling, array-operationer

- **scikit-learn** (>=1.3.0, <2.0.0)
  - Maskininlärningsbibliotek
  - Används för: TF-IDF vektorisering, Agglomerative Clustering

- **scipy** (>=1.11.0, <2.0.0)
  - Vetenskapliga beräkningar
  - Används för: Stöd för scikit-learn

#### Data Export
- **pandas** (>=2.0.0, <3.0.0)
  - Dataanalys och manipulation
  - Används för: Strukturering av data för export

- **openpyxl** (>=3.1.0, <4.0.0)
  - Excel-filhantering
  - Används för: Export till .xlsx-format

### Utvecklingsdependencies (requirements-dev.txt)

Dessa är valfria och används endast för utveckling:

- **black** (>=23.0.0) - Kodformatering
- **flake8** (>=6.0.0) - Linting
- **mypy** (>=1.5.0) - Typkontroll
- **pytest** (>=7.4.0) - Testning
- **pytest-qt** (>=4.2.0) - Qt-specifik testning

## Systemverktyg (Externa Dependencies)

Dessa måste installeras separat och är inte Python-paket:

### Tesseract OCR
**Krävs för OCR-funktionalitet**

- **Version**: 5.x eller senare
- **Windows**: https://github.com/UB-Mannheim/tesseract/wiki
- **Standard installationssökväg**: `C:\Program Files\Tesseract-OCR\tesseract.exe`
- **Språkpaket**: Svenska (swe) och engelska (eng) rekommenderas
- **Verifiering**: `tesseract --version`

### Poppler
**Krävs för pdf2image (PDF-till-bild konvertering)**

- **Windows**: https://github.com/oschwartz10612/poppler-windows/releases/
- **Alternativ (Conda)**: `conda install -c conda-forge poppler`
- **PATH**: Måste läggas till systemets PATH-miljövariabel
- **Standard sökväg**: `C:\poppler\Library\bin`

## Python Standardbibliotek

Följande används från Python standardbibliotek (kräver ingen installation):

- `json` - JSON-serialisering
- `csv` - CSV-hantering
- `pathlib` - Sökvägshantering
- `os` - Operativsystemsfunktioner
- `re` - Reguljära uttryck
- `typing` - Typ-hints
- `dataclasses` - Dataklasser

## Versionshantering

### Versionsbegränsningar

Alla dependencies använder major version-begränsningar för att:
- Förhindra breaking changes från större version-uppgraderingar
- Säkerställa kompatibilitet mellan paket
- Göra installationen mer förutsägbar

### Uppdateringar

För att uppdatera dependencies:

```bash
# Uppdatera alla till senaste kompatibla version
pip install --upgrade -r requirements.txt

# Kontrollera för utdaterade paket
pip list --outdated
```

## Kompatibilitet

### Testade Kombinationer

- Python 3.10 + PySide6 6.6.0 + Windows 10/11
- Python 3.11 + PySide6 6.6.0 + Windows 10/11

### Kända Begränsningar

- **OCR-kvalitet**: Beror på Tesseract-version och språkpaket
- **PDF-komplexitet**: Mycket komplexa layout kan kräva manuell justering
- **Stora filer**: PDF:er > 50 MB kan vara långsamma att bearbeta

## Säkerhet

### Säkerhetsöverväganden

- Alla dependencies är från PyPI (Python Package Index)
- Inga dependencies kräver root/administratörsrättigheter
- PDF-filer bearbetas lokalt (ingen nätverkskommunikation)

### Rekommendationer

- Använd virtual environment för isolering
- Håll dependencies uppdaterade för säkerhetsfixar
- Granska PDF:er från okända källor innan bearbetning

## Prestanda

### Minne
- Basminne: ~200 MB (tom applikation)
- Per PDF: ~10-50 MB beroende på storlek
- Klustering: Ytterligare ~100-500 MB för större dataset

### CPU
- OCR är CPU-intensivt (använder alla tillgängliga kärnor)
- Klustering är CPU-intensivt för stora dataset (>100 PDF:er)

### Disk
- Templates: ~1-10 KB per mall
- Dokumentdata: ~1-5 MB per 100 PDF:er

## Felsökning

### Vanliga Problem

1. **TesseractNotFoundError**
   - Lösning: Installera Tesseract och lägg till till PATH

2. **PDFInfoNotInstalledError** (pdf2image)
   - Lösning: Installera Poppler och lägg till till PATH

3. **ImportError: DLL load failed**
   - Lösning: Installera Visual C++ Redistributables

4. **MemoryError vid stora PDF:er**
   - Lösning: Öka systemminne eller bearbeta färre PDF:er åt gången

Se [SETUP.md](SETUP.md) för detaljerad felsökning.

## Licensöverväganden

Alla dependencies är open source med kompatibla licenser:
- PySide6: LGPL/Commercial
- Övriga: MIT, Apache 2.0, eller liknande permissiva licenser

## Framtida Dependencies

Potentiella framtida tillägg:
- **PyMuPDF (fitz)**: Alternativ PDF-processor med bättre prestanda
- **opencv-python**: Avancerad bildförbehandling för OCR
- **langdetect**: Automatisk språkdetektering
- **dateparser**: Intelligent datumparsing
