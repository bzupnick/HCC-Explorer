# CLAUDE.md

See README.md for full docs; this file is only the non-obvious constraints.

Generated files (`index.html`, `graphs/`): never edit directly — see
"Development" in README.md for the edit-and-rebuild workflow.

## Data gotchas
- **HCC ids are strings, never ints.** HHS V07 has age-split HCCs ("35.1"),
  which CMS spells three different ways across its own files (`35_1`, `35.1`,
  `HCC035_1`). Parsing ids as integers silently corrupts the graph (this bug
  happened once: `35_1` became `35` + a bogus edge to HCC `1`). Use `norm()` /
  `hcc_key()` in Python and `hccCmp()` in JS.
- CMS text files are **latin-1**, not UTF-8.
- Coefficient CSVs come in three shapes (wide / HHS long / RxHCC long) —
  see `COEF_PARSERS` in parse_cms.py.

## Verifying changes
No test suite. Verify by serving the build over HTTP (`python3 -m http.server`;
`file://` is rejected by browser-driver tooling) and driving headless Chrome
via CDP — check the console for errors, exercise search, a hierarchy diagram,
and an HHS split-HCC route like `#hhs/hcc/35.1`. The CI workflow's
sanity-check step (`.github/workflows/build.yml`) is the minimum bar: the
embedded payload must parse and contain all five models, non-empty.
