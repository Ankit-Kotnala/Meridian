# Test fixtures

All records in this package are synthetic and explicitly marked fictional. Phase
0's `seed` command prints the deterministic fixture; database seeding is
introduced alongside the first durable product models.

Phase 2 document fixtures live in `generated/`. They contain only fictional
`example.test` data and are reproducibly created by:

```powershell
python packages/test-fixtures/scripts/generate-resume-documents.py
```

`generated/manifest.json` pins the byte length and SHA-256 digest of each benign
fixture. The corpus includes searchable PDF and DOCX resumes plus an image-only
PDF for the insufficient-data path. Malformed, traversal, archive-expansion, and
malware samples are generated inside isolated tests instead of being committed;
in particular, the EICAR signature is assembled only inside the scanner test so
host antivirus software never encounters a checked-in signature.
