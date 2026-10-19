# 指定モデルによる候補批判のAPI利用計画

用途は開始指示§2.1手順6の例外に限る。上位5候補について弱点を求め、テーマ・方法の作業を委任しない。論文やコードの作成・文献要約・解釈の相談には使わない。

- プロバイダー：OpenAI。指定モデル `gpt-6-astra`、`reasoning.effort=xhigh`。
- 入口：`scripts/api_wrapper.py`。Python SDKのResponses API。`background=True`、`tools=[{"type":"web_search"}]`、`include=["web_search_call.action.sources"]`。標準料金の `service_tier=default` を明示する。
- 回数：通常1回、失敗時を含め最大2回。SDK自動再送を0とし、既存の完了応答は再利用する。Web非対応が原因の失敗時のみ2回目をWebなしで送る。状態取得は回数に含めない。
- 入力：開始指示の批判依頼文をそのまま使い、候補ID・問い・方法・近い先行研究と差分だけを埋める。採点と採用意向を送らない。個人情報は送らない。
- 入出力トークンの最大と最大費用の事前確認：この1用途について開始指示が明示的に除外し、出力上限を設定しないよう要求しているため設定しない。見積もりを実績として記録しない。累計が予算に達した場合は追加呼び出しをしない。
- 料金：公式の料金表を取得し、標準の短文脈で入力$10/100万、キャッシュ済み入力$1/100万、出力$50/100万、Web検索$0.01/回を確認した。検索内容はモデル入力トークンとして課金される。思考トークンは出力使用量に含める。出典：`literature/openai-pricing.md`（元URL https://developers.openai.com/api/docs/pricing ）。確認日は2026-10-18 UTC（2026-10-19日本時間）。
- ローカルモデルで代替しない理由：この候補批判のモデルと設定は開始条件で指定されている。指定を利用できなければ別モデルに置換せず、未実施を記録する。
- 公式仕様：モデル、background、Web search、sourcesの公式ページを取得・確認した。`literature/openai-model-astra.md`、`openai-background.md`、`openai-web-search.md`。
- 利用規約：2026-01-01発効のOpenAI Services Agreementの制限、出力の権利、学習・改善への利用条件を公式本文で確認した（https://openai.com/policies/services-agreement/ ）。出力を競合モデルの学習に使わない。今回の出力は候補批判として保存・参照するだけ。APIデータの取扱いは公式ガイド `literature/openai-your-data.md` も確認。個別アカウントの契約・設定は読まず、一般条項の確認と区別する。
- 記録：リクエスト・応答JSON全体、返されたmodel、status、usage、検索回数、算出した費用を保存。`api_calls.jsonl` は同じcall_idの状態推移を追記するため、集計はcall_idごとに最後の行を採る。
- 解析：指摘を自分で確認し、採否と理由を追記。指摘文献の実在・内容を自分で検証する。順位や新テーマの提案は採否に使わない。未完応答だけで選定しない。待機をやめる場合はcancelする。
