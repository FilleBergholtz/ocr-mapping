---
phase: 01-stabilisering-bugfixes
plan: 02
status: completed
completed_at: 2026-01-16T20:45:00Z
duration_minutes: ~75
---

accomplishments:
  - Förbättrad logger med strukturerad loggning och file rotation
  - Tydliga användar-felmeddelanden på svenska i alla tabs
  - Custom exception hierarchy för tydligare felhantering
  - Graceful degradation vid saknade dependencies med helper-funktioner och caching
  - Dependency status-visning i DocumentTypesTab UI

files_modified:
  - src/core/logger.py
  - src/core/exceptions.py (new)
  - src/tabs/mapping_tab.py
  - src/core/pdf_processor.py
  - src/core/extraction_engine.py
  - src/tabs/document_types_tab.py

key_decisions:
  - Strukturerad loggning med kontextuell information för bättre debugging
  - Separation av användar-meddelanden (svenska) och teknisk loggning (engelska)
  - Custom exceptions med user_message för användarvänliga meddelanden
  - Graceful degradation pattern: applikationen fungerar även utan dependencies
  - Dependency-detektering med caching för bättre prestanda
  - UI-status för dependencies med varningar som visas endast en gång

issues_encountered: []

next_phase_readiness:
  - Plan 02 klar - Felhantering och loggning förbättrad
  - Alla success criteria uppfyllda
  - Phase 1 är nu komplett med både Plan 01 och Plan 02

# Plan 02 Summary: Felhantering och loggning

## Accomplishments

### Task 1: Förbättra logger med kontextuell information ✅

Förbättrat `setup_logger()` och `get_logger()` i `src/core/logger.py`:

- **Strukturerad loggning** med kontextuell information (funktion, fil, etc.)
- **File rotation** med max size (10MB) och backup count (5)
- **Dual logging** - INFO till console, DEBUG till fil
- **Timestamped log files** (`app-2026-01-16.log`)
- **Helper-funktioner** för vanliga loggings-scenarion:
  - `log_info_with_context()` - Loggar info med kontext
  - `log_warning_with_context()` - Loggar warnings med kontext
  - `log_error_with_context()` - Loggar errors med stack traces och kontext
  - `log_critical_with_context()` - Loggar kritiska fel med kontext

**Tekniska detaljer:**
- RotatingFileHandler för automatisk rotation
- Structured formatter med timestamp, level, module, och message
- Exception logging med full stack traces
- Kontextuell information i JSON-liknande format i loggar

### Task 2: Förbättra felmeddelanden i MappingTab ✅

Förbättrat felhantering i alla metoder i `src/tabs/mapping_tab.py`:

- **Try/except blocks** i alla kritiska operationer
- **Strukturerad loggning** med kontext innan QMessageBox visas
- **Tydliga svenska felmeddelanden** för användare
- **Debugging-info i loggar** men inte i user-facing meddelanden
- **Specifika fel-scenarion** hanterade:
  - PDF kan inte laddas: "Kunde inte ladda PDF: {filnamn}. Kontrollera att filen är korruptfri."
  - OCR misslyckas: "OCR-fel. Kontrollera att Tesseract är installerat."
  - Koordinatfel: "Kunde inte mappa koordinater. Försök markera området igen."
  - Extraktionfel: "Extraktion misslyckades. Loggar innehåller mer information."

**Förbättringar:**
- Fel loggas med `log_error_with_context()` med full kontext
- Användar-meddelanden är på svenska och användarvänliga
- Teknisk information finns i loggar för debugging
- Validering av PDF-dimensioner innan mappning

### Task 3: Förbättra felhantering i core-moduler ✅

Förbättrat felhantering i `src/core/pdf_processor.py` och `src/core/extraction_engine.py`:

**Custom Exception Hierarchy (`src/core/exceptions.py`):**
- `OCRMappingException` - Base exception för applikationen
- `PDFProcessingError` - Fel vid PDF-bearbetning (med filnamn och sidnummer)
- `OCRProcessingError` - Fel vid OCR-bearbetning (med OCR-specifik information)
- `ExtractionError` - Fel vid dataextraktion (med fält/tabellnamn)
- `DependencyNotFoundError` - Saknade dependencies (med installationsinstruktioner)
- `CoordinateError` - Fel vid koordinathantering
- `TemplateError` - Fel vid mallhantering

**PDFProcessor förbättringar:**
- **Validering** att PDF-fil existerar innan bearbetning
- **Custom exceptions** vid Tesseract/Poppler-saknas med installationsinstruktioner
- **Loggning** med kontext (filnamn, sidnummer) för alla fel
- **Graceful handling** - returnerar None eller raise custom exceptions med tydliga meddelanden

**ExtractionEngine förbättringar:**
- **Validering** av template innan extraktion
- **Hantering** av saknade koordinater med `CoordinateError`
- **Partiella resultat** - returnerar delvis extraherad data även om några fält misslyckas
- **Loggning** med kontext (vilka fält misslyckades) för debugging

**Alla exceptions har `user_message` för användarvänliga meddelanden.**

### Task 4: Graceful degradation vid saknade dependencies ✅

Förbättrat dependency-detektering och graceful degradation:

**Helper-funktioner i `src/core/pdf_processor.py`:**
- `check_tesseract_available(tesseract_cmd)` - Kontrollerar om Tesseract är tillgängligt (med caching)
- `check_poppler_available(poppler_path)` - Kontrollerar om Poppler är tillgängligt (med caching)
- `get_tesseract_installation_guide()` - Returnerar installationsguide för Tesseract
- `get_poppler_installation_guide()` - Returnerar installationsguide för Poppler

**Global caching:**
- `_tesseract_checked`, `_tesseract_path` - Cache för Tesseract-detektering
- `_poppler_checked`, `_poppler_path` - Cache för Poppler-detektering
- Dependency-checks körs endast en gång per session för bättre prestanda

**UI-förbättringar i `src/tabs/document_types_tab.py`:**
- **Systemstatus-sektion** som visar dependency-status i realtid
- **Varningsdialog** visas endast en gång vid start om dependencies saknas
- **Tydliga installationsguider** i varningsmeddelanden
- **Information** om vilka funktioner som påverkas

**Graceful degradation:**
- Applikationen fungerar fortfarande med textbaserade PDF:er även utan Tesseract
- PDF-extraktion från text-lager fungerar även utan Poppler
- Tydliga meddelanden om vad som saknas och hur man installerar det
- Funktioner som kräver dependencies är disabled men tydligt markerade

## Technical Details

### Logging Architecture

**Structured Logging:**
```
[2026-01-16 20:30:45,123] INFO [mapping_tab:load_cluster] Loading cluster: cluster-123
  Context: {file_path: "invoice.pdf", cluster_id: "cluster-123"}
```

**File Rotation:**
- Max file size: 10MB
- Backup count: 5
- Filename pattern: `app-YYYY-MM-DD.log`
- Rotating handler: Automatisk rotation när filen når max size

**Helper Functions:**
- `log_info_with_context(logger, message, context, title)` - Info med kontext
- `log_warning_with_context(logger, message, context, title)` - Warning med kontext
- `log_error_with_context(logger, exception, context, title)` - Error med stack trace
- `log_critical_with_context(logger, exception, context, title)` - Critical med stack trace

### Exception Hierarchy

**Base Exception:**
- `OCRMappingException` - Alla exceptions ärver från denna
  - `user_message` - Användarvänligt meddelande på svenska

**PDF Processing Exceptions:**
- `PDFProcessingError` - Allmänna PDF-fel
  - `file_path` - Sökväg till PDF-fil
  - `page_num` - Sidnummer (0-indexerat)
- `OCRProcessingError` - OCR-specifika fel
  - Ärver från `PDFProcessingError`
  - `ocr_engine` - OCR-motor som användes

**Extraction Exceptions:**
- `ExtractionError` - Fel vid dataextraktion
  - `field_name` - Namn på fält som misslyckades
  - `table_name` - Namn på tabell som misslyckades
- `CoordinateError` - Fel vid koordinathantering
  - `coords` - Koordinater som orsakade felet
- `TemplateError` - Fel vid mallhantering
  - `cluster_id` - Kluster-ID för mallen

**Dependency Exceptions:**
- `DependencyNotFoundError` - Saknade dependencies
  - `dependency_name` - Namn på dependency
  - `installation_guide` - Detaljerade installationsinstruktioner
  - `affected_features` - Vilka funktioner som påverkas

### Dependency Detection

**Caching Strategy:**
- Global module-level variables för caching
- First check: Kontrollera cache, returnera om finns
- Cache miss: Kör full detection, spara i cache
- Cache invalidation: Endast vid explicit path override

**Detection Methods:**
1. **Tesseract:** 
   - Kontrollera explicit path (om angiven)
   - Försök hitta automatiskt (standard paths på Windows)
   - Verifiera med `pytesseract.get_tesseract_version()`

2. **Poppler:**
   - Kontrollera explicit path (om angiven)
   - Försök hitta automatiskt (standard paths på Windows)
   - Verifiera med pdf2image import (heuristisk)

### Graceful Degradation Pattern

**Principle:** Applikationen ska vara användbar även om dependencies saknas.

**Strategy:**
1. **Detect** - Kontrollera om dependency finns vid start
2. **Inform** - Visa tydligt meddelande om vad som saknas (endast en gång)
3. **Disable** - Disable funktioner som kräver dependency (men visa tydligt)
4. **Fallback** - Använd alternativa metoder där möjligt
   - Textbaserade PDF:er fungerar utan Tesseract
   - PDF-extraktion från text-lager fungerar utan Poppler

**UI Feedback:**
- Dependency status visas i Systemstatus-sektion
- Varningar visas endast en gång vid start
- Tydliga installationsguider med länkar

## Verification

Alla success criteria uppfyllda:

- ✅ Logger loggar strukturerad information med kontext
- ✅ Alla fel i UI visar tydliga svenska meddelanden
- ✅ Alla fel loggas med stack traces och kontext
- ✅ Applikationen hanterar saknade dependencies gracefully
- ✅ Custom exceptions finns för tydligare felhantering
- ✅ Applikationen kraschar inte vid fel - hanterar fel gracefully

## Files Modified

### `src/core/logger.py`
- Förbättrad `setup_logger()` med struktur och rotation
- Helper-funktioner för kontextuell loggning
- Dual logging (console + file)

### `src/core/exceptions.py` (NEW)
- Custom exception hierarchy
- Alla exceptions med `user_message` för användarvänliga meddelanden
- Tydlig struktur för olika typer av fel

### `src/tabs/mapping_tab.py`
- Förbättrad felhantering i alla metoder
- Tydliga svenska felmeddelanden för användare
- Strukturerad loggning med kontext

### `src/core/pdf_processor.py`
- Helper-funktioner för dependency-detektering
- Custom exceptions för PDF/OCR-fel
- Validering och robust felhantering
- Graceful degradation vid saknade dependencies

### `src/core/extraction_engine.py`
- Custom exceptions för extraktionsfel
- Partiella resultat vid delvisa fel
- Loggning med kontext

### `src/tabs/document_types_tab.py`
- Dependency status-visning i UI
- Varningsdialog för saknade dependencies
- Tydliga installationsguider

## Git Commits

Följande commits implementerade Plan 02:

1. **`733c6ef`** - feat(logger): förbättra loggning med struktur, rotation och helper-metoder
2. **`a80fb58`** - feat(mapping): förbättra felhantering och felmeddelanden i MappingTab
3. **`da4df6f`** - feat(core): förbättra felhantering i core-moduler med custom exceptions
4. **`bf6cffa`** - feat(core,ui): graceful degradation vid saknade dependencies

## Next Steps

Phase 1 är nu komplett med både Plan 01 och Plan 02. Alla mål för stabilisering och bugfixes är uppfyllda:

- ✅ PDF-visualisering och koordinatförbättringar
- ✅ Felhantering och loggning

**Nästa steg:**
- Phase 2: Kärnfunktioner & Förbättringar kan nu påbörjas
- Eller: Ytterligare förbättringar i Phase 1 om behov uppstår
