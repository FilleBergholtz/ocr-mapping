# Installera Poppler

Poppler krävs för att konvertera PDF-sidor till bilder (används för OCR och PDF-visualisering).

## Snabbinstallation

### Steg 1: Ladda ner Poppler

1. Gå till: https://github.com/oschwartz10612/poppler-windows/releases/
2. Ladda ner den senaste `Release-XX.XX.X-X.zip` filen
3. Extrahera zip-filen

### Steg 2: Installera Poppler

**Alternativ A: Standardplats (Rekommenderas)**
1. Skapa mappen `C:\poppler` om den inte finns
2. Extrahera innehållet från zip-filen till `C:\poppler`
3. Du bör ha strukturen: `C:\poppler\Library\bin\pdftoppm.exe`

**Alternativ B: Anpassad plats**
1. Extrahera till valfri plats (t.ex. `D:\Tools\poppler`)
2. Kom ihåg sökvägen för konfiguration senare

### Steg 3: Lägg till till PATH

#### Temporärt (för nuvarande session):
```powershell
# PowerShell
$env:PATH += ";C:\poppler\Library\bin"
```

#### Permanent (Rekommenderas):

**Windows 10/11:**
1. Öppna "System Properties" (Win + Pause/Break)
2. Klicka "Environment Variables"
3. Under "System variables", välj "Path" och klicka "Edit"
4. Klicka "New" och lägg till: `C:\poppler\Library\bin`
5. Klicka "OK" på alla dialoger
6. **Starta om terminalen** för att PATH ska uppdateras

**Via PowerShell (Admin):**
```powershell
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "Machine") + ";C:\poppler\Library\bin",
    "Machine"
)
```

### Steg 4: Verifiera installation

```powershell
# Kontrollera att Poppler är tillgängligt
pdftoppm -h
```

Om kommandot fungerar, är Poppler korrekt installerat!

## Konfigurera i applikationen

Om du inte vill lägga till Poppler till systemets PATH, kan du konfigurera sökvägen direkt i applikationen:

### I koden:

Uppdatera `src/tabs/document_types_tab.py` och `src/tabs/mapping_tab.py`:

```python
# Istället för:
pdf_processor = PDFProcessor()

# Använd:
pdf_processor = PDFProcessor(
    poppler_path=r"C:\poppler\Library\bin"
)
```

## Alternativ: Använd Conda

Om du använder Conda:

```bash
conda install -c conda-forge poppler
```

Detta installerar Poppler automatiskt och konfigurerar PATH.

## Felsökning

### "Unable to get page count. Is poppler installed and in PATH?"

**Lösning:**
1. Kontrollera att Poppler är extraherad korrekt
2. Verifiera att `pdftoppm.exe` finns i `C:\poppler\Library\bin`
3. Lägg till till PATH (se ovan)
4. Starta om terminalen/applikationen

### "pdftoppm: command not found"

**Lösning:**
- PATH är inte uppdaterad - starta om terminalen
- Eller använd manuell sökväg i koden (se ovan)

### Testa manuellt:

```powershell
# Testa att köra pdftoppm direkt
C:\poppler\Library\bin\pdftoppm.exe -h
```

Om detta fungerar men `pdftoppm` inte gör det, är PATH-problemet.

## Ytterligare resurser

- Poppler Windows releases: https://github.com/oschwartz10612/poppler-windows/releases/
- Poppler dokumentation: https://poppler.freedesktop.org/
