"""Generate revision tables and numeric prose from post-review saved analysis."""
import json
import pandas as pd

def render(paths,table,f,ci,select):
    if 'review_strata' not in paths:return {}
    base=paths['review_strata'];d=pd.read_csv(base/'horizon-comparisons.csv');s=json.loads((base/'summary.json').read_text());labels={'ensemble':'3方法固定合成','chronos_bolt_base':'Chronos-Bolt','timesfm_2p5':'TimesFM'};facts={}
    def get(model,age,stratum='all',comparison='fresh_ensemble'):
        r=select(d,model=model,source_age_weeks=age,stratum=stratum,comparison=comparison);facts['|'.join(map(str,[model,age,stratum,comparison]))]=r;return r
    rows=[]
    for model in labels:
        for stratum,name in [('fresh_horizon_le2','最新参照の予測距離≤2週'),('fresh_horizon_ge3','最新参照の予測距離≥3週')]:
            z=[get(model,age,stratum) for age in [0,1,2]];assert len({r['n_pairs'] for r in z})==1;rows.append([labels[model],name,int(z[0]['n_pairs']),int(z[0]['n_issue_weeks']),*[r['ratio_ci'] for r in z]])
    htable=table(['予測方法','条件','ペア数','発行週数','最新入力','1週前入力','2週前入力'],rows)
    own=[]
    for model in labels:
        z=[get(model,age,'all','fresh_same_method') for age in [1,2]];own.append([labels[model],int(z[0]['n_pairs']),int(z[0]['n_issue_weeks']),*[r['ratio_ci'] for r in z]])
    own_table=table(['方法（同じ方法の最新入力を1）','ペア数','発行週数','1週前入力','2週前入力'],own)
    p=pd.read_csv(base/'pathogen-comparisons.csv',dtype={'truth_lag':str});prows=[]
    for model in ['chronos_bolt_base','timesfm_2p5']:
        for period,name in [('all_test','全テスト'),('year2026','2026年')]:
            for pathogen in ['SARS-CoV-2','Influenza A','RSV A/B']:
                z=p[(p.model==model)&(p.period==period)&(p.stratum=='pathogen:'+pathogen)].sort_values('source_age_weeks')
                if z.empty:
                    # Use actual fixed config labels; preserve all three without guessing translations.
                    continue
                assert len(z)==3;prows.append([labels[model],name,{'Influenza A':'インフルエンザA'}.get(pathogen,pathogen),int(z.iloc[0].n_pairs),int(z.iloc[0].n_issue_weeks),*[ci(r) for _,r in z.iterrows()]])
    # Pathogen names in the analysis are taken verbatim, then labelled only for display.
    if len(prows)!=12:
        prows=[]
        for (model,period,pathogen),g in p.groupby(['model','period','stratum'],sort=True):
            g=g.sort_values('source_age_weeks');assert len(g)==3;prows.append([labels[model],{'all_test':'全テスト','year2026':'2026年'}[period],pathogen.removeprefix('pathogen:'),int(g.iloc[0].n_pairs),int(g.iloc[0].n_issue_weeks),*[ci(r) for _,r in g.iterrows()]])
    ptable=table(['方法','期間','病原体','ペア数','発行週数','最新入力','1週前入力','2週前入力'],prows)
    ident=pd.read_csv(base/'identity-weeks.csv');irows=[]
    for issue,g in ident.groupby('issue_date',sort=True):
        counts={r.model:int(r.n_pairs) for r in g.itertuples()};irows.append([issue,counts.get('chronos_bolt_base','—'),counts.get('timesfm_2p5','—'),str(int(g.minimum_fresh_horizon.min()))+'〜'+str(int(g.maximum_fresh_horizon.max()))])
    itable=table(['発行週','Chronosの同一入力組数','TimesFMの同一入力組数','最新参照の予測距離（週）'],irows)
    hist=pd.read_csv(base/'horizon-distribution.csv');hrows=[]
    for horizon,g in hist.groupby('fresh_horizon_weeks',sort=True):
        a={r.model:r for r in g.itertuples()};row=[int(horizon)]
        for model in ['chronos_bolt_base','timesfm_2p5']:
            r=a.get(model);row.extend([int(r.n_pairs) if r else 0,int(r.same_input_count) if r else 0])
        hrows.append(row)
    dist=table(['最新参照の予測距離（週）','Chronos標本数','うち同一入力','TimesFM標本数','うち同一入力'],hrows)
    gaps=pd.read_csv(base/'publication-gaps.csv');gtable=table(['前の全国ファイル更新日','次の更新日','間隔（暦日）'],[[r.previous_publication[:10],r.next_publication[:10],int(r.calendar_days)] for r in gaps.itertuples()])
    gap_prose='保存した全国集計ファイルの更新には、'+ '、'.join(r.previous_publication[:10]+'から'+r.next_publication[:10]+'まで'+str(int(r.calendar_days))+'日' for r in gaps.itertuples())+'の空白があった。これは当該ファイルの公表履歴であり、採水・測定の停止や他の配信経路の停止を確認したものではない。'
    nz=pd.read_csv(base/'nz-publication-intervals.csv');ntable=table(['NZの公表間隔（暦日）','件数'],nz.values.tolist());n=int(nz.n_intervals.sum());fourteen=int(nz.loc[nz.interval_days==14,'n_intervals'].sum());nztext='テスト期間の保存公表履歴では'+str(len(s['nz_publication_dates']))+'公表日、連続する'+str(n)+'間隔のうち'+str(fourteen)+'間隔が14日であり、おおむね隔週だった。曜日は木曜'+str(s['nz_weekday_counts'].get('Thursday',0))+'日が最多だった。1週前の締切を設けても更新がない場合と、次の公表で複数週が加わる場合が混在し、ドイツの1週前入力と同じ観測差を意味しない。'
    for model in labels:
        for age in [0,1,2]:get(model,age)
    cnear=get('chronos_bolt_base',1,'fresh_horizon_le2');tnear=get('timesfm_2p5',1,'fresh_horizon_le2');cnew=get('chronos_bolt_base',1,'new_observations','fresh_same_method');tnew=get('timesfm_2p5',1,'new_observations','fresh_same_method');enew=get('ensemble',1,'new_observations','fresh_same_method')
    result=dict(table_review_horizons=htable,table_review_own_age=own_table,table_review_pathogens=ptable,table_review_identity_weeks=itable,table_review_horizon_distribution=dist,table_review_publication_gaps=gtable,table_review_nz_intervals=ntable,review_calendar_text=gap_prose,review_nz_calendar_text=nztext,review_facts=facts)
    result['review_horizon_interpretation']='査読後の探索的解析で、最新参照の予測距離が2週以下の'+str(int(cnear['n_pairs']))+'組では、1週前入力のChronos-Boltの比は'+cnear['ratio_ci']+'、TimesFMは'+tnear['ratio_ci']+'だった。群は予測距離による区分であり、通常公表/休止を完全に分けない。3週以上には公表の数日の遅れと次週対象も含まれ、同じ発行週が両群に入る場合がある。各方法の全体平均と、短い予測距離で運用する場合の成績を区別する必要がある。'
    result['review_own_new_text']='新しい観測週との差がある組で、同じ方法の最新入力を参照とする1週前入力のWIS比は、Chronos-Bolt '+cnew['ratio_ci']+'、TimesFM '+tnew['ratio_ci']+'、3方法合成 '+enew['ratio_ci']+'だった。これは公表時期による条件付きの比較で、測定や公表を早める介入の効果ではない。'
    return result
