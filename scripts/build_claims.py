"""Generate the claim/evidence index directly from complete numerical tables."""
import argparse,json,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT

MODELS={'chronos_bolt_base':'Chronos-Bolt','timesfm_2p5':'TimesFM'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',default='config/report-results.json');ap.add_argument('--out',required=True);args=ap.parse_args();mapping=json.loads((ROOT/args.manifest).read_text());cache={};claims=[]
    def get(alias,filters,fields,file='comparisons.csv'):
        path=mapping[alias]+'/'+file
        if path not in cache:cache[path]=pd.read_csv(ROOT/path,dtype={'truth_lag':str},float_precision='round_trip')
        d=cache[path];mask=np.ones(len(d),bool)
        for k,v in filters.items():mask&=d[k].eq(v).to_numpy()
        s=d.loc[mask];assert len(s)==1,(alias,filters,len(s));r=s.iloc[0].to_dict();values={k:r[k] for k in fields};return r,dict(path=path,filters=filters,values=values)
    def band(r,prefix='ratio'):return f"{r[prefix]:.3f} [{r[prefix+'_low']:.3f}, {r[prefix+'_high']:.3f}]"
    def add(cid,text,checks,scope,implication,exploratory=True,sources=(),status='supported'):
        evidence=list(dict.fromkeys(c['path'] for c in checks));claims.append(dict(claim_id=cid,text=text,status=status,evidence_paths=evidence,source_ids=list(sources),experiment_ids=sorted({path.split('/')[1] for path in evidence if path.startswith('experiments/')}),scope=scope,verify=dict(command='python scripts/verify_claims.py --out /path/outside/checkout/claim-check.json',checks=checks),expected=[c['values'] for c in checks],exploratory=exploratory,reader_implication=implication))
    common=dict(truth_lag='56',variant='native',source_age_weeks=1,period='all_test',stratum='all',metric='wis',block_weeks=8);fields=['n_pairs','n_issue_weeks','ratio','ratio_low','ratio_high','same_input_count','same_prediction_count','known_target_count'];checks=[];p={}
    for model in MODELS:p[model],c=get('primary',dict(common,model=model),fields);checks.append(c)
    add('CL01','主要解析の1週前入力/最新3方法固定合成の平均WIS比は'+ '、'.join(MODELS[k]+' '+band(v) for k,v in p.items())+'。両95%区間は1を含み、同等性・非劣性を立証していない。',checks,'ドイツ全国3病原体、実公表入力、対象位置−2/+5日、56日参照、未補正。TimesFMは重み公開後の期間。区間は週ブロック8週、2000再抽出、多重比較未調整。','新しい予測器が1週分の新しい公表情報を一律に代替すると判断する根拠は得られない。',False,['LIT-BRACHER-2021'])
    checks=[];parts=[]
    for model in MODELS:
        r,c=get('primary',dict(common,model=model,stratum='information:new_observations'),fields);checks.append(c);z=p[model];parts.append(MODELS[model]+f"：全体の同一保存履歴{int(z['same_input_count'])}/{int(z['n_pairs'])}、観測終端延長群のWIS比"+band(r))
    add('CL02','暦上1週前でも入力差は一様ではない。'+'。'.join(parts)+'。',checks+[x for x in claims[0]['verify']['checks']], '保存履歴の日付とfloat64対数値の一致。採水条件や観測/補完の来歴まで同じとはしない。新観測群は公表工程と時期による観察的層別。','暦上の週差に加えて、実際の観測終端の追加・改訂・同一履歴を分けて評価する。',False)
    checks=[];parts=[]
    for ref in ['ensemble_extended','rolling_best_classical']:
        for model in MODELS:
            r,c=get('extended',dict(common,model=model,reference_model=ref),fields);checks.append(c);parts.append(ref+'/'+MODELS[model]+' '+band(r))
    add('CL03','全国の1週前入力の評価は従来参照に依存する。'+'、'.join(parts)+'。',checks,'元の主要解析後に追加した6方法固定合成と、過去に成熟済みの成績による選択。基準が変わると共通標本も少し異なる。全テスト最良法ではない。','単純な従来参照だけで汎用予測の運用上の価値を決めず、強い固定合成と時点ごとの選択を併記する。')
    checks=[];parts=[]
    for alias,levels in [('site',['site']),('nz',['national','regional'])]:
        for level in levels:
            for model in MODELS:
                r,c=get(alias,dict(common,model=model,reference_model='ensemble',stratum='level:'+level),fields);checks.append(c);parts.append(alias+'/'+level+'/'+MODELS[model]+' '+band(r))
    add('CL04','地点・別の公表制度への拡張では一様な交換関係を得ない。'+'、'.join(parts)+'。',checks,'固定した公表前コホート、観測・参照が揃った条件のみ。NZ全国と地域、ドイツ地点は独立した流行数ではない。国の順位比較ではない。','運用対象の公表頻度と評価対象で再検証し、全国一系列の結果をそのまま移さない。')
    checks=[];parts=[]
    for alias,levels in [('pooled_site',['site']),('pooled_nz',['national','regional'])]:
        for level in levels:
            for model in MODELS:
                r,c=get(alias,dict(common,model=model,reference_model='pooled_hgb',stratum='level:'+level),['n_pairs','ratio','ratio_low','ratio_high']);checks.append(c);parts.append(alias+'/'+level+'/'+MODELS[model]+' '+band(r))
    add('CL05','最新の共有学習との比較も国により異なる。'+'、'.join(parts)+'。',checks,'国別の過去成熟済み複数系列から学ぶ35特徴・固定設定HGB。汎用モデルより情報が多い。構造の因果比較ではない。','共有学習を運用上の比較対象に含める価値があるが、それが普遍的に優れるとも判断しない。',True,['METHOD-HGB-OFFICIAL'])
    checks=[];parts=[]
    for lag in ['56','latest']:
        r,c=get('sensitivity',dict(model='chronos_bolt_base',source_age_weeks=1,period='all_test',truth_lag=lag,metric='wis'),['n_pairs','ratio','ratio_low','ratio_high'],file='matched-maturity.csv');checks.append(c);parts.append(lag+'日/版 '+band(r))
    add('CL06','全参照が揃う同じ全国対象でも、Chronos-Boltの1週前入力の比は参照版で変わる。'+'、'.join(parts)+'。',checks,'各参照に同じ予測を対応し、共通対象に限定。最新版は将来の改訂を含み、どちらも生物学的真値ではない。','参照版と成熟期間を明示し、後日の改訂への一致を感染動態への一致と混同しない。')
    checks=[];parts=[]
    for alias,levels in [('interaction_national',['national']),('interaction_site',['site']),('interaction_nz',['national','regional'])]:
        for level in levels:
            for model in MODELS:
                f=dict(model=model,reference_model='ensemble',source_age_weeks=1,period='all_test',unit_level=level,stratum='information:new_observations',metric='wis',block_weeks=8);r,c=get(alias,f,['n_pairs','ratio_of_freshness_ratios','ratio_of_freshness_ratios_low','ratio_of_freshness_ratios_high','replacement_ratio']);checks.append(c);parts.append(alias+'/'+level+'/'+MODELS[model]+' '+band(r,'ratio_of_freshness_ratios'))
    add('CL07','観測終端延長群で古い/最新の4予測を揃えた損失比の比は、'+'、'.join(parts)+'。相対的な増分の小ささは、最新の別方法を代替できることと異なる。',checks,'探索的な同一週共同再抽出。固定3方法との8週ブロック結果。TimesFMはブロック長・2026年・6方法参照を替えると区間が1を含む場合がある。因果効果ではない。','情報更新への相対的な頑健性と、最新の選択肢に対する実損失を別に評価する。')
    checks=[];parts=[]
    for dataset,level in [('germany_national','national'),('germany_sites','site'),('nz','national'),('nz','regional')]:
        r,c=get('quality',dict(dataset=dataset,unit_level=level,source_age_weeks=1),['n_pairs','recorded_exact','float32_exact','additional_float32_identical','both_without_imputation'],file='similarity-summary.csv');checks.append(c);parts.append(dataset+'/'+level+f"：float32変換で追加された完全一致{int(r['additional_float32_identical'])}例")
    add('CL08','全テスト入力の1週差を比較した精度点検では、'+'、'.join(parts)+'。',checks,'同じ日付・長さの保存履歴をfloat32に変換した一致。予測・参照が揃う主要損失表とは分母が異なる。生物学的同等性の検証ではない。補完来歴は各caseから取得するE097がE096を訂正。','この標本の同一入力頻度をfloat32丸めだけで説明せず、実際の公表更新と補完を点検する。')
    checks=[];parts=[]
    for model in MODELS:
        r,c=get('indicator',dict(variant='native',reference_model='ensemble',model=model,source_age_weeks=1,period='all_test',metric='wis',block_weeks=8),['n_pairs','raw_ratio','raw_ratio_low','raw_ratio_high','normalized_ratio','normalized_ratio_low','normalized_ratio_high'],file='matched-indicator-ratios.csv');checks.append(c);parts.append(MODELS[model]+' 非正規化 '+band(r,'raw_ratio')+'、正規化 '+band(r,'normalized_ratio'))
    add('CL09','同じ対象に揃えたSARS指標の比較では、'+'。'.join(parts)+'。',checks,'非正規化系列を明示的に利用できる2025年8月以後。両条件で予測と参照の数値尺度が異なる。正規化の因果効果や全病原体への一般化ではない。','公表機関が推奨する指標と評価指標が異なる場合、共通標本で感度を確認する。',True,['DATA-AMELAG-FROZEN-METHODS'])
    checks=[];parts=[]
    for offset in [-2,5]:
        for side in ['candidate','reference']:
            r,c=get('primary',dict(period='all_test',model='chronos_bolt_base',source_age_weeks=1,target_offset_days=offset,side=side),['n','positive','negative','tp','fp','false_positive_rate'],file='alerts-paired.csv');checks.append(c);parts.append(f"{offset}日/{side}:上昇{int(r['positive'])}、検出{int(r['tp'])}、誤通知{int(r['fp'])}/{int(r['negative'])}")
    add('CL10','事前計画の全国2倍上昇の検出は事例が少ない。'+'、'.join(parts)+'。',checks,'下水指標の2週変化、成熟済み過去非上昇例の90百分位閾値。対象位置・近接週で同じ波が重なる。臨床的警報や感染者数を検証していない。','濃度のWISだけから通知の誤りや利用者への効果を推定しない。',False)
    if 'history' in mapping:
        checks=[];parts=[]
        for dataset,levels in [('national',['national']),('site',['site']),('nz',['national','regional'])]:
            for level in levels:
                for model in MODELS:
                    r,c=get('history',dict(dataset=dataset,unit_level=level,model=model,reference_model='ensemble',source_age_weeks=1,period='all_test',stratum='all',metric='wis',block_weeks=8),['n_pairs','candidate_extended_count','reference_extended_count','baseline_ratio','extended_both_ratio','extended_both_ratio_low','extended_both_ratio_high','candidate_long_short_ratio','candidate_long_short_ratio_low','candidate_long_short_ratio_high','extended_candidate_ratio','extended_candidate_ratio_low','extended_candidate_ratio_high','reference_long_short_ratio','reference_long_short_ratio_low','reference_long_short_ratio_high']);checks.append(c);parts.append(dataset+'/'+level+'/'+MODELS[model]+' 長い履歴の両者比 '+band(r,'extended_both_ratio'))
        add('CL11','最大104週から256週へ履歴を延ばす探索的感度を、同じ対象・同じ公表版で検証した。比較の改善と汎用自体の改善は同一ではなく、最新従来の損失も変わった。'+'、'.join(parts)+'。',checks,'固定公開重み、TimesFMは長短ともコンパイル上限256。利用可能な履歴が104週以下の条件は入力不変。NZの利用可能履歴は一部256を超える。最適長の探索や全履歴の保証ではない。','履歴の延長による汎用の変化と最新従来の損失増を分け、参照を固定した比較も併記する。')
    if 'joint' in mapping:
        checks=[];parts=[]
        for country in ['Germany','NZ']:
            r,c=get('joint',dict(country=country,block_weeks=8),['statistics','valid_bootstrap','invalid_bootstrap','nominal_intervals_excluding_one','simultaneous_intervals_excluding_one'],file='family-summary.csv');checks.append(c);parts.append(country+f"：通常区間で1を含まない{int(r['nominal_intervals_excluding_one'])}/{int(r['statistics'])}本、同時区間で{int(r['simultaneous_intervals_excluding_one'])}/{int(r['statistics'])}本")
            for level in ['national','site'] if country=='Germany' else ['national','regional']:
                for model in MODELS:
                    r,c=get('joint',dict(country=country,unit_level=level,model=model,reference_model='ensemble',source_age_weeks=1,statistic='ratio_of_freshness_ratios',block_weeks=8),['n_pairs','value','nominal_low','nominal_high','simultaneous_low','simultaneous_high']);checks.append(c)
        add('CL12','両モデルの公開後の共同期間で国ごとに32統計量を同時に扱う探索的点検では、'+'、'.join(parts)+'。',checks,'元の104週、観測終端延長群、固定3/6参照、1/2週前、国ごと2集計水準、比の比と代替比較。8週ブロック10000共同再抽出による最大絶対対数偏差の区間。論文中全比較を包括せず、小標本で厳密な被覆率を保証しない。','公称区間が1を除く探索的な例を、そのまま普遍的な頑健性や独立検証と扱わない。')
    def native(x):
        if isinstance(x,np.generic):return x.item()
        raise TypeError(type(x).__name__)
    path=pathlib.Path(args.out);path.write_text(''.join(json.dumps(c,ensure_ascii=False,default=native,allow_nan=False)+'\n' for c in claims));print(json.dumps(dict(claims=len(claims),path=str(path))))

if __name__=='__main__':main()
