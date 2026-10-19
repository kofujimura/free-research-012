# Forecasters and the Freshness of Published Information in Wastewater Surveillance — replication package

Code, analysis outputs and the complete research record for:

> Ko Fujimura (Otsuma Women's University, Faculty of Social Information Studies). *Forecasters and the Freshness of Published Information in Wastewater Surveillance: A Comparison Based on Actual Publication Histories.* Preprint, 2026. [arXiv identifier to be added]

The study compares pretrained time-series forecasters (Chronos-Bolt, TimesFM 2.5) fed older actually published wastewater data with classical forecasters fed the latest data, using the public Git publication histories of Germany's AMELAG and New Zealand's wastewater surveillance.

## Please read first

- **This study was conducted autonomously by an AI research agent.** An OpenAI model running in the Codex command-line agent chose the topic, designed and ran all experiments, analysed the data and wrote the original manuscript (in Japanese, `paper.md`). The model was `gpt-6.1-sol` with reasoning effort xhigh, as stated by the human author after the run; the run's own records describe it only as "Codex, based on GPT-6", because the identifier was not exposed to the agent. The run was one agent session from 2026-10-18 15:26:38 UTC (initial draft 2026-10-19 03:54:02 UTC, final manuscript 06:38:53 UTC). It stopped three times at the runtime's usage limit and was resumed by the human author each time. The human author wrote the topic-agnostic instruction protocol; `input_prompt.md` is the AI's own, incomplete transcription of it (known omissions are listed in `manifest.json`). One review round was done by another AI agent (Claude Opus 5.5 in Claude Code, according to that agent's record), whose report the human author transmitted (`review/review-1.md`, answered in `review/response-1.md`).
- **Verification status.** All checks in the record were done by AI systems: the research agent's own offline replays of all tables (`VERIFY.md`, `review/verification-result.json`, `review/final-verification-result.json`) and the reviewing agent's re-runs on the same machine. Neither is an independent replication. Checks by the human author: [to be added].
- **Changes after the run** (English version, regenerated tables, figures replaced by tables, re-checked references, an issue-tracker search) are listed in `CHANGES_AFTER_RUN.md`. No number of the original manuscript was changed.
- **Language.** The original manuscript and most records are in Japanese. The English manuscript is in `preprint/`.

## Layout

| Path | Contents |
|---|---|
| `preprint/` | English manuscript (`arxiv/main.tex`, `arxiv/tables/`), preview PDF, arXiv metadata, table generator and checks. Created after the run |
| `paper.md`, `figures/` | Original manuscript (Japanese) and its two figures, as finalised by the run |
| `paper.template.md`, `paper-facts.json`, `table_*.md` | Template and rendered values/tables; `scripts/render_paper.py` renders `paper.md` from the analysis outputs |
| `input_prompt.md` | The AI's transcription of the instruction protocol (incomplete; see `manifest.json`) |
| `manifest.json`, `requirements-*.txt` | Environment, model description, limits, known gaps; Python packages |
| `events.jsonl`, `research_log.md`, `interventions.jsonl`, `checkpoint.md` | Event log, readable research log, human interventions, checkpoint |
| `protocol/` | Topic selection, plan versions and revisions (append-only); `deviations.md` indexes the revisions |
| `claims.jsonl`, `sources.jsonl` | Claims with evidence and checks; sources with reading scope |
| `final_report.md`, `execution-summary.json` | Final report of the run and its machine-readable summary |
| `VERIFY.md` | Verification procedure (Japanese; summary below) |
| `experiments/` | Every experiment (successful and failed): `run.json`, logs, raw forecasts, analysis outputs, trained pooled models |
| `data/` | Frozen AMELAG and New Zealand data versions, documents and licences; model metadata (see `data/NOTICE.md`) |
| `config/`, `scripts/` | Configuration and all code written by the AI |
| `api/`, `api_calls.jsonl` | The single AI API call (topic critique by `gpt-6-astra`): request, response, usage and cost |
| `literature/` | AI-written reading notes and metadata checks only (full texts not redistributed, see below) |
| `review/` | Self-check, review, response, verification records; `review/submission-1/` holds the initial draft |
| `SHA256SUMS.json`, `SHA256SUMS-check.json` | SHA-256 inventory produced at the end of the run (lists files not redistributed here) |
| `RUN_README.md` | The run's own README (Japanese), unchanged |
| `RELEASE_SHA256SUMS.txt` | SHA-256 of every file in this repository except itself (build outputs ignored by Git are not listed); check with `shasum -a 256 -c RELEASE_SHA256SUMS.txt` |

## Not included, and how to regenerate it

| Item | Reason | How to regenerate |
|---|---|---|
| `data/models/*/model.safetensors` (Chronos-Bolt base, TimesFM 2.5 200M and the pilot's Chronos-Bolt tiny; about 1.8 GB) | Third-party weights (Apache-2.0); size | Download from Hugging Face at the revisions in `data/models/weight-publication-metadata.json` (`scripts/acquire_models.py`); SHA-256 in `SHA256SUMS.json`. Needed only to re-run inference, not to recompute the results from the saved forecasts |
| 109 files in `literature/` (PDFs, text extractions, captured web pages, search results, copies of documentation pages) | Third-party copyrighted text | URLs and reading scope in `sources.jsonl`, retrieval records in `data/downloads.jsonl`, SHA-256 in `SHA256SUMS.json` |
| `experiments/E072-site-panel-analysis/results/case-scores.csv.gz` (139.7 MB) | Larger than GitHub's 100 MB per-file limit | Recomputed by the `site` stage of `scripts/reproduce.py`; in the run's own replays and in the post-run replay from this package the recomputed file had the same SHA-256 (`4901f433...`, listed in `SHA256SUMS.json`) |
| `.verify-work/` | The run's self-verification work area (about 1.1 GB), excluded by the run from `SHA256SUMS.json` | Follow `VERIFY.md` |
| The run's local Git history (tags `submission-1`, `final`, `final-record`) | Size; this package is a snapshot of the run directory at the `final-record` commit `59a4fb4b82721a61d55009374989251e75d32cbf` | Not regenerable; [author to decide whether to publish it]. The initial draft is in `review/submission-1/` |
| `.venv/`, `.cache/`, `__pycache__/` | Generated | Re-created by the steps below |

## Reproducing

`VERIFY.md` (Japanese) describes the procedure in detail. In short, from a copy of this repository and with Python 3.13:

```sh
python3.13 -m venv /path/to/env
/path/to/env/bin/python -m pip install -r requirements-analysis.txt
/path/to/env/bin/python scripts/reproduce.py --out /path/outside/this/repository --config config/reproduction.json --max-seconds 1740
```

The single entry point recomputes all 70 analysis tables from the saved forecasts in 44 stages, re-renders `paper.md` and the figures, and compares every table cell with the saved tables (relative tolerance 1e-9, absolute 1e-11). It needs no network, no AI API and no model weights, and it requires the source to be a Git checkout without tracked edits. In the run it took about 20 minutes on an Apple-silicon Mac with 4 threads. Re-running the model inference additionally needs the weights (above); see `VERIFY.md` §5.

The English tables are regenerated with `preprint/make_tables_tex.py` (see `preprint/README.md`).

## Licences

- **Code — MIT License** (`LICENSE`). This covers the source code written for this study (`scripts/`, `config/`, and the scripts in `preprint/`).
- **Data and text — CC BY 4.0** (`LICENSE-CC-BY-4.0.txt`). This covers analysis outputs, forecasts, logs, research records, manuscripts and figures. Attribution: cite the preprint (`CITATION.cff`).
- **Third-party material keeps its original licence.** The AMELAG data and documents (Robert Koch-Institut and Umweltbundesamt) and the New Zealand wastewater data and documents (PHF Science, formerly ESR) are CC BY 4.0; model configuration files and model cards in `data/models/` are Apache-2.0. `data/NOTICE.md` gives the attributions and citations that the data providers require or recommend, and the modifications.

## Citation

See `CITATION.cff`.
