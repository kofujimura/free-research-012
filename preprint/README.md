# English preprint of free-research-012

Created after the research run, at the human author's request, by Claude Opus 5.5 (Anthropic) in Claude Code, with the `research-to-arxiv` procedure. Nothing here was uploaded or submitted.

## Files

| Path | What it is |
|---|---|
| `arxiv/main.tex` | English manuscript (pdfLaTeX, ASCII only, inline bibliography). Red `[...]` marks (`\fillin{}`) are facts only the human author can supply |
| `arxiv/tables/tab_*.tex` | The 33 tables, generated; do not edit by hand |
| `make_tables_tex.py` | Generates the tables from the run's analysis outputs (see below) |
| `check_values.py` | Stricter number check between `paper.md` and the LaTeX version |
| `sources_check/` | Reference checks of 2026-10-19: arXiv API responses (`arxiv_*.xml`), Crossref records (`crossref_*.json`), HTTP status of the other URLs (`url_status.tsv`), upstream heads (`upstream_heads.txt`) and the AMELAG issue-tracker search (`gh_*.json`) |
| `main_preview.pdf` | Preview built with Tectonic (31 pages) |
| `arxiv_submission.tar.gz` | Upload bundle (`main.tex` + `tables/`); ignored by Git, rebuilt by the build step |
| `arxiv_metadata.txt` | Title, authors, abstract (1,822 characters), comments, suggested categories, licence |
| `build/` | Build log and page images (ignored by Git) |

## Rebuilding

From the release root, with the analysis environment of the run (`requirements-analysis.txt`; pandas, numpy, jinja2):

```sh
python -I -B preprint/make_tables_tex.py      # tables; asserts paper.md is reproduced byte for byte
python3 -I preprint/check_values.py                                  # number checks (standard library only)
cd preprint/arxiv && pdflatex main.tex && pdflatex main.tex && pdflatex main.tex
```

`make_tables_tex.py` calls the run's own `scripts/render_paper.py` functions on the CSVs listed in `config/report-results.json`, re-renders `paper.template.md`, asserts that the result equals `paper.md` byte for byte, translates the Japanese labels with a fixed dictionary (numbers pass through unchanged) and writes `arxiv/tables/`. `tab_extended.tex` also carries the 0- and 2-week values that the original manuscript showed only in a figure.

## Checks run (2026-10-19)

- **Build:** pdfLaTeX (local TeX Live 2026; arXiv also uses pdfLaTeX) and Tectonic both build without errors, with 0 overfull boxes and 0 undefined references; the sources contain no non-ASCII characters. All 31 pages were inspected as page images.
- **Tables:** the re-rendered manuscript equals `paper.md` byte for byte, so every table cell equals the original. The analysis outputs are unrounded and rounded once for display, so there were no rounding corrections.
- **Numbers** (`check_values.py`): all 389 interval triples occur verbatim in `paper.md`, except the eight 0- and 2-week values of Table 8 taken from the figure's data. Numbers in the LaTeX version found in none of the sources: those eight values; 1.8 (GB of excluded weights, from the file sizes in `SHA256SUMS.json`); 139.7 (MB, size of the excluded file); 0.162 and 6.1 (the Codex package version and model name seen in the process list after the run, marked as unconfirmed). The skill's generic `check_numbers.py` additionally lists section numbers, bibliographic numbers (volumes, pages, article numbers, URLs), clock times, the protocol version 1.9, package versions and the run's counts taken from `final_report.md` and `manifest.json` (e.g. 8519, 4561, 177911, 178110, 1246056); numbers glued to Japanese text in `paper.md` (e.g. 71, 104, 120, 12012) are not found by that script but are found by `check_values.py`. All were checked.
- **Abstract:** 1,822 characters (arXiv limit 1,920); the metadata abstract is generated from the LaTeX abstract.
- **References:** see `sources_check/` and `../CHANGES_AFTER_RUN.md`.

## Before submitting (the human author)

1. Replace every red `\fillin{}`: affiliation (optional), the research model's identifier and settings, whether you reviewed the translation, confirmation of your role and whether you checked the data, and the repository URL (twice).
2. Read the whole translation against `../paper.md`; you take full responsibility for the content.
3. Decide the categories (suggested: stat.AP primary; cs.LG and q-bio.PE cross-lists). A first submission to a category may need an endorsement.
4. Upload `arxiv_submission.tar.gz`, and check arXiv's own pdfLaTeX preview (the local preview was built with Tectonic, which is XeTeX-based; a pdfLaTeX build was also checked locally).
5. Publish the replication package (this directory, a local Git repository) and put its URL into `main.tex`, `arxiv_metadata.txt`, `../README.md` and `../CITATION.cff`.
6. Decide whether to tell the AMELAG and New Zealand data maintainers about the preprint.
