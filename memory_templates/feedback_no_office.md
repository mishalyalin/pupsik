---
name: Never create Office files
description: CRITICAL - Misha has no Microsoft Office. Always use Google ecosystem (Sheets/Docs/Slides). Never create XLSX, DOCX, or PPTX.
type: feedback
originSessionId: af6bd2f3-9e29-4055-9165-6ed45b721f14
---
NEVER create Microsoft Office files (XLSX, DOCX, PPTX). Misha does NOT have Office installed.

**Why:** Misha was very explicit (2026-04-16, multiple times) - there is no Excel, no Word, no PowerPoint.

**How to apply:**
- Spreadsheets → Google Sheets (edit existing URL or create new via API)
- Documents → Google Docs
- Presentations → Google Slides
- If Misha provides a Google Sheets URL - work directly IN that spreadsheet, never create a local copy
- Skills like `/xlsx`, `/docx`, `/pptx` should redirect to the Google equivalent

Google Sheets URL for your-company financial model: <your-spreadsheet-url>
