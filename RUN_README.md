# 下水監視の予測と公表情報の新しさ

試行`free-research-012`。ドイツ全国の実公表履歴を使った主要解析と、ドイツ地点・ニュージーランド・指標定義・比較方法への探索的な拡張である。公開済みの集計データだけを用い、患者データや人間参加者の実験は含まない。外部公開は行っていない。

論文は[paper.md](paper.md)、主張と証拠の対応は[claims.jsonl](claims.jsonl)、実施範囲・失敗・利用量は[final_report.md](final_report.md)、提出前の点検は[review/self-check.md](review/self-check.md)。査読状態は論文冒頭と実施報告を参照する。最終版では人間から伝達された1回のAIエージェントによる査読に対応した。[回答書](review/response-1.md)を参照。

保存した予測から主要な数値と図を再計算する単一の入口は`scripts/reproduce.py`である。**研究ディレクトリの複製から実行し、出力先をその複製の外に指定する。** 手順と検証範囲、APIを使わない再計算、原データからの追加再実行の違いは[VERIFY.md](VERIFY.md)に記した。

`protocol/`は計画と改訂、`experiments/`は成功・失敗を含む実行と未加工予測・分析・学習モデル、`data/`は公開元と固定版、`literature/`は資料確認の記録、`sources.jsonl`は確認範囲付きの出典索引である。`events.jsonl`とローカルGitは研究の順序を追う索引であり、独立した不変監査ログではない。

データの再利用条件はAMELAG（Robert Koch-Institut・Umweltbundesamt）およびNZ（PHF Science、旧ESR）のCC BY 4.0であり、取得時のライセンスを同梱した。モデル重みは各公式リポジトリのApache 2.0。これらの権利表示を保持する。地域・地点の比較は定義や観測頻度・欠測が異なり、個別組織の順位や非難を示すものではない。

Git管理外の大きな汎用モデル重みは、保存出力の検証には不要である。初稿の固定版はsubmission-1、改訂最終版はfinalタグから参照する。再現の出力を原本へ書き戻さない。
