"""Additional manuscript tables; numerical text comes from frozen analysis outputs."""
import json
import numpy as np
import pandas as pd

MODELS={'chronos_bolt_base':'Chronos-Bolt','timesfm_2p5':'TimesFM'}
REFS={'ensemble':'3方法固定合成','ensemble_extended':'6方法固定合成','rolling_best_classical':'過去成績による選択','pooled_hgb':'共有学習の勾配ブースティング'}

def extension_tables(paths,select,table,f,ci,ROOT):
    facts={};result={}
    def load(alias,filename='comparisons.csv'):
        return pd.read_csv(paths[alias]/filename,dtype={'truth_lag':str},float_precision='round_trip')
    common=dict(truth_lag='56',variant='native',period='all_test',metric='wis',block_weeks=8,source_age_weeks=1)
    if 'indicator' in paths:
        d=load('indicator','matched-indicator-ratios.csv');rows=[]
        for ref in ['ensemble','ensemble_extended','rolling_best_classical']:
            for model,name in MODELS.items():
                q=d[(d.variant=='native')&(d.reference_model==ref)&(d.model==model)&(d.source_age_weeks==1)&(d.period=='all_test')&(d.metric=='wis')&(d.block_weeks==8)]
                assert len(q)==1;r=q.iloc[0]
                raw={k:r['raw_'+k] for k in ['ratio','ratio_low','ratio_high']};norm={k:r['normalized_'+k] for k in ['ratio','ratio_low','ratio_high']}
                difference={k:r[k] for k in ['ratio_difference','ratio_difference_low','ratio_difference_high']}
                rows.append([REFS[ref],name,str(int(r.n_pairs)),ci(raw),ci(norm),f(difference['ratio_difference'])+' ['+f(difference['ratio_difference_low'])+', '+f(difference['ratio_difference_high'])+']'])
                facts['indicator|'+ref+'|'+model]=dict(n_pairs=int(r.n_pairs),raw=raw,normalized=norm,difference=difference)
        result['indicator_results']='SARS-CoV-2だけで、非正規化指標と主要解析の正規化指標を、両方で評価できる同じ対象に揃えた。非正規化指標の明示的な公開系列が使える期間に限定される。\n\n'+table(['最新の参照','候補（1週前）','共通ペア数','非正規化 WIS比','正規化 WIS比','比の差 [95%区間]'],rows)+'\n\n各指標で予測も参照値も異なる。最後の列は同じ週を再抽出した比の差であり、正規化処理を介入した因果効果ではない。'
    else:result['indicator_results']='非正規化指標の比較は未集計。'
    rows=[]
    for alias,name,levels in [('pooled_site','ドイツ地点',['site']),('pooled_nz','NZ',['national','regional'])]:
        if alias not in paths:continue
        d=load(alias)
        for level in levels:
            for model,label in MODELS.items():
                r=select(d,reference_model='pooled_hgb',stratum='level:'+level,model=model,**common)
                facts[alias+'|'+level+'|'+model]=r;rows.append([name+'・'+level,label,str(int(r['n_pairs'])),str(int(r['n_units'])),r['ratio_ci']])
    result['pooled_results']=table(['対象','候補（1週前）','共通ペア数','系列数','最新の共有学習に対するWIS比 [95%区間]'],rows)+'\n\n国ごとに別々に学習した。共有学習には、他系列から得る成熟済みの参照値、病原体区分、対象日の年周期を加えた。単変量の汎用モデルと学習情報量を揃えたアーキテクチャ比較ではなく、利用可能な運用上の比較対象を増やす検証である。' if rows else '共有学習の比較は未集計。'
    if 'shifted' in paths:
        d=load('shifted');rows=[]
        for country,name,levels in [('germany_national','ドイツ全国',['national']),('nz','NZ',['national','regional'])]:
            for level in levels:
                for shift in [24,48]:
                    for model,label in MODELS.items():
                        r=select(d,country=country,availability_shift_hours=shift,reference_model='ensemble',stratum='level:'+level,model=model,**common)
                        facts['shift|'+country+'|'+level+'|'+str(shift)+'|'+model]=r;rows.append([name+'・'+level,str(shift),label,str(int(r['n_pairs'])),r['ratio_ci']])
        result['timing_results']=table(['対象','公開がGitより遅い仮定（時間）','候補（1週前）','ペア数','最新3方法へのWIS比 [95%区間]'],rows)+'\n\n入力の公開を一律に遅らせた仮想条件である。過去成績を使う時点も、参照の成熟締切と遅らせた公開時刻の遅い方に制限した。実際の公開遅延がこの長さだったと確認した結果ではない。'
    else:result['timing_results']='時刻代理の精度感度は未集計。'
    rows=[]
    for alias,name in [('cqr_national','ドイツ全国'),('cqr_nz','NZ'),('cqr_site','ドイツ地点')]:
        if alias not in paths:continue
        d=load(alias)
        levels=['all'] if alias!='cqr_nz' else ['level:national','level:regional']
        for level in levels:
            for window in [12,26,52]:
                for model,label in MODELS.items():
                    r=select(d,truth_lag='56',variant='calibrated',period='all_test',stratum=level,metric='wis',block_weeks=8,source_age_weeks=1,reference_model='ensemble',reference_interval='same_correction',calibration_window=window,model=model)
                    rows.append([name+'・'+level,str(window),label,str(int(r['n_pairs'])),r['ratio_ci']]);facts[alias+'|'+level+'|'+str(window)+'|'+model]=r
        summary=json.loads((paths[alias]/'summary.json').read_text());assert all(x['max_paired_point_mae_change']==0 and x['max_median_change']==0 for x in summary['windows'])
    result['calibration_results']=table(['対象','補正窓（過去例）','候補（1週前）','ペア数','同じ補正の最新3方法へのWIS比 [95%区間]'],rows)+'\n\n全窓を残し、テストの成績で最良窓を選んでいない。共通標本で中央値と点予測MAEが変わらないことを検証した。区間の補正から得られたWISの変化を点予測の改善とは解釈しない。' if rows else '追加の区間補正の比較は未集計。'
    result['extension_facts']=facts
    if 'site' in paths:
        d=load('site');rows=[]
        labels=[('information:identical','同一入力'),('information:same_end_revised','同じ終端・改訂あり'),('information:new_observations','観測終端の延長'),('advance_weeks:3+','観測終端の差が3週以上'),('reference_above_floor','参照週の定量下限未満の標識割合0'),('reference_floor_majority','参照週の同割合0.5以上'),('active2026','テスト前に固定した2026年継続群')]
        for model,name in MODELS.items():
            for label,text in labels:
                r=select(d,reference_model='ensemble',stratum=label,model=model,**common);rows.append([name,text,str(int(r['n_pairs'])),r['ratio_ci']]);facts['site_quality|'+label+'|'+model]=r
        result['site_quality_results']=table(['候補（1週前）','条件','ペア数','最新3方法へのWIS比 [95%区間]'],rows)+'\n\n定量下限の標識割合は日別標識を週内で平均した値であり、0でも全ての遺伝子が定量できたと保証しない。公式説明では定量下限未満の値は下限の半分で置き換える。標識付きの濃度を真のウイルス量や独立した検出事象として扱わない。各層の成績は流行時期なども異なり、層同士の因果比較ではない。同一入力でも予測器が異なるため予測自体が同じになるわけではなく、主要比較のほぼ同一予測の件数は保存表で確認できる。'
    else:result['site_quality_results']='地点の条件別結果は未集計。'
    availability=[];quality=[]
    for name,folder,start in [('ドイツ全国','experiments/E007-prepare-inputs-fixed','2025-07-04'),('ドイツ地点','experiments/E024-site-panel-inputs','2025-07-04'),('NZ','experiments/E027-nz-panel-inputs-eligible','2025-07-07')]:
        cases=pd.read_csv(ROOT/folder/'cases.csv');c=cases[(cases.input_mode=='actual')&(cases.issue_date>=start)&(cases.source_age_weeks==1)];counts=c.status.value_counts()
        availability.append([name,str(len(c)),str(int(counts.get('ok',0))),str(int(counts.get('horizon_outside_plan',0))),str(int(sum(v for k,v in counts.items() if k not in ['ok','horizon_outside_plan']))),str(int(c.known_target.sum()))])
    if 'sensitivity' in paths:
        context=load('sensitivity','context-audit.csv')
        for dataset,g in context.groupby('dataset',sort=True):
            quality.append([dataset,str(len(g)),str(int(g.constant.sum())),str(int(g.last_two_equal.sum()))])
    result['availability_results']=table(['対象（1週前入力）','意図した条件','入力可','16週超で範囲外','その他の入力欠測','既知の対象週'],availability)+'\n\n入力可でも、後日の参照値や比較相手が欠ける場合は損失のペアを作れない。主要結果のペア数を入力可の全数と混同しない。\n\n'+table(['対象','異なる入力数','定数列','末尾2点が同じ'],quality)+'\n\n後半の入力監査は保存された全ユニーク数値履歴であり、較正期間と、全国の将来版を切った診断用入力も含む。テストの実公表入力だけの頻度や、独立した事例数ではない。実測・補完の来歴は入力IDだけでは決まらず、次のケース単位の監査で各公開版の記録を用いる。'
    return result

def primary_auxiliary(paths,table,f,ROOT):
    d=pd.read_csv(paths['primary']/'case-scores.csv',dtype={'truth_lag':str},float_precision='round_trip')
    cfg=json.loads((ROOT/'config/main.json').read_text());d=d[(d.truth_lag=='56')&(d.variant=='native')&(d.input_mode=='actual')&(~d.known_target)&d.issue_date.between(cfg['test_start'],cfg['test_end'])];rows=[]
    keys=['issue_date','pathogen','target_date','target_offset_days']
    for model,label in MODELS.items():
        c=d[(d.model==model)&(d.source_age_weeks==1)];r=d[(d.model=='ensemble')&(d.source_age_weeks==0)];p=c.merge(r,on=keys,suffixes=('_candidate','_reference'),validate='one_to_one')
        if model=='timesfm_2p5':p=p[p.issue_date>=cfg['timesfm_interpretation_start']]
        for offset in cfg['target_offsets_days']:
            g=p[p.target_offset_days==offset]
            for side,name in [('candidate',label+'・1週前'),('reference','最新3方法（同標本）')]:
                rows.append([name,str(offset),str(len(g)),f(g['mae_'+side].mean()),f(g['covered80_'+side].mean()),f(g['width80_'+side].mean())])
    return table(['予測','対象日−発行日（日）','ペア数','MAE','80%区間の被覆率','平均区間幅'],rows)
