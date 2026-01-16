# Project State

**Last Updated:** 2026-01-16
**Current Phase:** Phase 2 - Planning

## Current Position

**Active Phase:** Phase 2 - Kärnfunktioner & Förbättringar (Planning)
**Last Completed Phase:** Phase 1 - Stabilisering & Bugfixes (Completed)
**Next Phase:** Phase 2 - Kärnfunktioner & Förbättringar (Execution)

## Accumulated Decisions

### Technical Decisions
- **GUI Framework:** PySide6 (Qt 6) for desktop application
- **PDF Processing:** PyPDF2 for text extraction, pdf2image for OCR preprocessing
- **OCR:** Tesseract OCR via pytesseract
- **ML/Clustering:** scikit-learn (TF-IDF + Agglomerative Clustering)
- **Architecture:** Modular structure with core/ and tabs/ separation

### Design Decisions
- **Coordinate System:** Normalized coordinates (0.0-1.0) for PDF-agnostic mapping
- **Template System:** JSON-based templates for field and table mappings
- **Data Storage:** JSON files in data/ directory for document metadata

## Pending Todos

- Visual mappningsvisning implementerad (visa var man mappat + extraherade värden)
- GitHub repo skapad och synkroniserad

## Blockers/Concerns

- None currently identified

## Alignment Status

**Status:** On track
**Notes:** Phase 1 (Stabilisering & Bugfixes) är komplett. Alla mål för stabilisering och bugfixes är uppfyllda. Project är redo för Phase 2: Kärnfunktioner & Förbättringar.

## Recent Accomplishments

### Phase 1 - Stabilisering & Bugfixes (Completed)

**Plan 01: PDF-visualisering och koordinatförbättringar** ✅
- Förbättrad koordinatnormalisering med normaliserade värden (0.0-1.0)
- Förbättrad zoom- och panning-funktionalitet med begränsningar
- Förbättrad synlighet av markeringar och mappade områden
- Zoom-slider synkroniserad med PDFViewer

**Plan 02: Felhantering och loggning** ✅
- Strukturerad loggning med kontext och file rotation
- Custom exception hierarchy med user_message för användarvänliga meddelanden
- Tydliga svenska felmeddelanden i alla tabs
- Graceful degradation vid saknade dependencies
- Helper-funktioner för dependency-detektering med caching
- UI-status för dependencies i DocumentTypesTab

### Phase 2 - Kärnfunktioner & Förbättringar (In Progress)

**Plan 01: Tabellmappning-förbättringar** ✅
- Automatisk header-rad detektering baserat på mönster
- Tabellvalidering med varningar före sparning
- Förhandsgranskning av extraherad tabell i realtid
- Färgkodning av tomma/problemiska celler

**Plan 02: OCR-förbättringar** ✅
- Förbättrad bildförbehandling med adaptive thresholding och noise reduction
- Multi-språkstöd med språkval per kluster via templates
- Kontrastförbättring och skew correction-stöd

**Plan 03: Smart fältdetektering** ✅
- Automatisk identifiering av vanliga fälttyper (fakturanummer, datum, belopp, etc.)
- Mönsterbaserad identifiering med regex och nyckelord
- Förslag till fälttyper i UI baserat på detektering
- Konfidensnivåer för transparens i detektering

### Earlier Accomplishments

- Created GitHub repository (ocr-mapping)
- Implemented visual mapping display (shows mapped areas and extracted values)
- Fixed AttributeError in TableMappingDialog

## Next Steps

1. ✅ Phase 1 completion verified (VERIFICATION.md created)
2. ✅ Phase 2 - Plan 01 executed and completed (Tabellmappning-förbättringar)
3. ✅ Phase 2 - Plan 02 executed and completed (OCR-förbättringar)
4. ✅ Phase 2 - Plan 03 executed and completed (Smart fältdetektering)
5. Plan Phase 2 - Plan 04: Mappningsmallar-bibliotek (nästa hög prioritet) eller ytterligare förbättringar
