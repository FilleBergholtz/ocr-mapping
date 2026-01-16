# Installation och Setup

## Systemkrav

### Windows
- Windows 10 eller senare
- Python 3.8 eller senare
- Minst 4 GB RAM (rekommenderas 8 GB för större PDF-filer)

### Externt mjukvara (måste installeras separat)

#### 1. Tesseract OCR
**Krävs för OCR-funktionalitet**

- **Ladda ner**: https://github.com/UB-Mannheim/tesseract/wiki
- **Installation**:
  1. Ladda ner Windows-installeraren
  2. Kör installeraren
  3. Standard installationssökväg: `C:\Program Files\Tesseract-OCR\tesseract.exe`
  4. Välj svenska och engelska språkpaket under installationen

**Verifiera installation:**
```bash
tesseract --version
```

#### 2. Poppler (för pdf2image)
**Krävs för att konvertera PDF till bilder**

- **Ladda ner**: https://github.com/oschwartz10612/poppler-windows/releases/
- **Installation**:
  1. Ladda ner zip-filen
  2. Extrahera till `C:\poppler` (eller valfri plats)
  3. Lägg till `C:\poppler\Library\bin` till systemets PATH-miljövariabel

**Alternativt**: Om du använder conda:
```bash
conda install -c conda-forge poppler
```

## Python-installation

### Steg 1: Installera Python

1. Ladda ner Python från https://www.python.org/downloads/
2. Under installationen, **kryssa i "Add Python to PATH"**
3. Verifiera installation:
```bash
python --version
```

### Steg 2: Skapa Virtual Environment (Rekommenderas)

```bash
# Skapa virtual environment
python -m venv venv

# Aktivera virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Windows CMD:
venv\Scripts\activate.bat
```

### Steg 3: Installera Python-dependencies

```bash
# Installera alla dependencies
pip install -r requirements.txt

# Om du vill installera dev-dependencies också:
pip install -r requirements-dev.txt
```

### Steg 4: Verifiera installation

Kör följande för att kontrollera att alla paket är installerade:

```bash
python -c "import PySide6; import PyPDF2; import pdf2image; import pytesseract; import PIL; import numpy; import sklearn; import pandas; import openpyxl; print('Alla paket installerade korrekt!')"
```

## Konfiguration

### Tesseract-sökväg (om Tesseract inte är i standardplats)

Om Tesseract är installerad på en annan plats, kan du antingen:

1. **Lägga till till PATH**: Lägg till Tesseract-installationsmappen till systemets PATH
2. **Modifiera kod**: I `src/core/pdf_processor.py`, uppdatera `PDFProcessor.__init__()` med rätt sökväg:

```python
pdf_processor = PDFProcessor(
    tesseract_cmd=r"C:\Sökväg\Till\Tesseract\tesseract.exe"
)
```

### Poppler-sökväg (om pdf2image inte hittar Poppler)

Om Poppler inte hittas automatiskt, lägg till till PATH eller använd miljövariabel:

```bash
# Windows PowerShell
$env:PATH += ";C:\poppler\Library\bin"
```

## Felsökning

### Problem: "TesseractNotFoundError"
**Lösning**: 
- Kontrollera att Tesseract är installerad
- Verifiera att Tesseract finns i PATH eller uppdatera `PDFProcessor` med rätt sökväg

### Problem: "pdf2image.exceptions.PDFInfoNotInstalledError"
**Lösning**:
- Installera Poppler och lägg till till PATH
- Se instruktioner ovan för Poppler-installation

### Problem: "ModuleNotFoundError"
**Lösning**:
- Kontrollera att virtual environment är aktiverat
- Kör `pip install -r requirements.txt` igen
- Verifiera Python-version (kräver 3.8+)

### Problem: "ImportError: DLL load failed"
**Lösning**:
- Detta kan bero på saknade Visual C++ Redistributables
- Ladda ner och installera: https://aka.ms/vs/17/release/vc_redist.x64.exe

## Snabbstart

Efter installation:

```bash
# Aktivera virtual environment
.\venv\Scripts\Activate.ps1

# Kör applikationen
python main.py
```

## Ytterligare resurser

- **PySide6 dokumentation**: https://doc.qt.io/qtforpython/
- **Tesseract OCR**: https://tesseract-ocr.github.io/
- **Poppler**: https://poppler.freedesktop.org/
