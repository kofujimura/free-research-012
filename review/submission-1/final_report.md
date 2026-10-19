# 実施報告

状態：初稿・AIエージェントによる査読待ち。集計基準時刻：2026-10-19T03:53:05.051673+00:00。集計は保存記録から自動生成した。

## テーマと実施範囲

研究質問は、古い実公表情報を入力する汎用時系列予測が、最新情報を入力する従来予測と比べて、下水指標の濃度と上昇をどこまで再現するかである。ドイツ全国を主要解析、地点・NZ・非正規化SARS・追加従来法・共有学習・区間較正・参照版と時刻代理の感度を探索的検証とした。主張と範囲はpaper.mdとclaims.jsonlを参照。

## 確認できた主要結果

最新の3方法固定合成を参照とする主要の1週前入力のWIS比は、Chronos-Boltで1.039 [0.915, 1.163]、公開後のTimesFMで1.023 [0.932, 1.155]。同等性・非劣性は立証していない。追加比較の結果も含め、有利な条件だけを選んで主要結果に置換していない。

## 未検証と限界

真のウイルス量、患者の感染数、入院、臨床警報、実利用者の判断・費用対効果は測定していない。Git時刻は公表時刻の代理。参照は後日の公開値で最終真値ではない。国・地点は独立した流行ではなく、国や組織の順位として解釈できない。事前学習データとの過去の重複は全て確認できていない。探索的な追加と主要計画は区別した。

## 実行・失敗

実験・取得・検証の実行記録の状態別件数：`{"failed": 8, "completed": 134, "failed_before_launch": 1}`。保存された未補正予測レコード数（相関・再利用があり独立試行数ではない）：`{"chronos_bolt_base": 23406, "naive": 14378, "damped_trend": 14378, "autoarima": 14378, "autoets": 14378, "ensemble": 14378, "timesfm_2p5": 23406, "autotheta": 14027, "seasonal_naive": 14027, "harmonic_arima": 14027}`。実験記録上の共有学習は117発行週の学習、特徴行列と発行週の異なる組は115組、再学習は2回。対応する分位点推定器の学習回数は1053。通し実行の作業場所での再学習はこの件数に含めず、別記する。

失敗した実行は消去していない。

- E001-vintage-audit：failed、終了コード1。`experiments/E001-vintage-audit/run.json`とstderr.txtを参照。

- E003-vintage-audit-retry：failed、終了コード1。`experiments/E003-vintage-audit-retry/run.json`とstderr.txtを参照。

- E005-prepare-inputs：failed、終了コード1。`experiments/E005-prepare-inputs/run.json`とstderr.txtを参照。

- E006-prepare-inputs-valid：failed、終了コード1。`experiments/E006-prepare-inputs-valid/run.json`とstderr.txtを参照。

- E021-extra-baseline-analysis：failed、終了コード1。`experiments/E021-extra-baseline-analysis/run.json`とstderr.txtを参照。

- E025-nz-panel-inputs：failed、終了コード1。`experiments/E025-nz-panel-inputs/run.json`とstderr.txtを参照。

- E067-site-c4-timesfm：failed_before_launch、終了コード1。`experiments/E067-site-c4-timesfm/run.json`を参照。stderr原文のファイル保存はなく、記録上の欠落として扱う。

- E098-history-length-inputs：failed、終了コード1。`experiments/E098-history-length-inputs/run.json`とstderr.txtを参照。

- E141-offline-clean-checkout：failed、終了コード1。`experiments/E141-offline-clean-checkout/run.json`とstderr.txtを参照。

## 介入・資源・利用量

人間介入の種類別件数：`{"runtime_resume": 2}`。利用枠による停止を除外した時間は8519秒。停止中に動いた実験はmanifest.jsonに記録。確認できた総容量は10596671488bytes（du）。このセッションの正確なモデル識別子、推論設定、セッションID、通常のツール・モデルのトークン使用量と限界費用は取得できていない。

## AI API費用

モデル要求は1回。状態確認と会計訂正の追記を重複して数えない。料金表と保存usageから算定した実績は2.2708675米ドル。請求明細との照合はしていない。料金表はliterature/openai-pricing.md、キャッシュ書込みの公式計算定義はliterature/reading-cache-accounting-official.json。以前の2.25286米ドルという記録は書込み料金の計算漏れであり、旧行を残して訂正した。

- gpt-6-astra／Authorized one-time critique of five topic candidates; user section 2.1 step 6：入力118991（通常111788、キャッシュ読込み0、書込み7203）、出力18659（内数の思考10464）、検索13回、算定実績2.2708675米ドル。失敗要求なし。

## 記録上の制限と終了状態

input_prompt.mdは不完全な手動転記で、既知の欠落をmanifest.jsonに明示し、初期化後は変更していない。E006を完了と誤って記した過去のイベントは、直後の訂正イベントで失敗と訂正した。候補選定の未採用C02では最寄り文献の一つの本文にアクセスできず、完全確認とは扱っていない。API会計の書込みトークン漏れも追記訂正した。記録は独立した不変監査ログではない。

初稿を査読待ちとして提出する場合、査読は未実施であり最終版ではない。初稿提出後はREVIEW-1または査読を行わない旨の通知まで研究ディレクトリを変更しない。

## 主要成果物

- paper.md：論文。
- claims.jsonl：主張・証拠・検証手順。
- VERIFY.md：保存出力からのオフライン再計算と時系列の検証。
- review/self-check.md：提出前の自己点検。
- protocol/：事前計画と探索的な改訂。
- experiments/：成功・失敗・未加工予測・分析結果・学習モデル。
- SHA256SUMS.json：成果物ハッシュ一覧（記載した除外範囲を参照）。
- execution-summary.json：この報告の機械可読集計。

## 追加の訂正と検証状態

入力品質のE096は数値入力を共用する代表メタデータに依存したため、公開版ごとの実測/補完の来歴を取り違える例があった。E097でケースごとの来歴へ修正し、旧結果と修正差の集計をreview/input-quality-correction-check.jsonに残した。主要全標本の予測と損失は変わっていない。履歴長の入力準備E098は参照版フィルターの不一致で予測前に失敗し、修正したE099を使った。

2回目の利用枠停止は人間が確認したが、再開直後の時刻出力が履歴圧縮で参照できなかった。代理の停止区間と記録欠落をmanifest.jsonに明示し、不確かな時間延長は利用せず、以前に確認済みの作業期限を維持した。

通し実行の初回E141は、品質2表のデータセット処理順が元の表と異なり、最後の厳密な行順照合で失敗した。全64表はデータセットを整列した診断では数値・ラベルが一致したが、初回を成功には変更していない。v2で設定の処理順を修正し、期待表・数値解析・許容差を変えず、空の別出力先で全段階を再試行した。初回出力は全て保存し、計算後に全バイト一致を確認した重複だけを不変の実験成果物とハードリンクで共用した。対応はreview/verification-deduplication.jsonにある。

検証作業場所で実行した追加の最初の発行週の学習は、記録から4回、対応する分位点推定器は36回だった。元の実験記録上の学習回数とは分けた。同じ入力・週の再学習であり、異なる流行や独立した検証例の件数ではない。

共同期間・複数比較の探索的点検では、全国・固定3方法・1週前の相対的な損失増の比の比はChronos-Bolt 0.882 [0.766, 1.017]、TimesFM 0.940 [0.816, 1.083]（国ごと32統計量の同時区間）。どちらも1を含むため、頑健性の優位を確証したとはしない。元の主要解析と公称区間は保持した。

最大104週/256週の探索的感度も行った。NZ全国では最新従来の長い/短い平均WIS比がChronos-Boltの比較対象で 1.115 [1.071, 1.167]、TimesFMの比較対象で 1.111 [1.078, 1.183]であり、比較の比の改善には参照損失が増えた条件も含む。汎用だけを長くして短い最新参照を固定した比較と区別した。

追加の全保存版確認は79版・157系列・1246056週集計値。最大絶対対数差8.88e-16、定量下限標識差0.0、日付と実測日数は一致した。同じ研究者の別実装であり、独立再現や生物学的な正解の確認ではない。

## 終了理由と残作業

主要解析、代替説明、強い比較、別の公表制度、履歴長、複数比較、全保存版の入力確認と通し再実行を終えた。容量が上限に近いため新規実験を終了し、初稿を固定して提出する。残るのは人間が別のAIエージェントを実行・伝達する1回の査読と、その後の対応である。外部公開は行っていない。

通し実行の結果：`{"observed_at_utc": "2026-10-19T03:29:33Z", "status": "completed", "successful_experiment": "E142-offline-clean-checkout-retry", "successful_source_commit": "834f84dc39144ca72bc28686018889bee5ab725b", "stages": 43, "tables": 64, "table_rows": 177911, "max_absolute_numeric_difference": 0.0, "relative_tolerance": 1e-09, "absolute_tolerance": 1e-11, "claims": 12, "claim_evidence_rows": 60, "elapsed_seconds": 1165.2253657910042, "source_input_files_checked": 2186, "source_inputs_unchanged": true, "source_tracked_edits_after": false, "full_not_quick": true, "first_attempt_status": "failed", "first_attempt_reason": "Only dataset traversal order in two quality tables; failure and all outputs preserved", "first_attempt_records": "review/verification-attempt-1", "successful_records": "review/verification-attempt-2", "independent_reproduction": false, "existing_dependency_environment_reused": true, "git_objects_shared": true, "first_duplicate_outputs_shared_only_after_computation": true, "api_required": false, "network_required": false, "manuscript_bytes_match_saved_analysis_render": true}`。同じ研究者による保存出力の再計算であり、第三者の独立再現ではない。
