# HCC Explorer

Searchable explorer for five CMS risk-adjustment models — hierarchies
(zero-out rules), ICD-10-CM mappings, and RAF coefficients:

| Toggle | Model | Payment categories | Mapping vintage | ICDs |
|---|---|---|---|---|
| V28 | CMS-HCC V28 (Medicare Advantage) | 115 HCCs | FY2024 | 7,810 |
| V24 | CMS-HCC V24 (Medicare Advantage) | 86 HCCs | FY2022 | 9,597 |
| ESRD | CMS-HCC ESRD V21 (dialysis / functioning graft) | 87 HCCs | FY2019 | 9,520 |
| HHS | HHS-HCC V07 (commercial / ACA marketplace) | 141 HCCs¹ | BY2022 | 10,735 |
| RxHCC | RxHCC R08 (Part D) | 84 RxHCCs | FY2024–25² | 5,257 |

¹ includes 4 age-split pairs (e.g. HCC 35.1 / 35.2) — CMS spells these three
different ways across its own files (`35_1`, `35.1`, `HCC035_1`); the parser
canonicalizes to `35.1`.
² PY2026 *proposed* model software (R0825.84.X2), finalized in the PY2026 Rate
Announcement.

## Use it

Open **`index.html`** in a browser. No server, no dependencies — all five
models are embedded (~3.8 MB). The model toggle is in the header; the model is
part of the URL hash (`#v24/hcc/18`, `#hhs/hcc/35.1`), so deep links are
shareable per model.

- **Search** ICD codes (`E11.22`, dot optional), ICD descriptions
  (`heart failure`), or HCCs (`HCC 37`, `diabetes`) — within the active model.
- **HCC view**: interactive hierarchy diagram (click nodes to navigate),
  complete "zeroes out" / "zeroed out by" lists, **RAF coefficients by rate
  segment** (metal-level matrix for HHS), and every ICD mapping to it.
- **ICD view**: the HCC(s) a code maps to in the active model with hierarchy
  context, plus which of the other four models also map the code (one-click
  switch).
- An arrow A → B means: if HCC A is present, HCC B is zeroed out for payment.
  Diagrams show the transitive reduction; the lists are the complete rules.
- Coefficient panels show only the HCC's own add-on; demographic, group, and
  interaction terms are out of scope. A few HHS infant-model HCCs have no
  direct coefficient (they pay via maturity/severity groups) and say so.

## Files

| File | What |
|---|---|
| `index.html` | The app (generated — do not edit directly) |
| `template.html` | UI source; `scripts/build.py` injects the data into it |
| `scripts/parse_cms.py` | Parses raw CMS files into the graph JSONs (`MODELS` dict = one entry per model) |
| `scripts/build.py` | Embeds all graph JSONs + descriptions into `index.html` |
| `graphs/<model>-hcc-graph.json` | Per-model graph: nodes (with coefficients), `edges_full`, `edges_reduced`, `icd_to_hcc` |
| `source-data/` | Raw CMS files (see below) and `icd-descriptions.json` |

## What's in `source-data/`

Four raw CMS files per model — hierarchy, labels, ICD mapping, coefficients —
kept under their original CMS filenames so they can be diffed against a fresh
CMS download. The `MODELS` dict at the top of `scripts/parse_cms.py` is the index that
says which file plays which role.

| Model | Hierarchy | Labels | ICD mapping | Coefficients |
|---|---|---|---|---|
| V28 | `V28115H1.TXT` | `V28115L3.TXT` | `F2824T1N.TXT` (FY2024) | `V28hcccoefn.csv` |
| V24 | `V24H86H1.TXT` | `V24H86L1.TXT` | `F2422P1M.TXT` (FY2022) | `V24hcccoefn.csv` |
| ESRD V21³ | `V20H87H1.txt` | `V20H87L1.txt` | `F2118H1R.txt` (FY2019) | `ESRDhcccoefn.csv` |
| HHS V07 | `V07141H1.TXT` | `V07141L1.TXT` | `CY22F07A_FY2022_ICD10.TXT`⁴ (BY2022) | `HHS22hcccoefn.csv` |
| RxHCC R08 | `R08X84H1.TXT` | `R08X84L1.TXT` | `F0825X1O_FY24FY25.TXT` (FY2024–25) | `R0826X6O.csv` |

³ the ESRD V21 model reuses the older V20 87-category structure internally,
hence the `V20H87*` filenames.
⁴ renamed from CMS's original (which contains spaces): `CY22F07A_FY 2022 ICD10.TXT`.

CMS naming convention: hierarchy files are `<model><n>H1` ("H" = hierarchy,
`<n>` = payment category count — V28**115**, V24H**86**, V07**141**), labels
are `L1`/`L3`, mappings start with `F` + year digits. File formats: hierarchy
and labels are SAS macro fragments (`%SET0(CC=…, HIER=%STR(…))` and
`HCC<n> ="…"` LABEL blocks), mappings are tab-separated `ICD10 → CC` pairs,
coefficients are CSV (wide one-row format for the CMS models, long format for
HHS and RxHCC).

Plus one derived file: **`icd-descriptions.json`** — descriptions for all
14,346 mapped ICD codes, assembled from the CMS FY2025/FY2024/FY2022
code-description files. It's the only generated file here; it lives in
`source-data/` rather than `graphs/` because it's an *input* to the build, and
regenerating it needs the large CMS description zips that aren't kept in the
repo.

## Rebuild

```sh
python3 scripts/parse_cms.py   # source-data -> graphs/<model>-hcc-graph.json
python3 scripts/build.py       # graphs + template.html -> index.html
```

CI does the same on every push: `.github/workflows/build.yml` rebuilds from
`source-data/` and sanity-checks the output; on pushes to `main` it also
deploys `index.html` to GitHub Pages (enable it once under Settings → Pages →
Source: **GitHub Actions**).

To add a model (e.g. a new fiscal year): drop the four CMS files into
`source-data/`, add a `MODELS` entry in `scripts/parse_cms.py`, rerun both scripts.
If the new mapping introduces ICD codes with no description, extend
`source-data/icd-descriptions.json` from the CMS "code descriptions in tabular
order" file for that fiscal year.

## Data sources

- **V24, V28, ESRD, HHS** files from CMS risk adjustment model software,
  mirrored by [hccpy](https://github.com/yubin-park/hccpy).
- **RxHCC** from CMS directly: [PY2026 Proposed and Alternative RxHCC Part D
  Model Software](https://www.cms.gov/files/zip/py-2026-proposed-and-alternative-rxhcc-part-d-model-software.zip)
  (proposed/X2 variant).
- **ICD descriptions** from the CMS ICD-10-CM code-description files,
  first-match across FY2025 → FY2024 → FY2022 (codes + order files, so
  non-billable headers resolve too). Four pre-FY2021 poisoning codes
  (T40.4X2A/S, T40.7X2A/S) have manually written descriptions.
- Model vintages differ because they're the latest each source carries; the
  ESRD mapping (FY2019) is the oldest. Newer years exist in CMS model software
  zips if needed.
