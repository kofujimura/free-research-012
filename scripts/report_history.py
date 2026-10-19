"""Manuscript history-length tables, including the unchanged-input denominator."""
import pandas as pd

def render(paths,table,f):
    if 'history' not in paths:return dict(history_results='履歴長の追加計算は未完了。',history_appendix='',history_facts={})
    d=pd.read_csv(paths['history']/'comparisons.csv',float_precision='round_trip');s=d[(d.source_age_weeks==1)&(d.period=='all_test')&(d.stratum=='all')&(d.metric=='wis')&(d.block_weeks==8)];facts={};main=[];extra=[]
    def band(r,k):return f(r[k])+' ['+f(r[k+'_low'])+', '+f(r[k+'_high'])+']'
    names={'national':'ドイツ全国','site':'ドイツ地点','nz':'NZ'};models={'chronos_bolt_base':'Chronos-Bolt','timesfm_2p5':'TimesFM'};refs={'ensemble':'3方法固定合成','ensemble_extended':'6方法固定合成','rolling_best_classical':'過去成績選択','pooled_hgb':'共有学習（履歴は固定）'}
    for dataset,levels in [('national',['national']),('site',['site']),('nz',['national','regional'])]:
        for level in levels:
            for model,label in models.items():
                for ref,refname in refs.items():
                    g=s[(s.dataset==dataset)&(s.unit_level==level)&(s.model==model)&(s.reference_model==ref)]
                    if g.empty:
                        assert ref=='pooled_hgb' and dataset=='national';continue
                    assert len(g)==1;r=g.iloc[0].to_dict();facts[dataset+'|'+level+'|'+ref+'|'+model]=r
                    row=[names[dataset]+'・'+level,label,refname,str(int(r['n_pairs'])),str(int(r['candidate_extended_count'])),band(r,'baseline_ratio'),band(r,'extended_candidate_ratio'),band(r,'extended_both_ratio'),band(r,'candidate_long_short_ratio'),band(r,'reference_long_short_ratio')]
                    (main if ref=='ensemble' else extra).append(row)
    headers=['対象','1週前の汎用','最新の参照','共通例','汎用の履歴が延長','短い両者 WIS比','汎用だけ長い WIS比','長い両者 WIS比','汎用の長い/短い損失比','最新従来の長い/短い損失比']
    compare_headers=[headers[i] for i in [0,1,3,4,5,6,7]];change_headers=[headers[i] for i in [0,1,3,8,9]]
    text='探索的に最大104週と256週の入力を比較した。公表版、観測終端、対象週、予測距離と56日参照は同じで、長短の汎用と長短の最新従来の4予測が揃う対象に限定した。TimesFMは短長とも推論設定の最大入力長256で計算したため、「短い両者」も元の主要表と設定が完全に同じとは限らない。以下は最新の固定3方法を参照に、1週前入力、未補正、全テスト期間、モデル公開後、8週ブロックで比較する。\n\n'+table(compare_headers,[[r[i] for i in [0,1,3,4,5,6,7]] for r in main])+'\n\n候補と最新従来それぞれの損失の変化も同じ対象で示す。\n\n'+table(change_headers,[[r[i] for i in [0,1,3,8,9]] for r in main])+'\n\n履歴を延ばしていない例も分母に含むため、延長件数を併記した。入力が元から104週以下で数値列が不変な条件の一致は整合性点検であり、長い履歴の効果とは数えない。全ての参照、延長した群、観測終端延長群、2026年、MAE、4/8/12週ブロックは保存した。'
    r=facts['nz|national|ensemble|chronos_bolt_base'];t=facts['nz|national|ensemble|timesfm_2p5'];text+='\n\nNZ全国の固定3方法との比較では、両者を長くした場合の比はChronos-Bolt '+band(r,'extended_both_ratio')+'、TimesFM '+band(t,'extended_both_ratio')+'だった。一方、最新従来の長い/短い損失比はそれぞれ'+band(r,'reference_long_short_ratio')+'、'+band(t,'reference_long_short_ratio')+'で、参照側の損失も増えている。汎用だけを長くし短い最新参照を固定した列と区別する。比較の比が下がったことだけを、汎用モデルが古い情報をよりよく補えた証拠としない。'
    compatibility=pd.read_csv(paths['history']/'original-short-compatibility.csv',float_precision='round_trip');rows=[]
    for r in compatibility.to_dict('records'):rows.append([names[r['dataset']],models[r['model']],str(int(r['n_pairs'])),format(r['max_quantile_absolute_difference'],'.3g'),str(int(r['changed_predictions_over_1e7'])),format(r['mean_wis_new_minus_old'],'.3g')])
    appendix=table(headers[:8],[r[:8] for r in extra])+'\n\n全参照の分子・分母それぞれの長短損失比もcomparisons.csvに保存した。共有学習は既存の最新104週特徴・学習モデルを固定した補足参照で、両者の履歴長を揃えた比較ではない。各従来成分も固定した直近窓を使うものは、その窓を変えていない。\n\n元の短い入力の予測との互換性を、較正用期間も含む同じ条件で点検した。\n\n'+table(['対象','汎用','照合予測数','分位点の最大絶対差','最大差1e-7超の予測数','平均WISの新−旧'],rows)+'\n\nこれは同じ研究者による数値点検であり独立再現ではない。モデル間のバッチやTimesFMの推論設定の違いも含む。主要結果を新しい予測で上書きしていない。最大256週は固定した感度条件で、最適な履歴長や全ての利用可能履歴を保証するものではない。'
    return dict(history_results=text,history_appendix=appendix,history_facts=facts)
