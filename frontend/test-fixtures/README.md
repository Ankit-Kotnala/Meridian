# Test fixtures

All records in this package are synthetic and explicitly marked fictional.
`npm run fixtures:preview` prints the presentation-only fixture without performing
I/O. The real local PostgreSQL/private-object seed is the separately guarded
`make seed` / `scripts/seed-local.ps1` workflow; it does not use this preview as
persisted product data.

Phase 2 document fixtures live in `generated/`. They contain only fictional
`example.test` data and are reproducibly created by:

```powershell
uv run --project backend --package rezumi-backend python frontend/test-fixtures/scripts/generate-resume-documents.py
```

`generated/manifest.json` pins the byte length and SHA-256 digest of each benign
fixture. The corpus includes searchable one- and two-column PDFs, DOCX,
header/footer, table-heavy, date-locale, concurrent-role, unusual-font,
bidirectional-control, long-document, and image-only cases. Malformed, traversal,
archive-expansion, and malware samples are generated inside isolated tests instead of being committed;
in particular, the EICAR signature is assembled only inside the scanner test so
host antivirus software never encounters a checked-in signature.
