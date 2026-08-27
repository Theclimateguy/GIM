# references.bib — audit

Source: `Paper/references_v2.bib` (72 entries). Result: **87 entries**, all cited, BibTeX
parses clean, `plainnat` author–year output verified in the compiled PDF.

## 1. Syntax errors that were silently breaking the build (6, all fixed)

A missing comma before a trailing `doi` field. BibTeX's recovery swallows the field, so the
DOIs were simply absent from the output rather than erroring loudly:

`ipcc_ar6_wg1`, `bernanke1999`, `celasun2021`, `lagi2011food`, `meadows1972`, `stern2007`.

## 2. Cross-check against the manuscript

- Cited in the old `.tex` but missing from the `.bib`: **none**.
- In the `.bib` but never cited: **9** — `augusiak2014`, `bennett2013`, `craig1997`,
  `grimm2014trace`, `grimm2020odd`, `jakeman2006`, `saltelli2020`, `schwanitz2013`,
  `wilson2021`. These are the model-evaluation literature someone had already collected and
  never wired in. **All are now cited**: the evaluation hierarchy in §1, the verification/
  corroboration ("evaludation") distinction in §3.2, `craig1997` as the origin of history
  matching in §5, `saltelli2020` in §2. This matters for GMD — a model-description paper that
  never places itself in the model-evaluation literature reads as unaware of it.
  (`grimm2020odd` is cited but ODD is not adopted; if a referee pushes, an ODD-structured
  supplement is the cheap answer.)

## 3. Wrong or weak entries

| Entry | Problem | Action |
|---|---|---|
| `sundberg2013` | Sundberg & Melander 2013 is the **UCDP GED** (georeferenced *event* dataset). The paper scores against the **UCDP/PRIO Armed Conflict Dataset**, a different product. | Kept, but the conflict claims now cite `gleditsch2002` (the ACD's own reference) + `davies2024` (the annual update), with the version stated: **v24.1**, as in `data/external/SOURCES.md`. |
| `lagi2011food` | Typed `@article` with journal "arXiv preprint" **and** an SSRN DOI — two mutually inconsistent venues. | Left as-is pending your call on which record you actually used; the text already flags it as a working paper. Recommend picking one. |
| `barney2002` | Key says "barney" but author is `{Millennium Institute}`, and it is a URL note with no bibliographic substance. | Left; if a referee objects, Barney, G.O. (2002), *Futures* 34:135–146 is the citable T21 paper. |
| `epa2023` | `@techreport` with no DOI or URL. | Left; add the EPA report URL before submission. |
| `theclimateguy2026gim` | Pointed at **v18.1.4** / `zenodo.21575176`. | Rewritten to **v20.1.0**, Apache-2.0, tag `v20.1.0`, and the DOI is a **placeholder `10.5281/zenodo.XXXXXXXX`** — `.zenodo.json` declares the new deposit `isNewVersionOf` 21575176, so the new DOI does not exist yet. **This is the one blocking TODO in the package.** |

## 4. Additions (15) — every one needed by a claim the old paper made without support

**Observational datasets the reviews correctly said were never named.** GMD's code-and-data
policy requires each comparison dataset to be cited with a version.

- `morice2021` — HadCRUT5.1.0.0. The paper reported a temperature RMSE against an unnamed
  series; `tests/fixtures/climate_observations_1990_2023.json` records it as HadCRUT.5.1.0.0
  rebased to 1850–1900.
- `noaa_gml_co2` — NOAA GML global annual mean CO₂, used to seed the base-year stock.
- `worldbank_pinksheet` — the Pink Sheet indices the whole resource-price validation is scored
  against, with the CC BY 4.0 licence and 2026-08-24 retrieval date.
- `worldbank_wdi` — WDI, source of output, population, debt, reserves, milex and Gini.
- `gleditsch2002`, `davies2024` — UCDP/PRIO ACD and its 2024 update.
- `sipri_milex` — SIPRI, behind the CINC military component. Flagged non-commercial-use-only in
  the data table.

**Forcing and climate anchors.**

- `meinshausen2020` — the SSP concentration/forcing paper. The non-CO₂ path is taken from the
  SSP2-4.5 marker; the old paper used that path and cited nothing for it.
- `forster2021` — AR6 WG1 Ch. 7. Needed because GIM uses the Myhre 1998 F₂ₓ rather than the AR6
  value, which the Limitations now states explicitly.
- `sherwood2020` — the multi-line ECS assessment, supporting the 3.0 °C prior.

**Economic regularities asserted by name and cited to nothing.**

- `okun1962` — "unemployment follows Okun's law".
- `phillips1958` — "inflation a flat post-1990 Phillips curve".
- `laeven2020` — the 3–5 % currency-crisis base rate the FX channel is validated against; the
  experiment file names Laeven & Valencia, the paper did not.
- `barro2008` — regime-collapse output/capital multipliers, previously plain text in a table.
- `nordhaus2018` — DICE-2016R, the actual reference for the deep-ocean heat capacity and the
  \$31 SCC comparison.

## 5. Style

`plainnat` + `natbib[round,authoryear]` produces the Copernicus-style `(Smith, 2009)` /
`Smith (2009)` / `(Smith, 2009; Mueller et al., 2010)` and an alphabetical list. Swap
`\bibliographystyle{plainnat}` → `{copernicus}` at production; no entry changes needed.
