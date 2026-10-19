"""Generate paired freshness/quality tables without selecting a winning setting."""
import pandas as pd

MODELS={'chronos_bolt_base':'Chronos-Bolt','timesfm_2p5':'TimesFM'}
REFS={'ensemble':'3方法固定合成','ensemble_extended':'6方法固定合成','pooled_hgb':'共有学習'}

def render(paths,table,f):
    def band(r,name):return f(r[name])+' ['+f(r[name+'_low'])+', '+f(r[name+'_high'])+']'
    result=dict(interaction_results='交互作用の集計は未完了。',quality_results='追加の入力品質点検は未完了。',interaction_facts={},quality_facts={},additional_abstract='')
    rows=[];facts={}
    for alias,name,levels in [('interaction_national','ドイツ全国',['national']),('interaction_site','ドイツ地点',['site']),('interaction_nz','NZ',['national','regional'])]:
        if alias not in paths:continue
        d=pd.read_csv(paths[alias]/'comparisons.csv',float_precision='round_trip');s=d[(d.source_age_weeks==1)&(d.period=='all_test')&(d.stratum=='information:new_observations')&(d.metric=='wis')&(d.block_weeks==8)]
        for level in levels:
            for reference in ['ensemble','ensemble_extended']:
                for model,label in MODELS.items():
                    q=s[(s.unit_level==level)&(s.reference_model==reference)&(s.model==model)];assert len(q)==1;r=q.iloc[0].to_dict();facts[alias+'|'+level+'|'+reference+'|'+model]=r
                    rows.append([name+'・'+level,label,REFS[reference],str(int(r['n_pairs'])),f(r['foundation_freshness_ratio']),f(r['classical_freshness_ratio']),band(r,'ratio_of_freshness_ratios'),f(r['replacement_ratio'])])
    if rows:
        result['interaction_results']='同じ対象の汎用・従来の古い/最新の4予測が揃い、観測終端が延長した群を示す。公表情報の年齢は1週、56日参照、未補正、全テスト期間、モデル公開後である。\n\n'+table(['対象','汎用モデル','従来参照','4予測の共通例','汎用の古い/最新','従来の古い/最新','比の比 [95%区間]','古い汎用/最新従来'],rows)+'\n\n比の比は1未満で、汎用モデルの相対的な損失増が小さい。同じ週を再抽出することで4予測を一緒に比較し、別々の区間の交差から交互作用を判断していない。ドイツ全国の固定3方法との比較では小さい値だったが、6方法やNZへの変更で一様な結果にはならなかった。同一入力で固定モデルの比が1になることは、整合性の点検であり経験的な発見ではない。\n\n過去成績選択・共有学習との全比較も保存した。これらの「古い」は数値履歴の締切を指し、選択・学習に使う情報全体を巻き戻した条件ではない。過去成績選択は、現在の入力が同じでも過去の成績から異なる成分を選びうる。'
        c=facts.get('interaction_national|national|ensemble|chronos_bolt_base');t=facts.get('interaction_national|national|ensemble|timesfm_2p5')
        if c and t:result['additional_abstract']='探索的に観測終端が延長した群の4予測を揃えると、全国の固定3方法に対する入力履歴の古さの損失比の比は'+band(c,'ratio_of_freshness_ratios')+'、'+band(t,'ratio_of_freshness_ratios')+'だった。相対的な損失増が小さいことと最新の別方法を代替できることは区別され、この関係は参照・国・地点を替えると一様ではなかった。'
        result['interaction_facts']=facts
    if 'quality' in paths:
        base=paths['quality'];d=pd.read_csv(base/'similarity-summary.csv',float_precision='round_trip');s=d[d.source_age_weeks==1];rows=[]
        for r in s.to_dict('records'):
            rows.append([r['dataset']+'・'+r['unit_level'],str(int(r['n_pairs'])),str(int(r['recorded_exact'])),str(int(r['float32_exact'])),str(int(r['same_grid_max_log_difference_le_1e-6'])),str(int(r['same_grid_max_log_difference_le_0.01'])),str(int(r['both_without_imputation']))])
        text=table(['対象（1週前入力）','入力を比較できる条件','保存履歴で同一','float32で同一','同じ日付・最大差1e-6以下','同じ日付・最大差0.01以下','両入力に補完なし'],rows)+'\n\nここでは後日の正解の有無で選ばず、全テストの実公表入力を比較した。主要の損失表とは分母が異なる。float32の一致も、日付と長さが同じ履歴に限る。差の閾値は生物学的同等性を意味しない。'
        q=pd.read_csv(base/'comparisons.csv',float_precision='round_trip');rows=[];selected={}
        names={'all':'全対象','both_without_imputation':'両入力に補完なし','both_imputed_at_most_point1':'両入力の補完割合0.1以下','both_imputed_at_most_point25':'両入力の補完割合0.25以下','either_imputed_over_point25':'いずれかの補完割合0.25超'}
        s=q[(q.dataset=='germany_sites')&(q.source_age_weeks==1)&(q.period=='all_test')&(q.metric=='wis')&(q.block_weeks==8)]
        for reference in ['ensemble','pooled_hgb']:
            for model,label in MODELS.items():
                for stratum,name in names.items():
                    z=s[(s.reference_model==reference)&(s.model==model)&(s.stratum==stratum)];assert len(z)==1;r=z.iloc[0].to_dict();selected[reference+'|'+model+'|'+stratum]=r;rows.append([label,REFS[reference],name,str(int(r['n_pairs'])),f(r['ratio'])+' ['+f(r['ratio_low'])+', '+f(r['ratio_high'])+']'])
        text+='\n\n'+table(['ドイツ地点の候補（1週前）','最新参照','入力の条件','ペア数','WIS比 [95%区間]'],rows)+'\n\n補完のない群は小さく、群によって時期・病原体・観測頻度も変わる。層別の差を補完の因果効果とは解釈しない。全閾値・全参照・2026年・MAE・ブロック長を保存した。'
        result.update(quality_results=text,quality_facts=dict(similarity=summaries_to_records(d),selected_comparisons=selected))
    return result

def summaries_to_records(frame):return frame.to_dict('records')

def joint_render(paths,table,f):
    if 'joint' not in paths:return dict(joint_results='共同期間・複数比較の追加点検は未完了。',joint_facts={},joint_main_note='')
    d=pd.read_csv(paths['joint']/'comparisons.csv',float_precision='round_trip');summary=pd.read_csv(paths['joint']/'family-summary.csv',float_precision='round_trip');rows=[]
    for r in summary.to_dict('records'):
        rows.append([r['country'],str(int(r['block_weeks'])),str(int(r['statistics'])),str(int(r['valid_bootstrap'])),str(int(r['invalid_bootstrap'])),str(int(r['nominal_intervals_excluding_one'])),str(int(r['simultaneous_intervals_excluding_one']))])
    text='両モデルを公開後の同じ期間に揃えた探索的な自己点検である。各国で、2モデル×2固定参照×1/2週前×2集計水準の16比較を作り、各比較の比の比と代替比較の比を合わせて32統計量とした。同じ週を全比較で共同再抽出し、対数比の最大絶対偏差の95百分位から同時区間を作った。国ごとに10000再抽出であり、論文中の全ての比較を包括した調整でも、少数の流行に対する厳密な被覆保証でもない。\n\n'+table(['比較群','ブロック週数','同時に扱う統計量','有効再抽出','無効再抽出','通常区間が1を含まない本数','同時区間が1を含まない本数'],rows)
    names={'national':'全国','site':'地点','regional':'地域'};models={'chronos_bolt_base':'Chronos-Bolt','timesfm_2p5':'TimesFM'};rows=[];selected={};s=d[(d.source_age_weeks==1)&(d.reference_model=='ensemble')&(d.block_weeks==8)]
    def band(r,lo,hi):return f(r['value'])+' ['+f(r[lo])+', '+f(r[hi])+']'
    for r in s.to_dict('records'):
        key='|'.join(str(r[x]) for x in ['country','unit_level','model','statistic']);selected[key]=r;rows.append([r['country']+'・'+names[r['unit_level']],models[r['model']],'古い/最新の比の比' if r['statistic']=='ratio_of_freshness_ratios' else '古い汎用/最新従来',str(int(r['n_pairs'])),band(r,'nominal_low','nominal_high'),band(r,'simultaneous_low','simultaneous_high')])
    text+='\n\n固定3方法・1週前の例を示す。固定6方法と2週前も同時比較群に含み、全値を保存した。\n\n'+table(['対象','汎用','統計量','4予測の共通例','共同期間の通常区間','同時区間'],rows)+'\n\n通常区間と同時区間は同じ期間・同じ予測を使う。元のChronos全期間の表との違いには、評価期間を揃えた影響も含まれる。区間が1を含むことを無効果や同等性の証明とせず、1を含まない探索的な区間も独立した検証とは扱わない。'
    c=selected['Germany|national|chronos_bolt_base|ratio_of_freshness_ratios'];t=selected['Germany|national|timesfm_2p5|ratio_of_freshness_ratios'];assert all(r['simultaneous_low']<=1<=r['simultaneous_high'] for r in [c,t])
    note='観測終端延長群を両モデルの公開後の共同期間に揃え、国ごとの32統計量を共同再抽出した探索的感度では、全国・固定3方法・1週前の損失比の比の同時区間は、Chronos-Bolt '+band(c,'simultaneous_low','simultaneous_high')+'、TimesFM '+band(t,'simultaneous_low','simultaneous_high')+'だった。いずれも1を含み、公称区間だけから相対的な頑健性の優位を確証しない。全比較群とブロック長別の結果は付録に示す。'
    abstract='観測終端延長群を両モデルの公開後の同じ期間に揃えた探索的解析でも、全国・固定3方法・1週前の相対的な損失増の優位は、32統計量の同時区間で確証できなかった。'
    return dict(joint_results=text,joint_facts=dict(family_summary=summary.to_dict('records'),selected=selected),joint_main_note=note,additional_abstract=abstract)
