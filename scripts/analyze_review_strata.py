"""Post-review exploratory horizon strata; saved forecasts only, no new inference."""
import argparse,hashlib,json,pathlib
import numpy as np
import pandas as pd
from analyze import KEY,bootstrap
from prepare_inputs import ROOT,load_config


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--primary-dir',default='experiments/E011-primary-analysis/results');ap.add_argument('--out',required=True);a=ap.parse_args();out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True);base=pathlib.Path(a.primary_dir);base=base if base.is_absolute() else ROOT/base;cfg=load_config()
    d=pd.read_csv(base/'case-scores.csv',dtype={'truth_lag':str});d=d[(d.truth_lag=='56')&(d.variant=='native')&(d.input_mode=='actual')&(~d.known_target)].copy();ref=d[(d.model=='ensemble')&(d.source_age_weeks==0)];rows=[];ident=[];hist=[];checks=[]
    old=pd.read_csv(base/'comparisons.csv',dtype={'truth_lag':str})
    for model in ['ensemble','chronos_bolt_base','timesfm_2p5']:
        start=max(cfg['test_start'],cfg['timesfm_interpretation_start']) if model=='timesfm_2p5' else cfg['test_start']
        for age in [0,1,2]:
            candidate=d[(d.model==model)&(d.source_age_weeks==age)];p=candidate.merge(ref,on=KEY,suffixes=('_candidate','_reference'),validate='one_to_one');p=p[(p.issue_date>=start)&(p.issue_date<=cfg['test_end'])].copy()
            p['relation']=np.select([p.input_id_candidate==p.input_id_reference,p.last_date_candidate==p.last_date_reference,p.last_date_candidate<p.last_date_reference],['identical','same_end_revised','new_observations'],default='fresh_end_older')
            same=d[(d.model==model)&(d.source_age_weeks==0)][KEY+['wis']].rename(columns={'wis':'wis_self_fresh'});p=p.merge(same,on=KEY,validate='one_to_one')
            for stratum,mask in [('all',np.ones(len(p),bool)),('fresh_horizon_le2',p.horizon_reference<=2),('fresh_horizon_ge3',p.horizon_reference>=3),*[(x,p.relation==x) for x in ['identical','same_end_revised','new_observations']]]:
                s=p.loc[mask].copy()
                if s.empty:continue
                for comparison in ['fresh_ensemble','fresh_same_method']:
                    z=s.copy()
                    if comparison=='fresh_same_method':z['wis_reference']=z.wis_self_fresh
                    seed=int.from_bytes(hashlib.sha256(f"{cfg['seed']}|REVIEW-1|{model}|{age}|{stratum}|{comparison}".encode()).digest()[:8],'little')
                    b=bootstrap(z,'wis',start,cfg['test_end'],8,cfg['bootstrap_repetitions'],seed)
                    row=dict(model=model,source_age_weeks=age,stratum=stratum,comparison=comparison,n_pairs=len(z),n_issue_weeks=z.issue_date.nunique(),candidate_mean=z.wis_candidate.mean(),reference_mean=z.wis_reference.mean(),same_input_count=(z.relation=='identical').sum(),minimum_fresh_horizon=z.horizon_reference.min(),maximum_fresh_horizon=z.horizon_reference.max(),analysis_start=start,**b);rows.append(row)
                    if stratum=='all' and comparison=='fresh_ensemble':
                        o=old[(old.truth_lag=='56')&(old.variant=='native')&(old.period=='all_test')&(old.stratum=='all')&(old.metric=='wis')&(old.block_weeks==8)&(old.model==model)&(old.source_age_weeks==age)].iloc[0];assert len(z)==o.n_pairs and np.isclose(b['ratio'],o.ratio,atol=1e-13,rtol=1e-13);checks.append(dict(model=model,age=age,n_pairs=len(z),absolute_ratio_difference=abs(b['ratio']-o.ratio)))
            if age==1:
                for issue,g in p[p.relation=='identical'].groupby('issue_date'):
                    ident.append(dict(model=model,issue_date=issue,n_pairs=len(g),minimum_fresh_horizon=g.horizon_reference.min(),maximum_fresh_horizon=g.horizon_reference.max()))
                for horizon,g in p.groupby('horizon_reference'):
                    hist.append(dict(model=model,fresh_horizon_weeks=int(horizon),n_pairs=len(g),n_issue_weeks=g.issue_date.nunique(),same_input_count=int((g.relation=='identical').sum())))
    pd.DataFrame(rows).to_csv(out/'horizon-comparisons.csv',index=False);pd.DataFrame(ident).to_csv(out/'identity-weeks.csv',index=False);pd.DataFrame(hist).to_csv(out/'horizon-distribution.csv',index=False)
    p=old[(old.truth_lag=='56')&(old.variant=='native')&(old.metric=='wis')&(old.block_weeks==8)&old.stratum.str.startswith('pathogen:')&old.model.isin(['chronos_bolt_base','timesfm_2p5'])&old.period.isin(['all_test','year2026'])].copy();p.to_csv(out/'pathogen-comparisons.csv',index=False)
    idx=json.loads((ROOT/'experiments/E004-vintage-audit-complete/archive-index.json').read_text())['records'];times=sorted(pd.Timestamp(r['commit_time']) for r in idx);gaps=[]
    for prev,cur in zip(times,times[1:]):
        days=(cur.date()-prev.date()).days
        if days>=10 and cur.date()>=pd.Timestamp(cfg['test_start']).date() and prev.date()<=pd.Timestamp(cfg['test_end']).date():gaps.append(dict(previous_publication=prev.isoformat(),next_publication=cur.isoformat(),calendar_days=days))
    pd.DataFrame(gaps).to_csv(out/'publication-gaps.csv',index=False)
    nzcfg=json.loads((ROOT/'experiments/E027-nz-panel-inputs-eligible/panel-config.json').read_text());nzreleases=json.loads((ROOT/'experiments/E027-nz-panel-inputs-eligible/release-eligibility.json').read_text());dates=sorted({pd.Timestamp(r['commit_time']).tz_convert('Pacific/Auckland').date() for r in nzreleases if nzcfg['test_start']<=pd.Timestamp(r['commit_time']).tz_convert('Pacific/Auckland').date().isoformat()<=nzcfg['test_end']});intervals=pd.Series([(y-x).days for x,y in zip(dates,dates[1:])],dtype=int).value_counts().sort_index();pd.DataFrame([dict(interval_days=int(k),n_intervals=int(v)) for k,v in intervals.items()]).to_csv(out/'nz-publication-intervals.csv',index=False)
    summary=dict(exploratory=True,post_review=True,threshold_selected_by_reviewer_after_results=True,bootstrap=dict(block_weeks=8,repetitions=cfg['bootstrap_repetitions'],calendar_week_grid=True,multiplicity_adjusted=False),all_primary_point_estimates_match=True,primary_checks=checks,publication_gap_scope='Changes of saved national aggregate file; no claim about all public channels or laboratory sampling',nz_test_start=nzcfg['test_start'],nz_test_end=nzcfg['test_end'],nz_publication_dates=[str(x) for x in dates],nz_weekday_counts=pd.Series([x.strftime('%A') for x in dates]).value_counts().to_dict(),nz_release_scope='All recorded release commits within test dates, whether later deemed eligible or not',n_horizon_rows=len(rows),pathogen_rows=len(p),fresh_horizon_groups_are_not_causal_regimes=True)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
