# 検証手順

この文書は、研究ディレクトリを変更せずに提出コミットの複製で検証するための手順である。保存出力の再計算はオフラインで行え、AI APIも汎用モデルの大きな重みも要らない。自分による通し実行は`review/verification-result.json`に記録する。第三者による独立した再現とは呼ばない。

## 1. 複製と環境

提出コミット（初稿はタグ`submission-1`）を、検証用の別の場所に複製する。以下の`/path/to/...`は利用者が選ぶパスに置き換える。原本の中でインストール・解析しない。Git管理された原データと保存予測、学習済みの小さな共有モデルは複製に含まれる。

```sh
git clone --no-hardlinks /path/to/run-012 /path/to/verification/checkout
git -C /path/to/verification/checkout checkout --detach submission-1
python3.13 -m venv /path/to/verification/environment
/path/to/verification/environment/bin/python -m pip install --cache-dir /path/to/verification/pip-cache -r /path/to/verification/checkout/requirements-analysis.txt
```

環境構築だけは公開パッケージの配布元へのネットワークを使う。利用した版は`requirements-analysis.txt`、推論を含む全環境は`requirements-lock.txt`にある。Mac arm64・Python 3.13で実行した。別のOS・数値ライブラリでの完全一致は未確認である。環境が既にあれば再インストールは不要。

## 2. 単一の再計算入口

```sh
/path/to/verification/environment/bin/python /path/to/verification/checkout/scripts/reproduce.py --out /path/to/verification/output --config config/reproduction.json --max-seconds 1740
```

出力先はソースの複製の外にする。スクリプトはソース内への出力を拒否し、キャッシュも出力先に置き、APIキーを子プロセスの環境から除く。各段階のコマンド、終了コード、実測時間、stdout/stderrは出力先の`verification-run.json`と各段階のログに残る。上限は29分であり、超えた場合は成功扱いにしない。

`config/reproduction.json`が、各段階、入力、再計算する表と保存済みの期待表を列挙する。図は同じ再計算表から作り直す。`expected-comparison.json`で**表の全行・全列**を照合し、数値の許容差は相対`1e-9`・絶対`1e-11`とする。丸めた本文の文字列だけを比べる手順ではない。本文の数値は`scripts/render_paper.py`が解析表から生成する。

全段階が30分を超える環境では、同じコマンドに`--quick`を加える。縮小版で除く段階は設定の`large_optional`で明示し、主張の主要表、図、元の主要解析は維持する。縮小版に含まれない区間補正や大きな補足解析まで再計算したとは扱わない。実測の内訳と縮小版の範囲は通し実行後の記録を参照する。

## 3. 主張ごとの証拠

機械可読な数値・条件・期待出力は`claims.jsonl`にある。元の保存値を別のAPI呼び出しで再生成する必要はない。

| 内容 | 元の証拠と再計算の段階 |
| --- | --- |
| 事前計画の濃度・上昇比較 | `experiments/E011-primary-analysis/results/`。`primary`段階が元の保存分位点から再計算する。 |
| 6方法合成・過去成績選択 | `experiments/E022-extra-analysis-fixed/results/`。`extended`段階。 |
| 改訂と観測追加、基準週からの変化 | `experiments/E018-update-decomposition/results/`。`updates`段階。恒等式は発見ではなく整合性点検。 |
| ドイツ地点、NZ全国・地域 | `experiments/E072-site-panel-analysis/results/`、`experiments/E044-nz-panel-analysis/results/`。`site`・`nz`段階。系列数は独立事例数ではない。 |
| 非正規化SARSと正規化指標の同じ対象での比較 | `experiments/E052-raw-sars-analysis/results/`、`experiments/E053-matched-raw-normalized/results/`。`raw`・`indicator`段階。 |
| 参照版と時刻代理 | `experiments/E038-reference-and-timing-sensitivity/results/`、`experiments/E076-shifted-timing-analysis/results/`。`sensitivity`・`shifted`段階。実配信時刻を証明するものではない。 |
| 共有学習の比較 | `experiments/E079-site-pooled-analysis/results/`、`experiments/E081-nz-pooled-analysis/results/`。保存した週別モデルと学習行の再点検を含む。 |
| 上昇のROC・追加比率・区間補正 | 設定の`growth_*`・`cqr_*`段階。元の全国2倍ROCと探索的な追加を区別する。臨床効果の検証ではない。 |
| 共同期間・複数比較への感度 | `experiments/E140-joint-comparison-sensitivity/results/`。`joint`段階。国ごとの限定した32統計量であり、全論文の同時被覆ではない。 |
| 古い/最新の相対的な損失増 | `experiments/E093-national-freshness-interaction/`、`E094-nz-freshness-interaction/`、`E095-site-freshness-interaction/`のresults。`interaction_*`段階で同じ対象の4予測を共同再抽出する。 |
| 入力の精度・補完条件 | 正式な訂正版は`experiments/E097-input-quality-case-provenance/results/`。`quality`段階。E096の代表メタデータによる補完層別は採用しない。 |
| 最大104週/256週の共通対象比較 | `history_native`段階で全6パネルを保存分位点から組み立て、`history`段階で4予測の共通例を再比較する。TimesFMの短い入力の互換性も別表に残す。 |

再計算の標準入力は固定したデータ版、作成済みの入力列、保存済みのモデル分位点である。大型モデルの推論を再度走らせたときの完全一致は要求しない。モデル公開後の解釈期間、ネイティブと較正、共通標本は設定と結合キーで分かれている。

`claims`段階は再生成した表の各該当行を、`claims.jsonl`に登録したフィルターと期待値で照合する。主張ごとの数値照合だけなら、`python scripts/verify_claims.py --out /path/outside/checkout/claim-check.json`を使える。これは元の表の照合であり、未加工分位点からの再計算は上の単一入口で行う。

## 4. 原データと時間の点検

`verify_temporal.py`は別の標準ライブラリ実装で、入力列のハッシュ、7日間隔、入力締切、予測距離、参照のGit日時と成熟締切を確認する。`verify_site_weekly.py`は別実装で6系列・4公開版の日別から週別への集計を照合する。既定のこの照合は標本による縮小検証である。別途、末尾の追加手順で全保存版・全コホート系列も照合した。元の照合結果は`experiments/E026-site-aggregation-check/`のsummary.jsonとrun.jsonを参照する。

原TSV・CSVのURL、取得日時、ライセンス、ハッシュは`data/downloads.jsonl`、実験の索引、`sources.jsonl`にある。サイトデータは無損失gzip、週集計はParquetで保存した。元の不適格な曜日版、日付にマージ印を含むNZの不適格版も残した。参照値が欠けた例を埋めて予測成績を作らない。

全原データからやり直す任意手順では、さらに別の書込み可能な作業用複製を用意し、入力準備と推論の各`experiments/E*/run.json`に記録された子コマンド・計画コミット・コードコミット・入力SHAを使う。出力先`RESEARCH_EXPERIMENT_DIR`は作業用複製の新しいディレクトリにして、原本や提出済み実験IDへ書き込まない。取得・入力準備の一部は複製のルートからの相対パスを索引に記録する実装である。研究期間の期限を強制する`run_experiment.py`を査読時に呼ぶ必要はない。地点週集計・全推論は30分を超えうるため、元の5入力チャンクのように子コマンドを各30分以下に分ける。主要表の再計算とは別の任意手順である。

## 5. 推論・学習の再実行とAPI

汎用モデルの公開重み2つはGit管理外で、`data/models/weight-publication-metadata.json`と各カードにリポジトリ、固定リビジョン、重みSHA、ライセンスがある。重みを原本から読み取り専用で複製するか、公式公開リポジトリの指定リビジョンから取得する。後者はネットワークが必要であり、保存出力の再計算には含めない。

推論は`generate_forecasts.py`、追加従来法は`extra_baselines.py`。seed、CPU・スレッド数、分位点、バッチ、コンテキスト長、TimesFMの設定をrun.json・計画・コードと揃える。全ての予測を再生成しなくても、例えば最初の16入力の縮小推論と、保存出力から全表を再計算する検証を区別して行える。縮小推論は全予測の再生成とは呼ばない。

共有学習は`train_pooled.py`で12発行週以下ずつ再学習できる。保存モデルの`train_indices`・`predict_indices`とハッシュを照合し、各学習行の56日成熟締切が発行より前であること、保存モデルによる9分位点が一致することを`verify_pooled.py`が点検する。追加の最初の1発行週の再学習も、既存モデルの再生と分けて記録する。

AI APIの実験測定は行っていない。1回のテーマ候補批判の要求・全応答・usage・検索回数と会計訂正は`api/`と`api_calls.jsonl`に保存した。最新のcall_id別記録から集計し、状態確認や訂正の行を重複課金として数えない。`scripts/api_wrapper.py`の純粋な費用計算と`api/accounting-self-check-v2.json`で保存JSONから費用を確認でき、APIキーや追加呼び出しは不要。成功済みの批判を検証目的で再送しない。

## 6. 時系列・逸脱・ハッシュ

`git log --reverse --format=fuller`と`events.jsonl`の計画・コミット・実験開始/終了を照合する。各実験のrun.jsonは実行時の計画ファイル、計画とコードのコミット、入力SHAを持つ。主要計画はv1→v2→v3の順で予測前、追加計画は主要結果後の探索的分析である。改訂の索引は`protocol/deviations.md`と各計画にある。

E006の完了という誤記はEV0071で失敗と訂正した。API費用の書込み分の漏れはEV0281以降の追記で訂正した。既存行を消して整えた記録ではない。Git日時は自己申告で、改ざん不能や第三者による独立性を証明しない。

E096の補完来歴の誤りはE097で修正した。全標本の損失が不変であることと、層別で変わった行数は`review/input-quality-correction-check.json`で分かる。履歴長の準備E098は参照版の不一致を検出して失敗し、E099で修正した。2回目の利用枠停止では正確な停止区間を復元できず、不確かな期限延長を使わなかった。再開までに先頭2ジョブが完了したことは確認できるが、正確な停止開始後の完了とは断定しない。

自己点検用の作業場所は`.verify-work/`で、元のGitオブジェクトを共有する複製を使う。容量を抑えるため、既定手順が読まない生TSV版と、再生成前提のケース中間表・推論用バッチを作業ツリーから省く。数値検証が読まない予備実験のtiny重みとPDF本文も作業ツリーから省く。文献本文の確認は別途自己点検で行い、原本とGitには保存する。対象は`review/sparse-checkout-patterns.txt`、見積りは`review/verification-space-plan.json`にある。原本やGit履歴からデータを削除する操作ではない。必要な4公開版の生データ、全保存分位点、共有モデル、入力列、全期待表は含む。これは全生データの別実装による再処理や独立再現とは異なる。

最終の`SHA256SUMS.json`は大型モデル重みも含む成果物一覧であり、自己参照する一覧、Git・仮想環境・キャッシュ・通し実行の作業場所を除く。Git管理外の重みを持たない複製では、次でGit管理対象だけを照合できる。

```sh
/path/to/verification/environment/bin/python /path/to/verification/checkout/scripts/verify_artifacts.py verify --tracked-only --out /path/to/verification/hash-check.json
```

ハッシュ一致は同じバイト列の確認であり、研究の正しさ・独立性・改ざん不能の証明ではない。

## 7. 自己再実行の実測

全手順の再試行は19.42分で終了した（同じMac・4スレッド・既存依存環境）。43段階・64表・総177911行の全セルで一致し、最大絶対数値差は0.0だった。表の行数は独立した流行例の数ではない。主張12件の60根拠行、入力/コードの不変、論文と図のバイト一致も確認した。詳細はreview/verification-result.json。

初回の失敗は入力品質2表のデータセット処理順であり、厳密照合の条件を緩めず、生成設定の順序を修正して全段階を再実行した。初回出力とログは保全し、計算後にバイト一致が確認された重複コピーだけを不変の元成果物とハードリンクで共用した。新しい出力先は空の状態から計算した。入力環境の新規インストールは別途未検証で、自己実行は既存環境を再利用した。

提出タグsubmission-1は論文・証拠の固定版を指す。実際の提出コミットIDを記録する管理用追記がある場合はsubmission-1-recordタグに保存する。追記は提出情報・ログ・集計・ハッシュだけで、論文・主張・数値入力は動かさない。提出タグと管理用記録を区別して確認する。

## 8. 全保存版の追加集計チェック

E143では全79版・157系列の1246056週集計値を標準ライブラリによる別実装で照合し、最大絶対対数差8.88e-16、標識差0.0、日付・実測日数は一致した。自己実行の所要時間は1.23分。これは同じ研究者の追加検証である。

全79版の原TSVと対応Parquetを含む通常の完全な提出コミット複製から、出力先をその複製の外へ指定する。自己実行のsparse複製に省いた75原TSVも、この任意手順には必要である。原本では全て保存しGit管理している。

```sh
mkdir -p /path/to/verification/full-weekly
RESEARCH_EXPERIMENT_DIR=/path/to/verification/full-weekly /path/to/verification/environment/bin/python /path/to/verification/checkout/scripts/verify_site_weekly.py --all-series --all-versions
```

期待値は上記と`review/full-site-aggregation-check.json`。標準の43段階は変更しておらず、この追加は数値解析や元の期待表を変更しない。

SHA256SUMS-check.jsonはハッシュ一覧の自己点検結果であり、自己参照を避けるためSHA256SUMS接頭辞の除外に含む。提出タグの一覧はタグ版で、後の管理用記録の一覧はその管理用タグで確認する。
