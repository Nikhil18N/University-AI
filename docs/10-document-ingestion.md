# Document Ingestion

## Supported inputs
- PDF
- Text
- DOCX where supported
- Scanned PDF through OCR where necessary

## Processing
1. Validate file.
2. Calculate checksum.
3. Detect duplicate.
4. Extract text/layout.
5. Extract tables where possible.
6. Normalize headers/footers.
7. Preserve page numbers.
8. Create metadata.
9. Chunk content.
10. Generate embeddings.
11. Store vectors and metadata.
12. Mark document active only after successful indexing.

## Special cases
- Multi-column PDFs
- Tables
- Images
- Scanned pages
- 50–100+ page documents
- Broken text encoding

## Versioning
Do not overwrite an old document invisibly. Keep versions and active/inactive status.
