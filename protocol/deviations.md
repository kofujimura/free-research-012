# 計画の改訂と逸脱

- v1→v2：E004の仕様監査の後、予測を行う前に確定。参照版を「56日後の最初」から「56日後までの最新」へ変更。公表の空白のため参照値が選択的に欠けることを避け、情報の締切を固定する。列の対応、モデル、較正、強い比較を具体化した。日時・event_idはevents.jsonlのplan_finalized参照。
- 予備調査のモデル動作確認は実測1分未満だったが、外側の明示的タイムアウトを付けなかった。既に記録済みの逸脱。主要実験は全てランナーで制限する。
- E001で失敗したGitコマンドのstderrは実装の不備で保存できず、原因は不明。後続E003ではstderrを保存し、部分クローンのcommit-graph不整合と確認した。全原TSVはE004で取得完了した。予測の証拠を消したものではない。

- 2026-10-18T16:32:02Z EV0063: v3、予測前。初期版の毎日値と2026-05-20の金曜日ラベルを週次水曜と混同せず、最新の適格版へ戻る規則を追加。E005を失敗として保持。ETSは記述の加法誤差に合わせAZNに固定。

- 2026-10-18T16:47:06Z EV0100: 主要結果後の探索的追加をextension-national-v1.mdに事前記載。情報更新の分解、共通基準日、季節性を含む従来比較、上昇定義への感度。主要分析は保持する。

- 2026-10-18T17:42:55Z: 多施設/NZの推論前の実装具体化。最低16実観測は保持した入力期間内でも満たす。主要386入力を点検し全て適格、主要予測・結果への変更なし。

2026-10-18T17:52:15Z NZ v2: E025 input failure on merge-marker rows; reject whole malformed release pair and use latest eligible predecessor before forecasting. No NZ forecast scores inspected.

2026-10-18T21:59:55Z: 用語の訂正：RKIのBestimmungsgrenzeは定量下限（LOQ）であり、過去の計画で使った「検出限界」は不正確だった。数値・標識の定義・層分けは変えず、論文では定量下限へ修正した。旧計画は保持。入力履歴とfloat32の同一性も区別した。対応eventはevents.jsonlのterminology_correction。

2026-10-18T22:17:16Z: E096の補完層に代表入力メタデータを使った誤りを検出。公開版ごとのケース来歴へ修正しE097で再計算する（input-quality-audit-v2）。数値入力同一性・主要予測・全標本損失は変更しない。measurement_issue_detected / measurement_correction_planned参照。

EV0462: 共同評価期間・複数比較への探索的な感度を追加。主要・交互作用の結果を見た後であり、事前の主要仮説とはしない。定義はjoint-comparison-sensitivity-v1。

2026-10-19T04:51:29Z: REVIEW-1後に予測距離≤2/≥3の層別と同じ方法の情報年齢比をE144で追加。境界は査読者の事後提案。主要結果は維持。病原体別は事前計画の既存出力を本文に昇格。計画protocol/review-response-v1.md。
