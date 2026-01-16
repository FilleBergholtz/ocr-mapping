---
phase: 02-karnfunktioner-forbattringar
plan: 01
status: completed
completed_at: 2026-01-16T21:30:00Z
duration_minutes: ~60

accomplishments:
  - Automatisk header-rad detektering baserat på mönster
  - Visuell markering av header-rad med ljusblå bakgrund
  - Auto-fyllning av kolumnnamn från header-rad
  - Manuell justering av header-rad med spinbox
  - Tabellvalidering med varningar före sparning
  - Förhandsgranskning av extraherad tabell i realtid
  - Färgkodning av tomma/problemiska celler i förhandsgranskning

files_modified:
  - src/tabs/table_mapping_dialog.py
  - src/core/extraction_engine.py
  - src/tabs/mapping_tab.py

key_decisions:
  - Header-detektering baserad på mönster (text vs siffror, kolumnantal, etc.)
  - Proaktiv validering med varningar (användare kan fortsätta med medvetenhet om risker)
  - Realtidsförhandsgranskning för bättre UX
  - Färgkodning för visuell feedback (gul = varning, vit = OK)

issues_encountered: []

next_phase_readiness:
  - Plan 01 klar - Tabellmappning-förbättringar implementerade
  - Redo för Plan 02: OCR-förbättringar (nästa hög prioritet i Phase 2)

# Plan 01 Summary: Tabellmappning-förbättringar

## Accomplishments

### Task 1: Avancerad kolumnmappning med interaktiv identifiering ✅

**Automatisk header-rad detektering:**
- Implementerat smart header-detektering baserat på flera kriterier:
  - Text vs siffror (header innehåller ofta text, inte bara siffror)
  - Kolumnantal (header har ofta fler icke-tomma kolumner)
  - Position (header är ofta första raden)
  - Cell-längd (header-celler är ofta kortare än data-celler)

**Visuell markering:**
- Header-rad markeras med ljusblå bakgrund (#C8E6FF) för tydlig visuell feedback
- Markering uppdateras automatiskt när header-rad ändras

**Auto-fyllning av kolumnnamn:**
- Kolumnnamn fylls automatiskt från identifierad header-rad
- Smart detektering: skippar långa textvärden och siffror
- Användare kan enkelt redigera eller behålla förslagen

**Manuell justering:**
- Spinbox för manuell val av header-rad index (0-10)
- Checkbox för att aktivera/inaktivera header-rad
- Ändringar uppdaterar kolumnnamn-förslag och visuell markering

### Task 2: Tabellvalidering och varningar ✅

**Validering i TableMappingDialog:**
- Proaktiv validering innan sparning av mappning
- Varningar för:
  - Saknade kolumner (index utanför tabellområdet)
  - Intilliggande kolumner (misstänkt split-fel)
  - Inkonsekvent tabellstruktur (olika antal kolumner per rad)
  - Header-rad utanför tabellområdet
  - Ingen data i förhandsgranskning

**Validering i ExtractionEngine:**
- `_validate_table_mapping()` metod implementerad
- Validerar tabellstruktur vid extraktion
- Loggar varningar med kontext för debugging
- Returnerar partiella resultat även vid varningar

**Användarvänliga varningar:**
- Varningar visas i QMessageBox före sparning
- Användare kan välja att fortsätta eller avbryta
- Tydliga svenska meddelanden som förklarar problem

### Task 3: Förhandsgranskning av extraherad tabell ✅

**Förhandsgranskning i TableMappingDialog:**
- Ny förhandsgranskning-sektion i dialogfönstret
- Visar hur tabellen kommer att extraheras baserat på nuvarande mappning
- Uppdateras i realtid när kolumnnamn ändras
- Visar extraherade värden för varje rad och kolumn

**Visuell representation:**
- QTableWidget för tydlig tabellrepresentation
- Färgkodning av celler:
  - Gul bakgrund (#FFFFC8) för tomma celler (varning)
  - Vit bakgrund för OK-celler med data
- Kolumnnamn visas i header

**Dynamisk uppdatering:**
- Förhandsgranskning uppdateras när:
  - Kolumnnamn ändras (textChanged signal)
  - Header-rad ändras
  - Has-header checkbox togglas

### Task 4: Förbättrad header-rad detektering ✅ (Delvis)

**Automatisk header-detektering:**
- Implementerat smart algoritm baserad på flera kriterier
- Analyserar första 3 raderna för att hitta bästa header-kandidat
- Poängsystem för att identifiera mest troliga header-rad

**Header-hantering:**
- Automatisk detektering vid dialog-öppning
- Manuell justering via spinbox
- Header-hantering används för auto-fyllning och extraktion

**Förbättringar för framtiden:**
- Stöd för flera header-rader (grupperade headers) - kan implementeras vid behov
- Mer avancerad header-detektering med ML - kan implementeras i framtida planer

## Technical Details

### Header-detektering Algoritm

**Poängsystem baserat på flera kriterier:**
1. Text vs siffror: +2 poäng per text-cell (inte bara siffror)
2. Icke-tomma kolumner: +1 poäng per icke-tom kolumn
3. Position: +3 poäng om första raden
4. Cell-längd: +2 poäng om genomsnittlig längd < 20 tecken

**Resultat:** Raden med högst poäng väljs som header-rad.

### Tabellvalidering

**Valideringar i TableMappingDialog:**
1. Alla mappade kolumner finns i tabellen
2. Kolumner är inte för nära varandra (index-skillnad > 1)
3. Tabellstruktur är konsekvent (samma antal kolumner per rad)
4. Header-rad ligger inom tabellområdet
5. Förhandsgranskning innehåller data

**Valideringar i ExtractionEngine:**
1. Kolumnindices är rimliga (inte utanför tabellstruktur)
2. Tabellstruktur är konsekvent
3. Header-rad finns om den förväntas
4. Kolumner är korrekt separerade

### Förhandsgranskning Implementation

**Data-flöde:**
1. Användare ändrar kolumnnamn → `textChanged` signal
2. `_update_preview()` anropas
3. Hämta nuvarande kolumnmappningar från inputs
4. Extrahera data från table_rows baserat på mappningar
5. Skippa header-rad om has_header är aktiverat
6. Uppdatera preview_table med extraherade värden
7. Färgkoda celler baserat på status

**Performance:**
- Förhandsgranskning uppdateras endast vid ändringar
- Effektiv algoritm för data-extraktion
- Max 200px höjd för förhandsgranskning (scrollbar vid behov)

## Verification

Alla success criteria uppfyllda:

- ✅ Interaktiv kolumnidentifiering fungerar korrekt (via header-detektering)
- ✅ Kolumnpositioner detekteras automatiskt (baserat på whitespace i extract_table_text)
- ✅ Användare kan justera header-rad manuellt (spinbox)
- ✅ Tabellvalidering fungerar korrekt med tydliga varningar
- ✅ Förhandsgranskning visar extraherade värden korrekt
- ✅ Header-rader detekteras automatiskt och kan justeras manuellt
- ✅ Alla förbättringar är intuitiva och användarvänliga

## Files Modified

### `src/tabs/table_mapping_dialog.py`
- Lägg till header-rad val-sektion (spinbox + checkbox)
- Implementera `_detect_header_row()` för automatisk detektering
- Implementera `_highlight_header_row()` för visuell markering
- Implementera `_on_header_row_changed()` och `_on_has_header_toggled()`
- Implementera `_update_preview()` för realtidsförhandsgranskning
- Implementera `_validate_table_structure()` för proaktiv validering
- Förbättra `_validate_and_accept()` med valideringsvarningar
- Ändra `get_result()` för att returnera (mappings, has_header, header_index)

### `src/core/extraction_engine.py`
- Lägg till `_validate_table_mapping()` metod för validering
- Anropa validering i `_extract_table()` med loggning av varningar
- Validera tabellstruktur, kolumnindices, och header-rad

### `src/tabs/mapping_tab.py`
- Uppdatera `_on_table_selected()` för att hantera ny get_result() format
- Använd `has_header_row` från dialog istället för hardcoded True

## Git Commits

Följande commits implementerade Plan 01:

1. **`0b507d7`** - feat(table-mapping): förbättrad header-detektering och auto-fyllning av kolumnnamn
   - Automatisk header-detektering
   - Visuell markering
   - Auto-fyllning

2. **`0812ddb`** - feat(table-mapping): förbättrad tabellvalidering och förhandsgranskning
   - Tabellvalidering med varningar
   - Förhandsgranskning i realtid
   - Färgkodning

## Next Steps

Plan 01 är komplett. Alla viktiga förbättringar för tabellmappning är implementerade:

- ✅ Automatisk header-detektering
- ✅ Tabellvalidering med varningar
- ✅ Förhandsgranskning i realtid
- ✅ Auto-fyllning av kolumnnamn

**Nästa steg:**
- Plan 02: OCR-förbättringar (bildförbehandling, multi-språkstöd)
- Eller: Ytterligare förbättringar i tabellmappning om behov uppstår
