"""Derive counts, API accounting and the final-report inventory from saved records."""
import argparse,collections,datetime as dt,json,pathlib,subprocess
from decimal import Decimal
from api_wrapper import costs
from record import ROOT

def stamp(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def lines(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--facts',default='paper-facts.json');ap.add_argument('--phase',default='in_progress');args=ap.parse_args();out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);manifest=json.loads((ROOT/'manifest.json').read_text());observed=dt.datetime.now(dt.timezone.utc);runs=[json.loads(p.read_text()) for p in sorted((ROOT/'experiments').glob('E*/run.json'))];events=lines(ROOT/'events.jsonl');interventions=lines(ROOT/'interventions.jsonl');calls={r['call_id']:r for r in lines(ROOT/'api_calls.jsonl')};api=[];total=Decimal(0)
    for call in calls.values():
        response=json.loads((ROOT/call['response_path']).read_text());fee,detail=costs(response)
        if fee is None:raise ValueError('Cannot verify actual API charge for '+call['call_id'])
        assert fee==Decimal(str(call['cost_usd']));total+=fee;api.append(dict(call_id=call['call_id'],purpose=call['purpose'],model_requested=call['model_requested'],model_returned=call['model_returned'],status=call['status'],usage=call['usage'],cost_usd=str(fee),cost_detail=detail))
    assert total<=Decimal(str(manifest['api']['budget_usd']));paused=sum(x['excluded_seconds'] for x in manifest['quota_pauses']);wall=(observed-stamp(manifest['start_at_utc'])).total_seconds();storage=int(subprocess.check_output(['du','-sk',str(ROOT)],text=True).split()[0])*1024
    failed=[r for r in runs if r['status'] not in ['completed','running']];counts=collections.Counter(r['status'] for r in runs);native=collections.Counter()
    for p in (ROOT/'experiments').glob('E*/forecasts.jsonl'):
        for line in p.read_text().splitlines():
            if line.strip():native[json.loads(line)['model']]+=1
    model_records=[]
    for p in (ROOT/'experiments').glob('E*/model-records.jsonl'):model_records.extend(lines(p))
    current_models=[r for r in model_records if r['status']=='completed'];unique_models={(r['feature_matrix_sha256'],r['issue_date']) for r in current_models};facts=json.loads((ROOT/args.facts).read_text()) if (ROOT/args.facts).exists() else None
    result=dict(observed_at_utc=observed.isoformat(),phase=args.phase,trial_id=manifest['trial_id'],start_at_utc=manifest['start_at_utc'],draft_deadline_utc=manifest['draft_deadline_utc'],wall_elapsed_seconds=wall,quota_excluded_seconds=paused,research_elapsed_seconds=wall-paused,storage_bytes_du=storage,experiment_counts=dict(counts),failed_experiments=failed,event_counts=dict(collections.Counter(e['type'] for e in events)),intervention_counts=dict(collections.Counter(e['type'] for e in interventions)),api_calls=api,api_unique_model_requests=len(calls),api_actual_cost_usd=str(total),native_saved_prediction_records=dict(native),pooled_completed_weekly_fits=len(current_models),pooled_quantile_estimators=len(current_models)*9,session_id=manifest.get('session_id'),continuation_session_ids=manifest.get('continuation_session_ids',[]),review=manifest.get('review',{}),host_usage_and_marginal_tool_costs_observable=False,invoice_reconciliation_performed=False)
    draft_submission=manifest.get('draft_submission',{});review_info=manifest.get('review',{});draft_end=draft_submission.get('submitted_at_utc')
    result['draft_submission']=draft_submission
    if manifest.get('final_submission'):result['final_submission']=manifest['final_submission']
    if draft_end:
        draft_wall=(stamp(draft_end)-stamp(manifest['start_at_utc'])).total_seconds();result.update(draft_wall_elapsed_seconds=draft_wall,research_elapsed_seconds=draft_wall-paused)
    if review_info.get('received_at_utc'):
        received=stamp(review_info['received_at_utc']);end=stamp(manifest['final_submission']['submitted_at_utc']) if manifest.get('final_submission',{}).get('submitted_at_utc') else observed
        review_excluded=sum(x['excluded_seconds'] for x in review_info.get('quota_pauses',[]));result.update(review_response_wall_elapsed_seconds=(end-received).total_seconds(),review_response_elapsed_seconds=(end-received).total_seconds()-review_excluded,review_response_deadline_utc=review_info['response_deadline_utc'],review_waiting_seconds=(received-stamp(draft_end)).total_seconds() if draft_end else None,review_quota_excluded_seconds=review_excluded,review_response_elapsed_scope='First review tool clock to report/final submission, excluding confirmed review quota intervals; waiting for initial review is separate.')
    result.update(elapsed_accounting_is_conservative_upper_bound=manifest.get('elapsed_accounting_is_conservative_upper_bound',False),actual_active_elapsed_seconds=None,pooled_unique_feature_matrix_issue_weeks=len(unique_models),pooled_repeated_weekly_fits=len(current_models)-len(unique_models),model_fit_count_scope='Experiments/E*/model-records.jsonl only; verification workspace refits are reported separately.')
    verification_fits=[]
    for directory in (ROOT/'.verify-work').glob('output*'):
        for name in ['site_first_refit','nz_first_refit']:
            path=directory/name/'model-records.jsonl'
            if path.exists():verification_fits.extend(x for x in lines(path) if x['status']=='completed')
    result.update(verification_completed_weekly_refits=len(verification_fits),verification_quantile_estimators_fitted=len(verification_fits)*9,verification_fit_count_scope='Both saved verification attempts; each first-week fitting invocation counted even when its resulting bytes match earlier fits.')
    response_path=ROOT/'review/response-1.json'
    if args.phase=='final' and response_path.exists():
        response=json.loads(response_path.read_text());result['review_response']=dict(review_id=response['review_id'],comment_count=len(response['comments']),decision_counts=dict(collections.Counter(x['decision'] for x in response['comments'])),claims_with_scope_changes=response['claims_with_scope_changes'],claims_with_status_changes=response['claims_with_status_changes'],withdrawn_claims=response['withdrawn_claims'],new_claims=response['new_claims'],additional_analysis_experiments=response['additional_analysis_experiments'],full_verification_status=response['full_verification_status'],reviewer_execution_directly_observed=False)
        proof=ROOT/'review/final-verification-result.json'
        if proof.exists():result['final_verification']=json.loads(proof.read_text())
    (out/'execution-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    status='最終版・AIエージェントによる査読対応済み' if args.phase=='final' else '初稿の提出準備中' if args.phase=='in_progress' else '初稿・AIエージェントによる査読待ち'
    text=['# 実施報告',f'\n状態：{status}。集計基準時刻：{observed.isoformat()}。集計は保存記録から自動生成した。', '\n## テーマと実施範囲','\n研究質問は、古い実公表情報を入力する汎用時系列予測が、最新情報を入力する従来予測と比べて、下水指標の濃度と上昇をどこまで再現するかである。ドイツ全国を主要解析、地点・NZ・非正規化SARS・追加従来法・共有学習・区間較正・参照版と時刻代理の感度を探索的検証とした。主張と範囲はpaper.mdとclaims.jsonlを参照。']
    if facts:
        text.extend(['\n## 確認できた主要結果','\n最新の3方法固定合成を参照とする主要の1週前入力のWIS比は、Chronos-Boltで'+facts['main']['c1']['ratio_ci']+'、公開後のTimesFMで'+facts['main']['t1']['ratio_ci']+'。同等性・非劣性は立証していない。追加比較の結果も含め、有利な条件だけを選んで主要結果に置換していない。'])
    if args.phase=='final' and facts and facts.get('review_facts'):
        r=facts['review_facts']['chronos_bolt_base|1|fresh_horizon_le2|fresh_ensemble'];t=facts['review_facts']['timesfm_2p5|1|fresh_horizon_le2|fresh_ensemble']
        text.append('\n査読後の探索的な追加では、最新参照の予測距離2週以下の組に限ると、1週前入力の比はChronos-Bolt '+r['ratio_ci']+'（'+str(int(r['n_pairs']))+'組）、TimesFM '+t['ratio_ci']+'（'+str(int(t['n_pairs']))+'組）だった。この境界は事後提案で、区間は多重比較未調整。休止期を含む全体平均を、短い予測距離での置換可能性の根拠にはできない。')
    text.extend(['\n## 未検証と限界','\n真のウイルス量、患者の感染数、入院、臨床警報、実利用者の判断・費用対効果は測定していない。Git時刻は公表時刻の代理。参照は後日の公開値で最終真値ではない。国・地点は独立した流行ではなく、国や組織の順位として解釈できない。事前学習データとの過去の重複は全て確認できていない。探索的な追加と主要計画は区別した。', '\n## 実行・失敗','\n実験・取得・検証の実行記録の状態別件数：`'+json.dumps(dict(counts),ensure_ascii=False)+'`。保存された未補正予測レコード数（相関・再利用があり独立試行数ではない）：`'+json.dumps(dict(native),ensure_ascii=False)+'`。実験記録上の共有学習は'+str(len(current_models))+'発行週の学習、特徴行列と発行週の異なる組は'+str(len(unique_models))+'組、再学習は'+str(len(current_models)-len(unique_models))+'回。対応する分位点推定器の学習回数は'+str(len(current_models)*9)+'。通し実行の作業場所での再学習はこの件数に含めず、別記する。','\n失敗した実行は消去していない。']+['\n- '+r['experiment_id']+'：'+r['status']+'、終了コード'+str(r.get('returncode'))+'。`experiments/'+r['experiment_id']+'/run.json`'+('とstderr.txtを参照。' if (ROOT/'experiments'/r['experiment_id']/'stderr.txt').exists() else 'を参照。stderr原文のファイル保存はなく、記録上の欠落として扱う。') for r in failed])
    text.extend(['\n## 介入・資源・利用量','\n人間介入の種類別件数：`'+json.dumps(result['intervention_counts'],ensure_ascii=False)+'`。利用枠による停止を除外した時間は'+str(paused)+'秒。停止中に動いた実験はmanifest.jsonに記録。確認できた総容量は'+str(storage)+'bytes（du）。このセッションの正確なモデル識別子、推論設定、セッションID、通常のツール・モデルのトークン使用量と限界費用は取得できていない。','\n## AI API費用','\nモデル要求は'+str(len(calls))+'回。状態確認と会計訂正の追記を重複して数えない。料金表と保存usageから算定した実績は'+str(total)+'米ドル。請求明細との照合はしていない。料金表はliterature/openai-pricing.md、キャッシュ書込みの公式計算定義はliterature/reading-cache-accounting-official.json。以前の2.25286米ドルという記録は書込み料金の計算漏れであり、旧行を残して訂正した。'])
    for c in api:text.append('\n- '+c['model_returned']+'／'+c['purpose']+'：入力'+str(c['usage']['input_tokens'])+'（通常'+str(c['cost_detail']['ordinary_input_tokens'])+'、キャッシュ読込み'+str(c['cost_detail']['cached_input_tokens'])+'、書込み'+str(c['cost_detail']['cache_write_tokens'])+'）、出力'+str(c['usage']['output_tokens'])+'（内数の思考'+str(c['cost_detail']['reasoning_tokens'])+'）、検索'+str(c['cost_detail']['web_search_calls'])+'回、算定実績'+c['cost_usd']+'米ドル。失敗要求なし。')
    text.extend(['\n## 記録上の制限と終了状態','\ninput_prompt.mdは不完全な手動転記で、既知の欠落をmanifest.jsonに明示し、初期化後は変更していない。E006を完了と誤って記した過去のイベントは、直後の訂正イベントで失敗と訂正した。候補選定の未採用C02では最寄り文献の一つの本文にアクセスできず、完全確認とは扱っていない。API会計の書込みトークン漏れも追記訂正した。記録は独立した不変監査ログではない。','\n初稿を査読待ちとして提出する場合、査読は未実施であり最終版ではない。初稿提出後はREVIEW-1または査読を行わない旨の通知まで研究ディレクトリを変更しない。','\n## 主要成果物','\n- paper.md：論文。\n- claims.jsonl：主張・証拠・検証手順。\n- VERIFY.md：保存出力からのオフライン再計算と時系列の検証。\n- review/self-check.md：提出前の自己点検。\n- protocol/：事前計画と探索的な改訂。\n- experiments/：成功・失敗・未加工予測・分析結果・学習モデル。\n- SHA256SUMS.json：成果物ハッシュ一覧（記載した除外範囲を参照）。\n- '+str(out/'execution-summary.json')+'：この報告の機械可読集計。'])
    text.extend(['\n## 追加の訂正と検証状態','\n入力品質のE096は数値入力を共用する代表メタデータに依存したため、公開版ごとの実測/補完の来歴を取り違える例があった。E097でケースごとの来歴へ修正し、旧結果と修正差の集計をreview/input-quality-correction-check.jsonに残した。主要全標本の予測と損失は変わっていない。履歴長の入力準備E098は参照版フィルターの不一致で予測前に失敗し、修正したE099を使った。','\n2回目の利用枠停止は人間が確認したが、再開直後の時刻出力が履歴圧縮で参照できなかった。代理の停止区間と記録欠落をmanifest.jsonに明示し、不確かな時間延長は利用せず、以前に確認済みの作業期限を維持した。'])
    text.append('\n通し実行の初回E141は、品質2表のデータセット処理順が元の表と異なり、最後の厳密な行順照合で失敗した。全64表はデータセットを整列した診断では数値・ラベルが一致したが、初回を成功には変更していない。v2で設定の処理順を修正し、期待表・数値解析・許容差を変えず、空の別出力先で全段階を再試行した。初回出力は全て保存し、計算後に全バイト一致を確認した重複だけを不変の実験成果物とハードリンクで共用した。対応はreview/verification-deduplication.jsonにある。')
    text.append('\n検証作業場所で実行した追加の最初の発行週の学習は、記録から'+str(len(verification_fits))+'回、対応する分位点推定器は'+str(len(verification_fits)*9)+'回だった。元の実験記録上の学習回数とは分けた。同じ入力・週の再学習であり、異なる流行や独立した検証例の件数ではない。')
    if facts and facts.get('joint_facts'):
        selected=facts['joint_facts']['selected'];parts=[]
        for model,label in [('chronos_bolt_base','Chronos-Bolt'),('timesfm_2p5','TimesFM')]:
            r=selected['Germany|national|'+model+'|ratio_of_freshness_ratios'];parts.append(label+f" {r['value']:.3f} [{r['simultaneous_low']:.3f}, {r['simultaneous_high']:.3f}]")
        text.append('\n共同期間・複数比較の探索的点検では、全国・固定3方法・1週前の相対的な損失増の比の比は'+ '、'.join(parts)+'（国ごと32統計量の同時区間）。どちらも1を含むため、頑健性の優位を確証したとはしない。元の主要解析と公称区間は保持した。')
    if facts and facts.get('history_facts'):
        parts=[]
        for model,label in [('chronos_bolt_base','Chronos-Bolt'),('timesfm_2p5','TimesFM')]:
            r=facts['history_facts']['nz|national|ensemble|'+model];parts.append(label+f"の比較対象で {r['reference_long_short_ratio']:.3f} [{r['reference_long_short_ratio_low']:.3f}, {r['reference_long_short_ratio_high']:.3f}]")
        text.append('\n最大104週/256週の探索的感度も行った。NZ全国では最新従来の長い/短い平均WIS比が'+ '、'.join(parts)+'であり、比較の比の改善には参照損失が増えた条件も含む。汎用だけを長くして短い最新参照を固定した比較と区別した。')
    full_check=ROOT/'review/full-site-aggregation-check.json'
    if full_check.exists():
        c=json.loads(full_check.read_text());text.append('\n追加の全保存版確認は'+str(len(c['source_versions']))+'版・'+str(c['series_checked'])+'系列・'+str(c['weekly_values_checked'])+'週集計値。最大絶対対数差'+format(c['max_absolute_log_difference'],'.3g')+'、定量下限標識差'+str(c['max_absolute_floor_flag_difference'])+'、日付と実測日数は一致した。同じ研究者の別実装であり、独立再現や生物学的な正解の確認ではない。')
    text.extend(['\n## 終了理由と残作業','\n主要解析、代替説明、強い比較、別の公表制度、履歴長、複数比較、全保存版の入力確認と通し再実行を終えた。容量が上限に近いため新規実験を終了し、初稿を固定して提出する。残るのは人間が別のAIエージェントを実行・伝達する1回の査読と、その後の対応である。外部公開は行っていない。'])
    verification=ROOT/'review/verification-result.json'
    if verification.exists():text.append('\n通し実行の結果：`'+json.dumps(json.loads(verification.read_text()),ensure_ascii=False)+'`。同じ研究者による保存出力の再計算であり、第三者の独立再現ではない。')
    else:text.append('\n通し実行の結果ファイルはこの集計時点では未作成。完了扱いにしない。')
    if args.phase=='final':
        text=[x.replace('初稿を査読待ちとして提出する場合、査読は未実施であり最終版ではない。初稿提出後はREVIEW-1または査読を行わない旨の通知まで研究ディレクトリを変更しない。','初稿の提出後は作業を停止し、REVIEW-1の受領後に対応を再開した。1回のAIエージェントによる査読に対応した改訂最終版である。').replace('容量が上限に近いため新規実験を終了し、初稿を固定して提出する。残るのは人間が別のAIエージェントを実行・伝達する1回の査読と、その後の対応である。','査読後に保存予測からの層別と表示・解釈を改訂し、追加の通し再実行を行った。容量と時間の範囲内で最終版を固定して研究を終了する。未検証の臨床効果と費用対効果、取得不能な文献本文は残る。') for x in text]
        if result.get('review_response'):
            r=result['review_response'];text.extend(['\n## 査読対応の集計','\n人間から伝達されたAIエージェントによる査読は1回。指摘'+str(r['comment_count'])+'件、判断別の件数は`'+json.dumps(r['decision_counts'],ensure_ascii=False)+'`。範囲を明確にした主張は'+ '、'.join(r['claims_with_scope_changes'])+'、status変更'+str(len(r['claims_with_status_changes']))+'件、撤回'+str(len(r['withdrawn_claims']))+'件、追加は'+ '、'.join(r['new_claims'])+'。追加解析は'+ '、'.join(r['additional_analysis_experiments'])+'。回答の全文はreview/response-1.md。', '\n査読後の予測距離2週以下の解析は探索的で、境界も査読者の事後提案による。元の主要結果は更新空白を含む平均であることを明記し、病原体別と同じ方法の情報の古さの損失を本文で表示した。新しい予測の推論とAI API要求は追加していない。Kalahastiの文献本文は403で未確認と明示した。'])
        text.append('\n時間の集計では、初稿までの研究期間、査読待ち、査読対応を分けた。研究期間の除外後経過は'+str(result['research_elapsed_seconds'])+'秒（不確かな2回目停止を除外しない保守的上限）、査読待ち'+str(result.get('review_waiting_seconds'))+'秒、査読対応の集計時点の経過'+str(result.get('review_response_elapsed_seconds'))+'秒。査読対応期限は'+str(result.get('review_response_deadline_utc'))+'。査読対応の確認済み利用枠停止の除外は'+str(result.get('review_quota_excluded_seconds'))+'秒。')
        if result.get('final_verification'):text.append('\n改訂後の自己再実行の実測：`'+json.dumps(result['final_verification'],ensure_ascii=False)+'`。初稿の自己再実行と、人間が伝達した査読者の再実行を区別する。独立再現とはしない。')
    (out/'final_report.md').write_text('\n'.join(text)+'\n');print(json.dumps(dict(experiments=len(runs),states=dict(counts),api_requests=len(calls),api_actual_cost_usd=str(total),storage_bytes_du=storage),ensure_ascii=False))

if __name__=='__main__':main()
