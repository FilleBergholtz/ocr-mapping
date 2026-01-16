# Project State

**Last Updated:** 2026-01-16
**Current Phase:** Planning Phase 1

## Current Position

**Active Phase:** None (planning phase 1)
**Last Completed Phase:** None
**Next Phase to Plan:** Phase 1 - Stabilisering & Bugfixes

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
**Notes:** Project is in early development phase. Core functionality exists but needs stabilization per Phase 1 roadmap.

## Recent Accomplishments

- Created GitHub repository (ocr-mapping)
- Implemented visual mapping display (shows mapped areas and extracted values)
- Fixed AttributeError in TableMappingDialog

## Next Steps

1. Plan Phase 1 (Stabilisering & Bugfixes)
2. Begin execution of Phase 1 plans
