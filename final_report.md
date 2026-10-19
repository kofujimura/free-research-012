# 実施報告

状態：最終版・AIエージェントによる査読対応済み。集計基準時刻：2026-10-19T06:38:53.569317+00:00。集計は保存記録から自動生成した。

## テーマと実施範囲

研究質問は、古い実公表情報を入力する汎用時系列予測が、最新情報を入力する従来予測と比べて、下水指標の濃度と上昇をどこまで再現するかである。ドイツ全国を主要解析、地点・NZ・非正規化SARS・追加従来法・共有学習・区間較正・参照版と時刻代理の感度を探索的検証とした。主張と範囲はpaper.mdとclaims.jsonlを参照。

## 確認できた主要結果

最新の3方法固定合成を参照とする主要の1週前入力のWIS比は、Chronos-Boltで1.039 [0.915, 1.163]、公開後のTimesFMで1.023 [0.932, 1.155]。同等性・非劣性は立証していない。追加比較の結果も含め、有利な条件だけを選んで主要結果に置換していない。

査読後の探索的な追加では、最新参照の予測距離2週以下の組に限ると、1週前入力の比はChronos-Bolt 1.127 [1.034, 1.222]（253組）、TimesFM 1.054 [0.954, 1.170]（228組）だった。この境界は事後提案で、区間は多重比較未調整。休止期を含む全体平均を、短い予測距離での置換可能性の根拠にはできない。

## 未検証と限界

真のウイルス量、患者の感染数、入院、臨床警報、実利用者の判断・費用対効果は測定していない。Git時刻は公表時刻の代理。参照は後日の公開値で最終真値ではない。国・地点は独立した流行ではなく、国や組織の順位として解釈できない。事前学習データとの過去の重複は全て確認できていない。探索的な追加と主要計画は区別した。

## 実行・失敗

実験・取得・検証の実行記録の状態別件数：`{"failed": 8, "completed": 137, "failed_before_launch": 1}`。保存された未補正予測レコード数（相関・再利用があり独立試行数ではない）：`{"chronos_bolt_base": 23406, "naive": 14378, "damped_trend": 14378, "autoarima": 14378, "autoets": 14378, "ensemble": 14378, "timesfm_2p5": 23406, "autotheta": 14027, "seasonal_naive": 14027, "harmonic_arima": 14027}`。実験記録上の共有学習は117発行週の学習、特徴行列と発行週の異なる組は115組、再学習は2回。対応する分位点推定器の学習回数は1053。通し実行の作業場所での再学習はこの件数に含めず、別記する。

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

人間介入の種類別件数：`{"runtime_resume": 3, "peer_review": 1}`。利用枠による停止を除外した時間は8519秒。停止中に動いた実験はmanifest.jsonに記録。確認できた総容量は9923416064bytes（du）。このセッションの正確なモデル識別子、推論設定、セッションID、通常のツール・モデルのトークン使用量と限界費用は取得できていない。

## AI API費用

モデル要求は1回。状態確認と会計訂正の追記を重複して数えない。料金表と保存usageから算定した実績は2.2708675米ドル。請求明細との照合はしていない。料金表はliterature/openai-pricing.md、キャッシュ書込みの公式計算定義はliterature/reading-cache-accounting-official.json。以前の2.25286米ドルという記録は書込み料金の計算漏れであり、旧行を残して訂正した。

- gpt-6-astra／Authorized one-time critique of five topic candidates; user section 2.1 step 6：入力118991（通常111788、キャッシュ読込み0、書込み7203）、出力18659（内数の思考10464）、検索13回、算定実績2.2708675米ドル。失敗要求なし。

## 記録上の制限と終了状態

input_prompt.mdは不完全な手動転記で、既知の欠落をmanifest.jsonに明示し、初期化後は変更していない。E006を完了と誤って記した過去のイベントは、直後の訂正イベントで失敗と訂正した。候補選定の未採用C02では最寄り文献の一つの本文にアクセスできず、完全確認とは扱っていない。API会計の書込みトークン漏れも追記訂正した。記録は独立した不変監査ログではない。

初稿の提出後は作業を停止し、REVIEW-1の受領後に対応を再開した。1回のAIエージェントによる査読に対応した改訂最終版である。

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

検証作業場所で実行した追加の最初の発行週の学習は、記録から6回、対応する分位点推定器は54回だった。元の実験記録上の学習回数とは分けた。同じ入力・週の再学習であり、異なる流行や独立した検証例の件数ではない。

共同期間・複数比較の探索的点検では、全国・固定3方法・1週前の相対的な損失増の比の比はChronos-Bolt 0.882 [0.766, 1.017]、TimesFM 0.940 [0.816, 1.083]（国ごと32統計量の同時区間）。どちらも1を含むため、頑健性の優位を確証したとはしない。元の主要解析と公称区間は保持した。

最大104週/256週の探索的感度も行った。NZ全国では最新従来の長い/短い平均WIS比がChronos-Boltの比較対象で 1.115 [1.071, 1.167]、TimesFMの比較対象で 1.111 [1.078, 1.183]であり、比較の比の改善には参照損失が増えた条件も含む。汎用だけを長くして短い最新参照を固定した比較と区別した。

追加の全保存版確認は79版・157系列・1246056週集計値。最大絶対対数差8.88e-16、定量下限標識差0.0、日付と実測日数は一致した。同じ研究者の別実装であり、独立再現や生物学的な正解の確認ではない。

## 終了理由と残作業

主要解析、代替説明、強い比較、別の公表制度、履歴長、複数比較、全保存版の入力確認と通し再実行を終えた。査読後に保存予測からの層別と表示・解釈を改訂し、追加の通し再実行を行った。容量と時間の範囲内で最終版を固定して研究を終了する。未検証の臨床効果と費用対効果、取得不能な文献本文は残る。外部公開は行っていない。

通し実行の結果：`{"observed_at_utc": "2026-10-19T03:29:33Z", "status": "completed", "successful_experiment": "E142-offline-clean-checkout-retry", "successful_source_commit": "834f84dc39144ca72bc28686018889bee5ab725b", "stages": 43, "tables": 64, "table_rows": 177911, "max_absolute_numeric_difference": 0.0, "relative_tolerance": 1e-09, "absolute_tolerance": 1e-11, "claims": 12, "claim_evidence_rows": 60, "elapsed_seconds": 1165.2253657910042, "source_input_files_checked": 2186, "source_inputs_unchanged": true, "source_tracked_edits_after": false, "full_not_quick": true, "first_attempt_status": "failed", "first_attempt_reason": "Only dataset traversal order in two quality tables; failure and all outputs preserved", "first_attempt_records": "review/verification-attempt-1", "successful_records": "review/verification-attempt-2", "independent_reproduction": false, "existing_dependency_environment_reused": true, "git_objects_shared": true, "first_duplicate_outputs_shared_only_after_computation": true, "api_required": false, "network_required": false, "manuscript_bytes_match_saved_analysis_render": true}`。同じ研究者による保存出力の再計算であり、第三者の独立再現ではない。

## 査読対応の集計

人間から伝達されたAIエージェントによる査読は1回。指摘8件、判断別の件数は`{"採用": 7, "一部採用": 1}`。範囲を明確にした主張はCL01、CL02、CL04、status変更0件、撤回0件、追加はCL13、CL14。追加解析はE144-post-review-horizon-strata。回答の全文はreview/response-1.md。

査読後の予測距離2週以下の解析は探索的で、境界も査読者の事後提案による。元の主要結果は更新空白を含む平均であることを明記し、病原体別と同じ方法の情報の古さの損失を本文で表示した。新しい予測の推論とAI API要求は追加していない。Kalahastiの文献本文は403で未確認と明示した。

時間の集計では、初稿までの研究期間、査読待ち、査読対応を分けた。研究期間の除外後経過は36325.0秒（不確かな2回目停止を除外しない保守的上限）、査読待ち2694.0秒、査読対応の集計時点の経過2636.0秒。査読対応期限は2026-10-19T07:54:57+00:00。査読対応の確認済み利用枠停止の除外は4561秒。

改訂後の自己再実行の実測：`{"observed_at_utc": "2026-10-19T05:12:21Z", "status": "completed", "phase": "post_review", "successful_experiment": "E145-post-review-full-replay", "successful_source_commit": "5d3c82a4330063f3375570afedf4ef4ba8b30346", "stages": 44, "tables": 70, "table_rows": 178110, "max_absolute_numeric_difference": 0.0, "relative_tolerance": 1e-09, "absolute_tolerance": 1e-11, "claims": 14, "claim_evidence_rows": 96, "elapsed_seconds": 1169.4420761670917, "source_input_files_checked": 2661, "source_inputs_unchanged": true, "source_tracked_edits_after": false, "full_not_quick": true, "manuscript_bytes_match_saved_analysis_render": true, "figures": [{"path": "figures/national-model-information.png", "sha256": "5426769f10bdb0f956a8d5dd623200b5300236a47a1445c125ca21198885535b", "regenerated_bytes_match": true}, {"path": "figures/national-model-information.svg", "sha256": "9c966159a0133f81ed5c0d5e06b89a5fcad624f4c00b761e60674f2dbda03706", "regenerated_bytes_match": true}, {"path": "figures/generalization-one-week.png", "sha256": "189e816470429596793456beec76f634e4809798f4918af77f6549ee2e18e5d5", "regenerated_bytes_match": true}, {"path": "figures/generalization-one-week.svg", "sha256": "7f5844f562ea02f95299fb961ce60df860524f8475bf0a23b2a453c0d7f41888", "regenerated_bytes_match": true}], "independent_reproduction": false, "existing_dependency_environment_reused": true, "git_objects_shared": true, "immutable_source_input_files_shared": true, "replay_outputs_started_empty": true, "api_required": false, "network_required": false, "initial_verification_record_preserved": "review/verification-result.json", "archive": "review/final-verification", "full_replay_manuscript_match_scope": "Paper and figures at full replay source5d3c82a; later definition/caption/reference-only changes verified separately by E146", "final_publication_check": {"observed_at_utc": "2026-10-19T05:13:46Z", "status": "completed", "source_commit": "4885e58dcc561a8c65586c6ee9c443f0be17b81b", "analysis_manifest": ".verify-work/output-final/report-manifest.json", "scope": "Presentation-only regenerated from E145 recalculated analysis tables; numerical algorithms and expected tables unchanged", "files": [{"path": "paper.md", "sha256": "81b166c208f3d799df407e910b9a5ead51b312e895a2fe51dfa20858fada8dce", "bytes_match": true}, {"path": "figures/national-model-information.png", "sha256": "e8c6f1b3c5841bb5463819f2db1404cb7de84ee2ce62e8311f061c4e5a52fdcc", "bytes_match": true}, {"path": "figures/national-model-information.svg", "sha256": "75da518f4c554aa95df775bb0ba3521b935298e65173a11d410b42df167a67b0", "bytes_match": true}, {"path": "figures/generalization-one-week.png", "sha256": "189e816470429596793456beec76f634e4809798f4918af77f6549ee2e18e5d5", "bytes_match": true}, {"path": "figures/generalization-one-week.svg", "sha256": "7f5844f562ea02f95299fb961ce60df860524f8475bf0a23b2a453c0d7f41888", "bytes_match": true}], "claims": 14, "evidence_rows": 96, "new_prediction_inference": false, "new_model_fitting": false, "independent_reproduction": false}, "final_publication_experiment": "E146-final-publication-check", "final_publication_inputs_checked": 321, "final_publication_inputs_unchanged": true, "final_publication_source_commit": "4885e58dcc561a8c65586c6ee9c443f0be17b81b", "final_manuscript_and_figures_match_recalculated_data": true, "completed_stage_storage_sharing_record": "review/final-replay-completed-stage-sharing.json", "all_completed_stage_bytes_preserved": true}`。初稿の自己再実行と、人間が伝達した査読者の再実行を区別する。独立再現とはしない。

## 最終提出記録

最終版タグ `final`、提出コミット `81164f32eb6b653835fe382422585beb5cf6e38c`。提出をツールで確認した時刻は 2026-10-19T06:38:53Z（2026-10-19T15:38:53+09:00）。`final-record` はこの実コミットID・時刻と集計・ハッシュを記録する管理用コミットであり、論文、主張、数値入力、図は `final` と同じ。全作業を終了した。保全が必要なセッションIDは取得できず null。
