"""Render manuscript numbers and tables from saved analysis; no network or AI."""
import argparse,json,pathlib,re
import numpy as np
import pandas as pd
from jinja2 import Environment,StrictUndefined
from prepare_inputs import ROOT,load_config
from report_extensions import extension_tables,primary_auxiliary
from report_interaction import render as render_interaction
from report_interaction import joint_render
from report_history import render as render_history
from report_review import render as render_review

LABEL={'chronos_bolt_base':'Chronos-Bolt','timesfm_2p5':'TimesFM','ensemble':'3方法固定合成','ensemble_extended':'6方法固定合成','rolling_best_classical':'過去成績による選択'}
DEFAULT={'primary':'experiments/E011-primary-analysis/results','extended':'experiments/E022-extra-analysis-fixed/results','updates':'experiments/E018-update-decomposition/results'}

def f(x,digits=3):return '—' if pd.isna(x) else f'{float(x):.{digits}f}'
def ci(row):return f(row['ratio'])+' ['+f(row['ratio_low'])+', '+f(row['ratio_high'])+']'
def integer(x):return str(int(x))
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',*['| '+' | '.join(map(str,row))+' |' for row in rows]])
def select(frame,**filters):
    mask=np.ones(len(frame),dtype=bool)
    for key,value in filters.items():mask&=(frame[key]==value).to_numpy()
    result=frame.loc[mask]
    if len(result)!=1:raise ValueError('Expected one report row: '+str(filters)+'; got '+str(len(result)))
    r=result.iloc[0].to_dict();r['ratio_ci']=ci(r);return r
def json_ready(x):
    if isinstance(x,dict):return {str(k):json_ready(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [json_ready(v) for v in x]
    if isinstance(x,np.generic):x=x.item()
    if isinstance(x,float) and not np.isfinite(x):return None
    return x

def primary_context(paths):
    comp=pd.read_csv(paths['primary']/'comparisons.csv',dtype={'truth_lag':str});filters=dict(truth_lag='56',variant='native',period='all_test',stratum='all',metric='wis',block_weeks=8)
    main={}
    for key,model,age in [('e0','ensemble',0),('e1','ensemble',1),('e2','ensemble',2),('c0','chronos_bolt_base',0),('c1','chronos_bolt_base',1),('c2','chronos_bolt_base',2),('t0','timesfm_2p5',0),('t1','timesfm_2p5',1),('t2','timesfm_2p5',2)]:main[key]=select(comp,model=model,source_age_weeks=age,**filters)
    for key,model in [('c1new','chronos_bolt_base'),('t1new','timesfm_2p5')]:main[key]=select(comp,model=model,source_age_weeks=1,**dict(filters,stratum='information:new_observations'))
    rows=[]
    for key in ['e0','e1','e2','c0','c1','c2','t0','t1','t2']:
        r=main[key];rows.append([LABEL[r['model']],integer(r['source_age_weeks']),integer(r['n_pairs']),integer(r['n_issue_weeks']),r['ratio_ci'],integer(r['same_input_count']),integer(r['same_prediction_count']),integer(r['known_target_count'])])
    info=[]
    for model in ['chronos_bolt_base','timesfm_2p5']:
        for label,name in [('identical','同一入力'),('same_end_revised','終端は同じ・改訂あり'),('new_observations','観測終端が延長')]:
            r=select(comp,model=model,source_age_weeks=1,**dict(filters,stratum='information:'+label));info.append([LABEL[model],name,integer(r['n_pairs']),integer(r['n_issue_weeks']),r['ratio_ci']])
    alerts=pd.read_csv(paths['primary']/'alerts-paired.csv');rows_alert=[]
    for model in ['chronos_bolt_base','timesfm_2p5']:
        for offset in [-2,5]:
            z=alerts[(alerts.period=='all_test')&(alerts.model==model)&(alerts.source_age_weeks==1)&(alerts.target_offset_days==offset)]
            for r in z.to_dict('records'):
                rows_alert.append([LABEL[model]+'・1週前' if r['side']=='candidate' else '最新3方法（同標本）',str(offset),integer(r['n']),integer(r['positive']),integer(r['tp']),integer(r['fp'])+'/'+integer(r['negative']),f(r['false_positive_rate']),f(r['miss_rate'])])
    result=dict(main=main,table_primary=table(['候補','公表情報の年齢（週）','ペア数','発行週数','WIS比 [95%区間]','同一入力','ほぼ同一予測','既知の対象'],rows),table_information=table(['候補（1週前）','入力の関係','ペア数','発行週数','WIS比 [95%区間]'],info),table_primary_alerts=table(['予測','対象日−発行日（日）','通知可能例','2倍上昇例','検出数','誤通知/非上昇','誤通知率','見逃し率'],rows_alert))
    result['abstract_primary_interpretation']='区間は平均損失の改善と悪化の双方を含み、同等性や非劣性を立証する設計でもない。'
    result['primary_interpretation']='最新情報を入力した場合の比はChronos-Boltで'+main['c0']['ratio_ci']+'、TimesFMで'+main['t0']['ratio_ci']+'だった。一方、古い公表情報での比は表1のとおりであり、モデルの改善を一定の「情報何週分」に置き換える根拠は得られない。1週前の情報に新しい観測週との差がある群では、Chronos-Boltの比は'+main['c1new']['ratio_ci']+'となった。ただし、この群分けは公表工程と流行時期にも依存するため、観測追加の因果効果とは解釈しない。'
    ac=alerts[(alerts.period=='all_test')&(alerts.model=='chronos_bolt_base')&(alerts.source_age_weeks==1)&(alerts.side=='candidate')]
    result['alerts_positive_count']=integer(ac.positive.iloc[0]);result['alerts_interpretation']='上昇例は各対象位置で'+ '、'.join(integer(x) for x in ac.positive)+'例に限られた。同じ上昇の波が異なる対象位置や近接週で重なるため、これらを独立した臨床的な警報事象として合計しない。濃度の誤差が小さいことから、誤通知率や見逃しが改善するとは限らない。意図した誤通知率を超えた条件もあり、この標本から臨床的有用性を結論できない。'
    return result

def extension_context(paths):
    d=pd.read_csv(paths['extended']/'comparisons.csv',dtype={'truth_lag':str});rows=[];selected={}
    for reference in ['ensemble_extended','rolling_best_classical']:
        for model in ['chronos_bolt_base','timesfm_2p5']:
            r=select(d,truth_lag='56',variant='native',period='all_test',stratum='all',metric='wis',block_weeks=8,reference_model=reference,model=model,source_age_weeks=1);selected[reference+'|'+model]=r
            rows.append([LABEL[reference],LABEL[model],integer(r['n_pairs']),r['ratio_ci']])
    anchor=pd.read_csv(paths['updates']/'anchored-comparisons.csv',dtype={'truth_lag':str});arows=[]
    for model in ['chronos_bolt_base','timesfm_2p5']:
        for stratum,metric in [('all','wis'),('all','anchored_wis'),('new_observations','wis'),('new_observations','anchored_wis')]:
            g=anchor[(anchor.truth_lag=='56')&(anchor.source_age_weeks==1)&(anchor.model==model)&(anchor.period=='all_test')&(anchor.stratum==stratum)&(anchor.metric==metric)]
            if len(g)!=1:raise ValueError('Missing anchor report row')
            r=g.iloc[0];arows.append([LABEL[model],stratum+' / '+metric,integer(r.n_pairs),ci(r)])
    updates=pd.read_csv(paths['updates']/'update-contributions.csv',dtype={'truth_lag':str});urows=[]
    for model in ['ensemble','chronos_bolt_base','timesfm_2p5']:
        for transition in ['revision','new_observations']:
            z=updates[(updates.truth_lag=='56')&(updates.source_age_weeks==1)&(updates.model==model)&(updates.stratum=='all')&(updates.metric=='wis')&(updates.transition==transition)]
            if len(z)==1:r=z.iloc[0];urows.append([LABEL[model],transition,integer(r.n_pairs),f(r.difference,5)])
    s=selected['ensemble_extended|chronos_bolt_base'];t=selected['ensemble_extended|timesfm_2p5'];r=selected['rolling_best_classical|chronos_bolt_base'];v=selected['rolling_best_classical|timesfm_2p5']
    return dict(extended=selected,table_extended=table(['最新の参照','候補（1週前）','ペア数','WIS比 [95%区間]'],rows),abstract_exploratory='探索的に従来参照を6方法固定合成に強めると、比は'+s['ratio_ci']+'、'+t['ratio_ci']+'となった。一方、過去成績による従来法選択に対する比は、それぞれ'+r['ratio_ci']+'、'+v['ratio_ci']+'であり、比較対象によって解釈が変わった。',extended_interpretation='固定合成を強めた比較と、過去に利用できた成績による選択では結果が異なる。どちらか片方を選んで「従来法一般への優位」や「常に新しい情報の方が良い」とは結論しない。全比較、MAE、較正条件、ブロック長別の結果は保存した。',update_results='基準週からの変化で測ったWISと、水準で測ったWISの比較は以下のとおりだった。基準週からの変化も臨床的な正解ではなく、異なる測定対象を用いた感度解析である。\n\n'+table(['候補（1週前）','評価条件','ペア数','WIS比 [95%区間]'],arows)+'\n\n更新順を固定した分解では、損失A−Bを既存履歴の更新、B−Cを新たな週の観測追加として記述した。差が足し合わさる恒等式自体を発見としない。\n\n'+table(['予測器','更新段階','ペア数','WISの減少（対数濃度上）'],urows))

def panel_context(paths):
    text=[];rows=[];facts={}
    for key,name in [('site','ドイツ地点'),('nz','ニュージーランド')]:
        if key not in paths:continue
        d=pd.read_csv(paths[key]/'comparisons.csv',dtype={'truth_lag':str});levels=['site'] if key=='site' else ['national','regional']
        for level in levels:
            for reference in ['ensemble','ensemble_extended','rolling_best_classical']:
                for model in ['chronos_bolt_base','timesfm_2p5']:
                    r=select(d,truth_lag='56',variant='native',period='all_test',stratum='level:'+level,metric='wis',block_weeks=8,reference_model=reference,model=model,source_age_weeks=1)
                    rows.append([name+'・'+level,LABEL[reference],LABEL[model],integer(r['n_pairs']),integer(r['n_issue_weeks']),integer(r['n_units']),r['ratio_ci'],integer(r['same_input_count'])]);facts[key+'|'+level+'|'+reference+'|'+model]=r
    if rows:text.append(table(['対象','最新の参照','1週前の候補','ペア数','発行週数','系列数','WIS比 [95%区間]','同一入力'],rows))
    if not text:return dict(panel_results='入力は準備済みだが予測精度の集計は未完了。完成した結果と扱わない。',panel_facts={},panel_figures='')
    text.append('表の地点・地域の数は独立した流行の数ではない。NZ全国と地域は同じ流行を含むため混合した値を主要な一般化の根拠にしない。欠測と情報更新の層別を含めた全結果は対応する解析出力に保存した。')
    return dict(panel_results='\n\n'.join(text),panel_facts=facts,panel_figures='')

def maturity_context(paths):
    if 'sensitivity' not in paths:return '参照版を共通標本に揃えた追加解析は未完了である。'
    d=pd.read_csv(paths['sensitivity']/'matched-maturity.csv',dtype={'truth_lag':str});rows=[]
    for model in ['chronos_bolt_base','timesfm_2p5']:
        for lag in ['28','56','84','latest']:
            r=select(d,model=model,source_age_weeks=1,period='all_test',truth_lag=lag,metric='wis');rows.append([LABEL[model],lag,integer(r['n_pairs']),r['ratio_ci']])
    matrix=pd.read_csv(paths['sensitivity']/'matched-input-reference-matrix.csv',dtype={'truth_lag':str});m=[]
    for mode in ['actual','finalized_prefix']:
        for lag in ['56','latest']:
            z=matrix[(matrix.model=='chronos_bolt_base')&(matrix.source_age_weeks==0)&(matrix.period=='all_test')&(matrix.input_mode==mode)&(matrix.truth_lag==lag)]
            if len(z)==1:r=z.iloc[0];m.append([mode,lag,integer(r.n),f(r.wis,5)])
    return '参照の欠測による分母の違いを避け、全ての参照版がある同じ対象に揃えた比較を示す。\n\n'+table(['候補（1週前）','参照の時点（日）','共通ペア数','WIS比 [95%区間]'],rows)+'\n\n実公表入力か最終版の終端切断入力かという違いと、どの参照を当てるかという違いを分けた。最終版入力は将来の改訂を含む。次の行列の違いを、利用可能な方法の優劣とは扱わない。\n\n'+table(['入力履歴（Chronos-Bolt・最新）','参照','共通例数','平均WIS'],m)

def data_context():
    cfg=load_config();archive=json.loads((ROOT/'experiments/E004-vintage-audit-complete/archive-index.json').read_text());summary=json.loads((ROOT/'experiments/E007-prepare-inputs-fixed/summary.json').read_text());cases=pd.read_csv(ROOT/'experiments/E007-prepare-inputs-fixed/cases.csv')
    test=cases[(cases.input_mode=='actual')&(cases.source_age_weeks==0)&(cases.issue_date>=cfg['test_start'])]
    sites=json.loads((ROOT/'experiments/E024-site-panel-inputs/summary.json').read_text());nz=json.loads((ROOT/'experiments/E027-nz-panel-inputs-eligible/summary.json').read_text());elig=json.loads((ROOT/'experiments/E027-nz-panel-inputs-eligible/release-eligibility.json').read_text());cohort=pd.read_csv(ROOT/'experiments/E023-site-weekly-cohort/cohort.csv');nsite=cohort.site_id.nunique()
    return dict(data_main='固定した公開履歴は'+str(len(archive['records']))+'版、最終版は'+archive['frozen_commit']+'である。',main_calendar='較正用の発行は'+cfg['calibration_start']+'から、評価は'+cfg['test_start']+'〜'+cfg['test_end']+'の'+integer(test.issue_date.nunique())+'週とした。',main_availability='最新実公表情報で意図したテスト条件は'+integer(len(test))+'例だった。主要の共通比較は'+integer(len(test)-int(summary['truth_missing_by_lag']['56']))+'例で、主要参照の欠測は'+integer(summary['truth_missing_by_lag']['56'])+'例、入力に既知の対象週が含まれた条件は'+integer(summary['known_target_cases'])+'例だった。',panel_data_description='ドイツでは、テスト前の公開情報から人口規模と観測履歴・直近の観測頻度で'+str(nsite)+'地点・'+str(sites['units'])+'系列を固定した。正の測定値だけを採り、同じ日の複数値を対数平均し、その後に週内の日別値を対数平均する。平滑化だけの行を実測とは扱わない。ニュージーランドでは、CC BY4.0の公式履歴の国'+str(sum(x['unit_level']=='national' for x in json.loads((ROOT/'experiments/E027-nz-panel-inputs-eligible/units.json').read_text())))+'系列・地域'+str(sum(x['unit_level']=='regional' for x in json.loads((ROOT/'experiments/E027-nz-panel-inputs-eligible/units.json').read_text())))+'系列を使った。全履歴のうち'+str(sum(not x['eligible'] for x in elig))+'版に不正な日付行などがあり、修復せず直前の適格な公開版を使った。日曜終了週に対し月曜に発行する。ドイツの正規化指標と異なり、人口あたり1日あたりのゲノムコピー数である。両拡張は主要結果の後に計画した探索的検証である。',model_publication='使用重みの公開ファイル履歴は`data/models/weight-publication-metadata.json`にあり、Chronos-Boltはテスト開始前、TimesFMは'+cfg['timesfm_interpretation_start']+'以後の評価に限定した。')

def references():
    ids=['LIT-MCDONALD-2021','LIT-CROUSHORE-STARK-2001','LIT-EPICASTBENCH-2026','LIT-ALHASSAN-2025','LIT-KALAHASTI-2025','LIT-RADERMACHER-2025','LIT-LISON-2026','LIT-ADIGA-2026','LIT-MCGOUGH-2020','LIT-TANG-2025','LIT-HU-2026','LIT-VINTAGE-TS-2026','LIT-GIANNONE-2005','LIT-BRACHER-2021','LIT-BRACHER-CORRECTION-2022','LIT-CDC-OFFICIAL-PIPELINE','METHOD-FPP3','METHOD-CQR-2019','METHOD-HGB-OFFICIAL','MODEL-BOLT-BASE','MODEL-TIMESFM-2.5','DATA-NZ-DOCS','DATA-AMELAG-FROZEN-METHODS'];sources={}
    for line in (ROOT/'sources.jsonl').read_text().splitlines():
        x=json.loads(line)
        if x.get('source_id') in ids:sources[x['source_id']]=x
    rows=[]
    for i in ids:
        if i not in sources:continue
        r=sources[i];parts=['['+r['title']+']('+r.get('url',r.get('URL',''))+')']
        parts.extend(str(r[k]) for k in ['authors','year','version'] if r.get(k) not in [None,''])
        parts.append('確認範囲と取得日は`sources.jsonl`の'+i)
        rows.append('- '+'。'.join(parts)+'。')
    return '\n'.join(rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest');ap.add_argument('--out',required=True);ap.add_argument('--publication-status',default='最終版・AIエージェントによる査読1回に対応済み');args=ap.parse_args();out=pathlib.Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    mapping=json.loads(pathlib.Path(args.manifest).read_text()) if args.manifest else DEFAULT;paths={k:(ROOT/v if not pathlib.Path(v).is_absolute() else pathlib.Path(v)) for k,v in mapping.items()}
    ctx={**primary_context(paths),**extension_context(paths),**data_context(),**panel_context(paths)};ctx.update(publication_status='初稿作成中・未査読',maturity_results=maturity_context(paths),critique_provenance='モデルはgpt-6-astra、利用日は2026-10-18で、批判の全文と応答JSONを保存した。批判で挙がった事実は別途確認し、確認できなかったものを根拠に使わなかった。',verification_status='初稿の通し実行は`review/verification-result.json`、改訂後の全体再実行と最終の論文・図の照合は`review/final-verification-result.json`に記録した。いずれも同じ研究者による再実行であり独立した再現ではない。',references=references(),discussion_empirical='全国の比較は、モデルの種類だけでなく、入力の更新状態、従来法の選び方、後日参照する濃度の尺度に依存した。これらを分けた比較を、モデル更新とデータ更新を検討する際の評価設計に使える。ただし、本研究は両者の費用や現場の運用への効果を測っていない。',appendices='全ての較正条件、4/8/12週ブロック、病原体、対象位置、2026年、参照版、入力の関係による結果は各解析出力にある。これらを有利な条件だけ選んで主要結果に置き換えない。追加の上昇比率、ROC、定量下限標識、欠測・範囲外、時刻代理の感度の出力も再現手順から参照できる。')
    ctx.update(extension_tables(paths,select,table,f,ci,ROOT));ctx['table_primary_auxiliary']=primary_auxiliary(paths,table,f,ROOT)
    ctx.update(render_interaction(paths,table,f));ctx.update(render_history(paths,table,f));ctx.update(joint_render(paths,table,f));ctx['publication_status']=args.publication_status
    ctx.update(render_review(paths,table,f,ci,select))
    if ctx['additional_abstract']:ctx['abstract_exploratory']=ctx['additional_abstract']
    if ctx.get('history_facts'):ctx['abstract_exploratory']+='地点・ニュージーランドへの拡張と最大256週の履歴の感度でも一様な改善はなく、比較の比が下がった条件には最新従来の損失が増えた場合もあった。'
    env=Environment(undefined=StrictUndefined,autoescape=False,keep_trailing_newline=True);paper=env.from_string((ROOT/'paper.template.md').read_text()).render(**ctx)
    (out/'paper.md').write_text(paper);(out/'paper-facts.json').write_text(json.dumps(json_ready(ctx),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    for key,value in ctx.items():
        if key.startswith('table_'):(out/(key+'.md')).write_text(value+'\n')
    print(json.dumps(dict(paper_path=str(out/'paper.md'),analysis_aliases=list(paths),publication_status=ctx['publication_status']),ensure_ascii=False))

if __name__=='__main__':main()
