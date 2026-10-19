#!/usr/bin/env python3
"""Generate the English LaTeX tables of the preprint from the run's saved analysis outputs.

Usage (from any directory; needs pandas, numpy and jinja2 as in requirements-analysis.txt):
    python -I -B preprint/make_tables_tex.py   (-B: write no .pyc; -I ignores PYTHON* variables)

What it does:
1. Rebuilds every table of the original manuscript with the run's own functions in
   scripts/render_paper.py (and the report_* modules), reading the analysis CSVs listed in
   config/report-results.json. Numbers are formatted by the run's code, from unrounded CSV values.
2. Re-renders paper.template.md and asserts that the result is byte-identical to paper.md, so every
   cell below equals the cell of the original (Japanese) manuscript.
3. Translates the Japanese labels with the fixed dictionary below; numeric cells pass through
   unchanged (only LaTeX escaping and typographic minus/dash signs are applied).
4. Writes preprint/arxiv/tables/tab_*.tex (tabular only; captions are in main.tex).

tab_extended.tex additionally carries the 0- and 2-week values for the exploratory references that
the original manuscript showed only in a figure (figures/national-model-information.*). They are read
from the same comparisons.csv with the same filters as the figure script (scripts/plot_results.py).
Nothing outside preprint/arxiv/tables/ is written.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "preprint" / "arxiv" / "tables"
sys.path.insert(0, str(ROOT / "scripts"))
import render_paper as rp  # noqa: E402  (run's own renderer; ROOT resolves to this release)
from jinja2 import Environment, StrictUndefined  # noqa: E402

# --- 1. rebuild the original context exactly as scripts/render_paper.py main() does ---------------
calls = []
_orig_table = rp.table


def recording_table(headers, rows):
    md = _orig_table(headers, rows)
    calls.append((list(headers), [[str(c) for c in r] for r in rows], md))
    return md


rp.table = recording_table
mapping = json.loads((ROOT / "config/report-results.json").read_text())
paths = {k: ROOT / v for k, v in mapping.items()}
ctx = {**rp.primary_context(paths), **rp.extension_context(paths), **rp.data_context(), **rp.panel_context(paths)}
ctx.update(
    publication_status="初稿作成中・未査読",
    maturity_results=rp.maturity_context(paths),
    critique_provenance="モデルはgpt-6-astra、利用日は2026-10-18で、批判の全文と応答JSONを保存した。批判で挙がった事実は別途確認し、確認できなかったものを根拠に使わなかった。",
    verification_status="初稿の通し実行は`review/verification-result.json`、改訂後の全体再実行と最終の論文・図の照合は`review/final-verification-result.json`に記録した。いずれも同じ研究者による再実行であり独立した再現ではない。",
    references=rp.references(),
    discussion_empirical="全国の比較は、モデルの種類だけでなく、入力の更新状態、従来法の選び方、後日参照する濃度の尺度に依存した。これらを分けた比較を、モデル更新とデータ更新を検討する際の評価設計に使える。ただし、本研究は両者の費用や現場の運用への効果を測っていない。",
    appendices="全ての較正条件、4/8/12週ブロック、病原体、対象位置、2026年、参照版、入力の関係による結果は各解析出力にある。これらを有利な条件だけ選んで主要結果に置き換えない。追加の上昇比率、ROC、定量下限標識、欠測・範囲外、時刻代理の感度の出力も再現手順から参照できる。",
)
ctx.update(rp.extension_tables(paths, rp.select, recording_table, rp.f, rp.ci, rp.ROOT))
ctx["table_primary_auxiliary"] = rp.primary_auxiliary(paths, recording_table, rp.f, rp.ROOT)
ctx.update(rp.render_interaction(paths, recording_table, rp.f))
ctx.update(rp.render_history(paths, recording_table, rp.f))
ctx.update(rp.joint_render(paths, recording_table, rp.f))
ctx["publication_status"] = "最終版・AIエージェントによる査読1回に対応済み"
ctx.update(rp.render_review(paths, recording_table, rp.f, rp.ci, rp.select))
if ctx["additional_abstract"]:
    ctx["abstract_exploratory"] = ctx["additional_abstract"]
if ctx.get("history_facts"):
    ctx["abstract_exploratory"] += "地点・ニュージーランドへの拡張と最大256週の履歴の感度でも一様な改善はなく、比較の比が下がった条件には最新従来の損失が増えた場合もあった。"
env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
paper = env.from_string((ROOT / "paper.template.md").read_text()).render(**ctx)

# --- 2. the rebuilt manuscript must equal the run's paper.md byte for byte -------------------------
original = (ROOT / "paper.md").read_text()
assert paper == original, "re-rendered paper differs from paper.md; tables would not match the manuscript"


def jp_units(s):  # same replacements as the jp_units macro of paper.template.md
    for a, b in [("ドイツ全国・national", "ドイツ全国"), ("ドイツ地点・site", "ドイツ地点"), ("ニュージーランド・national", "NZ全国"),
                 ("ニュージーランド・regional", "NZ地域"), ("NZ・national", "NZ全国"), ("NZ・regional", "NZ地域"),
                 ("germany_national・national", "ドイツ全国"), ("germany_sites・site", "ドイツ地点"), ("nz・national", "NZ全国"),
                 ("nz・regional", "NZ地域")]:
        s = s.replace(a, b)
    return s


placed = []
for headers, rows, md in calls:
    pos = original.find(md)
    if pos < 0:
        pos = original.find(jp_units(md))
    if pos >= 0:
        placed.append((pos, headers, rows))
placed.sort(key=lambda x: x[0])
assert len(placed) == original.count("\n| --- |"), "every manuscript table must be captured exactly once"

# Output names in manuscript order, with the first header and row count as a guard against reordering.
ORDER = [
    ("tab_primary", "候補", 9), ("tab_information", "候補（1週前）", 6), ("tab_pathogens", "方法", 12),
    ("tab_horizons", "予測方法", 6), ("tab_own_age", "方法（同じ方法の最新入力を1）", 3), ("tab_alerts", "予測", 8),
    ("tab_auxiliary", "予測", 8), ("tab_extended", "最新の参照", 4), ("tab_pub_gaps", "前の全国ファイル更新日", 3),
    ("tab_identity_weeks", "発行週", 13), ("tab_horizon_distribution", "最新参照の予測距離（週）", 9),
    ("tab_nz_intervals", "NZの公表間隔（暦日）", 9), ("tab_panel", "対象", 18), ("tab_pooled", "対象", 6),
    ("tab_interaction", "対象", 16), ("tab_history", "対象", 8), ("tab_history_losses", "対象", 8),
    ("tab_anchored", "候補（1週前）", 8), ("tab_update_contrib", "予測器", 6), ("tab_maturity", "候補（1週前）", 8),
    ("tab_input_reference_matrix", "入力履歴（Chronos-Bolt・最新）", 4), ("tab_site_strata", "候補（1週前）", 14),
    ("tab_indicator", "最新の参照", 6), ("tab_timing", "対象", 12), ("tab_calibration", "対象", 24),
    ("tab_availability", "対象（1週前入力）", 3), ("tab_unique_inputs", "対象", 3), ("tab_float32", "対象（1週前入力）", 4),
    ("tab_imputation", "ドイツ地点の候補（1週前）", 20), ("tab_history_refs", "対象", 22), ("tab_history_compat", "対象", 6),
    ("tab_joint_summary", "比較群", 6), ("tab_joint", "対象", 16),
]
assert len(ORDER) == len(placed)
for (name, first, n), (_, headers, rows) in zip(ORDER, placed):
    assert headers[0] == first and len(rows) == n, (name, headers[0], len(rows))

# --- 3. translation -----------------------------------------------------------------------------
# Header translations; "\\" marks a line break inside a header cell.
HEAD = {
    "候補": "Candidate", "公表情報の年齢（週）": "Information\\\\age (weeks)", "ペア数": "Pairs", "発行週数": "Issue\\\\weeks",
    "WIS比 [95%区間]": "WIS ratio [95\\% interval]", "同一入力": "Identical\\\\input", "ほぼ同一予測": "Near-identical\\\\forecast",
    "既知の対象": "Known\\\\target", "候補（1週前）": "Candidate\\\\(1 week earlier)", "入力の関係": "Input relation",
    "方法": "Method", "期間": "Period", "病原体": "Pathogen", "最新入力": "Latest input", "1週前入力": "1 week earlier",
    "2週前入力": "2 weeks earlier", "予測方法": "Method", "条件": "Stratum",
    "方法（同じ方法の最新入力を1）": "Method (same method,\\\\latest input = 1)",
    "予測": "Forecast", "対象日−発行日（日）": "Target $-$ issue\\\\(days)", "通知可能例": "Evaluable\\\\cases",
    "2倍上昇例": "Doubling\\\\cases", "検出数": "Detected", "誤通知/非上昇": "False alerts /\\\\non-doublings",
    "誤通知率": "False-alert\\\\rate", "見逃し率": "Miss\\\\rate", "MAE": "MAE", "80%区間の被覆率": "80\\% interval\\\\coverage",
    "平均区間幅": "Mean interval\\\\width", "最新の参照": "Latest-input\\\\reference",
    "前の全国ファイル更新日": "Previous update of\\\\the national file", "次の更新日": "Next update", "間隔（暦日）": "Gap (calendar days)",
    "発行週": "Issue week", "Chronosの同一入力組数": "Chronos-Bolt\\\\identical-input pairs",
    "TimesFMの同一入力組数": "TimesFM\\\\identical-input pairs", "最新参照の予測距離（週）": "Horizon of the latest\\\\reference (weeks)",
    "Chronos標本数": "Chronos-Bolt\\\\cases", "うち同一入力": "of which\\\\identical input", "TimesFM標本数": "TimesFM\\\\cases",
    "NZの公表間隔（暦日）": "NZ publication interval (calendar days)", "件数": "Count",
    "対象": "Dataset", "1週前の候補": "Candidate\\\\(1 week earlier)", "系列数": "Series",
    "共通ペア数": "Common\\\\pairs", "最新の共有学習に対するWIS比 [95%区間]": "WIS ratio vs.\\ latest pooled\\\\model [95\\% interval]",
    "汎用モデル": "Pretrained\\\\model", "従来参照": "Classical\\\\reference", "4予測の共通例": "Cases with\\\\all 4 forecasts",
    "汎用の古い/最新": "Pretrained\\\\old/latest", "従来の古い/最新": "Classical\\\\old/latest",
    "比の比 [95%区間]": "Ratio of ratios\\\\[95\\% interval]", "古い汎用/最新従来": "Old pretrained /\\\\latest classical",
    "1週前の汎用": "Pretrained model\\\\(1 week earlier)", "共通例": "Common\\\\cases", "汎用の履歴が延長": "Pretrained history\\\\extended",
    "短い両者 WIS比": "Both short:\\\\WIS ratio", "汎用だけ長い WIS比": "Pretrained only long:\\\\WIS ratio",
    "長い両者 WIS比": "Both long:\\\\WIS ratio", "汎用の長い/短い損失比": "Pretrained long/short\\\\loss ratio",
    "最新従来の長い/短い損失比": "Latest classical long/short\\\\loss ratio", "評価条件": "Evaluation\\\\(stratum / metric)",
    "予測器": "Forecaster", "更新段階": "Update step", "WISの減少（対数濃度上）": "WIS reduction\\\\(log concentration)",
    "参照の時点（日）": "Reference\\\\vintage (days)", "入力履歴（Chronos-Bolt・最新）": "Input history\\\\(Chronos-Bolt, latest)",
    "参照": "Reference", "共通例数": "Common\\\\cases", "平均WIS": "Mean WIS",
    "最新3方法へのWIS比 [95%区間]": "WIS ratio vs.\\ latest fixed 3\\\\[95\\% interval]",
    "非正規化 WIS比": "Non-normalised:\\\\WIS ratio", "正規化 WIS比": "Normalised:\\\\WIS ratio",
    "比の差 [95%区間]": "Difference of ratios\\\\[95\\% interval]", "公開がGitより遅い仮定（時間）": "Assumed release\\\\after Git (hours)",
    "補正窓（過去例）": "Correction window\\\\(past cases)",
    "同じ補正の最新3方法へのWIS比 [95%区間]": "WIS ratio vs.\\ latest fixed 3, same\\\\correction [95\\% interval]",
    "対象（1週前入力）": "Dataset\\\\(1-week-earlier input)", "意図した条件": "Intended\\\\cases", "入力可": "Input\\\\available",
    "16週超で範囲外": "Out of range\\\\($>$16 weeks)", "その他の入力欠測": "Other missing\\\\input", "既知の対象週": "Known\\\\target week",
    "異なる入力数": "Distinct inputs", "定数列": "Constant series", "末尾2点が同じ": "Last two values equal",
    "入力を比較できる条件": "Comparable\\\\cases", "保存履歴で同一": "Identical\\\\(stored history)", "float32で同一": "Identical\\\\(float32)",
    "同じ日付・最大差1e-6以下": "Same dates,\\\\max.\\ diff.\\ $\\le$1e-6", "同じ日付・最大差0.01以下": "Same dates,\\\\max.\\ diff.\\ $\\le$0.01",
    "両入力に補完なし": "No imputation\\\\in either input", "ドイツ地点の候補（1週前）": "German-site candidate\\\\(1 week earlier)",
    "最新参照": "Latest reference", "入力の条件": "Input condition", "汎用": "Pretrained", "照合予測数": "Forecasts\\\\compared",
    "分位点の最大絶対差": "Max.\\ abs.\\ quantile\\\\difference", "最大差1e-7超の予測数": "Forecasts with\\\\max.\\ diff.\\ $>$1e-7",
    "平均WISの新−旧": "Mean WIS\\\\new $-$ old", "比較群": "Comparison\\\\family", "ブロック週数": "Block\\\\(weeks)",
    "同時に扱う統計量": "Statistics", "有効再抽出": "Valid\\\\resamples", "無効再抽出": "Invalid\\\\resamples",
    "通常区間が1を含まない本数": "Nominal intervals\\\\excluding 1", "同時区間が1を含まない本数": "Simultaneous intervals\\\\excluding 1",
    "統計量": "Statistic", "共同期間の通常区間": "Nominal interval\\\\(joint period)", "同時区間": "Simultaneous\\\\interval",
}
CELL = {
    "3方法固定合成": "Fixed 3-method", "6方法固定合成": "Fixed 6-method", "過去成績による選択": "Past selection",
    "過去成績選択": "Past selection", "共有学習": "Pooled model", "共有学習（履歴は固定）": "Pooled (history fixed)",
    "同一入力": "Identical input", "終端は同じ・改訂あり": "Same end, revised", "観測終端が延長": "Observation end extended",
    "同じ終端・改訂あり": "Same end, revised", "観測終端の延長": "Observation end extended",
    "観測終端の差が3週以上": "Observation-end difference $\\ge$3 weeks",
    "参照週の定量下限未満の標識割合0": "Below-LOQ flag share 0 in reference week", "参照週の同割合0.5以上": "Same share $\\ge$0.5",
    "テスト前に固定した2026年継続群": "2026 continuing cohort (fixed before test)",
    "全テスト": "Full test", "2026年": "2026", "インフルエンザA": "Influenza A",
    "最新参照の予測距離≤2週": "Horizon $\\le$2 weeks", "最新参照の予測距離≥3週": "Horizon $\\ge$3 weeks",
    "Chronos-Bolt・1週前": "Chronos-Bolt, 1 week earlier", "TimesFM・1週前": "TimesFM, 1 week earlier",
    "最新3方法（同標本）": "Latest fixed 3 (same cases)",
    "ドイツ全国": "Germany, national", "ドイツ地点": "Germany, sites", "NZ全国": "NZ, national", "NZ地域": "NZ, regional",
    "ドイツ全国・national": "Germany, national", "ドイツ地点・site": "Germany, sites", "ドイツ全国・all": "Germany, national",
    "ドイツ地点・all": "Germany, sites", "ニュージーランド・national": "NZ, national", "ニュージーランド・regional": "NZ, regional",
    "NZ・national": "NZ, national", "NZ・regional": "NZ, regional", "NZ・level:national": "NZ, national", "NZ・level:regional": "NZ, regional",
    "germany_national・national": "Germany, national", "germany_sites・site": "Germany, sites", "nz・national": "NZ, national",
    "nz・regional": "NZ, regional", "germany_national": "Germany, national", "germany_sites": "Germany, sites", "nz": "NZ",
    "Germany・全国": "Germany, national", "Germany・地点": "Germany, sites", "NZ・全国": "NZ, national", "NZ・地域": "NZ, regional",
    "all / wis": "all / WIS", "all / anchored_wis": "all / anchored WIS", "new_observations / wis": "new observations / WIS",
    "new_observations / anchored_wis": "new observations / anchored WIS", "revision": "revision", "new_observations": "new observations",
    "actual": "actual vintages", "finalized_prefix": "finalised prefix", "latest": "latest",
    "両入力に補完なし": "No imputation in either input", "両入力の補完割合0.1以下": "Imputed share $\\le$0.1 in both",
    "両入力の補完割合0.25以下": "Imputed share $\\le$0.25 in both", "いずれかの補完割合0.25超": "Imputed share $>$0.25 in either",
    "全対象": "All", "古い/最新の比の比": "Old/latest ratio of ratios", "古い汎用/最新従来": "Old pretrained / latest classical",
    "—": "---",
}
PASS = re.compile(r"^(Chronos-Bolt|TimesFM|SARS-CoV-2|RSV A/B|Germany|NZ|[0-9]{4}-[0-9]{2}-[0-9]{2})$")
NUMERIC = re.compile(r"^-?[0-9.]+(e-?[0-9]+)?( \[-?[0-9.]+, -?[0-9.]+\])?$|^[0-9]+/[0-9]+$|^[0-9]+〜[0-9]+$")


def num(s):
    s = s.replace("〜", "--")
    return re.sub(r"(^|\[|, )-(?=[0-9])", r"\1$-$", s)


def cell(s):
    if NUMERIC.match(s):
        return num(s)
    if s in CELL:
        return CELL[s]
    if PASS.match(s):
        return s
    raise KeyError("no translation for cell: " + s)


def head(s, align):
    t = HEAD[s].replace("\\\\[", "\\\\{}[")  # keep "\\[" from being read as a line-break skip
    return "\\hd%s{%s}" % (align, t) if "\\\\" in t else t


def tabular(headers, rows):
    cells = [[cell(c) for c in r] for r in rows]
    aligns = ["r" if all(NUMERIC.match(r[j]) or r[j] == "—" for r in rows) else "l" for j in range(len(headers))]
    lines = ["%% generated by preprint/make_tables_tex.py from the run's analysis outputs; do not edit by hand",
             "\\begin{tabular}{%s}" % "".join(aligns), "\\toprule",
             " & ".join(head(h, a) for h, a in zip(headers, aligns)) + " \\\\", "\\midrule"]
    lines += [" & ".join(r) + " \\\\" for r in cells]
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    text = "\n".join(lines)
    bad = sorted({c for c in text if ord(c) > 127})
    assert not bad, ("non-ASCII left in table", bad)
    return text


OUT.mkdir(parents=True, exist_ok=True)
written = []
for (name, _, _), (_, headers, rows) in zip(ORDER, placed):
    if name == "tab_extended":
        continue
    (OUT / (name + ".tex")).write_text(tabular(headers, rows), encoding="utf-8")
    written.append(name)

# --- 4. exploratory references with all three information ages (folded in from the figure) -------
ext_md = next(h_r for h_r in placed if h_r[1][0] == "最新の参照")
ext = rp.pd.read_csv(paths["extended"] / "comparisons.csv", dtype={"truth_lag": str})
rows = []
for reference in ["ensemble_extended", "rolling_best_classical"]:
    for model in ["chronos_bolt_base", "timesfm_2p5"]:
        by_age = {age: rp.select(ext, truth_lag="56", variant="native", period="all_test", stratum="all", metric="wis",
                                 block_weeks=8, reference_model=reference, model=model, source_age_weeks=age) for age in (0, 1, 2)}
        assert len({(r["n_pairs"], r["n_issue_weeks"]) for r in by_age.values()}) == 1, "pairs differ between ages"
        rows.append([rp.LABEL[reference], rp.LABEL[model], rp.integer(by_age[1]["n_pairs"]), rp.integer(by_age[1]["n_issue_weeks"]),
                     by_age[0]["ratio_ci"], by_age[1]["ratio_ci"], by_age[2]["ratio_ci"]])
# the 1-week column must equal the original manuscript's table cell by cell
assert [[r[0], r[1], r[2], r[5]] for r in rows] == ext_md[2], "1-week column differs from the manuscript table"
(OUT / "tab_extended.tex").write_text(tabular(["最新の参照", "候補", "ペア数", "発行週数", "最新入力", "1週前入力", "2週前入力"], rows), encoding="utf-8")
written.append("tab_extended")
print(json.dumps(dict(paper_md_reproduced=True, tables=len(written), out=str(OUT.relative_to(ROOT))), ensure_ascii=False))
