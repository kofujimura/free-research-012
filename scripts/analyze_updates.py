"""Score revision-only input ablations and compare dynamics at a common anchor."""
import argparse,json,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT,Archive,load_config
from analyze import KEY,MODELS,bootstrap

DIRS=['E008-statistical','E009-chronos','E010-timesfm','E014-revision-statistical','E015-revision-chronos','E016-revision-timesfm']

def loss(q,y):
    e=y-q;taus=np.arange(1,10)/10
    return float(2*np.maximum(taus*e,(taus-1)*e).mean()),float(abs(q[4]-y))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--primary-dir',default='experiments/E011-primary-analysis/results');args=ap.parse_args();out=pathlib.Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    cfg=load_config();archive=Archive(cfg)
    cases=pd.read_csv(ROOT/'experiments/E012-prepare-revision-prefixes/cases.csv')
    contexts=json.loads((ROOT/'experiments/E012-prepare-revision-prefixes/all-inputs.json').read_text())
    truth=pd.read_csv(ROOT/'experiments/E007-prepare-inputs-fixed/truth.csv',dtype={'truth_lag':str})
    truths={tuple(r[k] for k in KEY)+(r['truth_lag'],):r for r in truth.to_dict('records')}
    raw={}
    for directory in DIRS:
        p=ROOT/'experiments'/directory
        assert json.loads((p/'run.json').read_text())['status']=='completed'
        for line in (p/'forecasts.jsonl').read_text().splitlines():
            r=json.loads(line);raw[(r['input_id'],r['model'])]=np.asarray(r['quantiles'],dtype=float)
    rows=[];identity_errors=[]
    for r in cases[cases.status=='ok'].to_dict('records'):
        if r['issue_date']<cfg['test_start']:continue
        for lag in ['56','latest']:
            ref=truths[tuple(r[k] for k in KEY)+(lag,)]
            if pd.isna(ref['y_log']):continue
            anchor=pd.Timestamp(r['anchor_date']);target=pd.Timestamp(r['target_date'])
            refseries=archive.series_at({'commit':ref['truth_commit']},r['pathogen'])['value']
            anchor_ref=refseries.get(anchor,np.nan)
            anchor_ref_log=float(np.log10(anchor_ref)) if pd.notna(anchor_ref) and anchor_ref>0 else np.nan
            for stage,uid in [('old',r['old_input_id']),('revised_prefix',r['revised_input_id']),('fresh',r['fresh_input_id'])]:
                ctx=contexts[uid];h=(target-pd.Timestamp(ctx['last_date'])).days//7
                input_anchor=ctx['log_values'][ctx['dates'].index(r['anchor_date'])] if r['anchor_date'] in ctx['dates'] else np.nan
                for model in MODELS:
                    if model=='timesfm_2p5' and r['issue_date']<cfg['timesfm_interpretation_start']:continue
                    q=raw[(uid,model)][h-1] if h>0 else np.repeat(ctx['log_values'][len(ctx['log_values'])-1+h],9)
                    wis,mae=loss(q,ref['y_log'])
                    if np.isfinite(input_anchor) and np.isfinite(anchor_ref_log):
                        anchored_q=q-input_anchor;anchored_y=ref['y_log']-anchor_ref_log
                        aw,am=loss(anchored_q,anchored_y)
                        decomposition=(q[4]-ref['y_log'])-((anchored_q[4]-anchored_y)+(input_anchor-anchor_ref_log))
                        identity_errors.append(abs(decomposition))
                    else:aw=am=np.nan
                    old=contexts[r['old_input_id']];fresh=contexts[r['fresh_input_id']]
                    relation='identical' if r['old_input_id']==r['fresh_input_id'] else 'same_end_revised' if old['last_date']==fresh['last_date'] else 'new_observations'
                    rows.append({**{k:r[k] for k in KEY},'source_age_weeks':r['source_age_weeks'],'truth_lag':lag,'stage':stage,'input_id':uid,'model':model,'anchor_date':r['anchor_date'],'input_anchor_log':input_anchor,'reference_anchor_log':anchor_ref_log,'anchor_revision_log':input_anchor-anchor_ref_log,'info_relation':relation,'wis':wis,'mae':mae,'anchored_wis':aw,'anchored_mae':am,'signed_level_error':q[4]-ref['y_log']})
    d=pd.DataFrame(rows);d.to_csv(out/'case-update-scores.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    summaries=[];paired_records=[]
    for lag in ['56','latest']:
        for age in [1,2]:
            z=d[(d.truth_lag==lag)&(d.source_age_weeks==age)]
            for model in MODELS:
                q=z[z.model==model]
                for transition,left,right in [('revision','old','revised_prefix'),('new_observations','revised_prefix','fresh'),('all_update','old','fresh')]:
                    pair=q[q.stage==left].merge(q[q.stage==right],on=KEY,suffixes=('_candidate','_reference'),validate='one_to_one')
                    for label in ['all',*cfg['pathogens']]:
                        s=pair if label=='all' else pair[pair.pathogen==label]
                        if s.empty:continue
                        start=max(cfg['test_start'],cfg['timesfm_interpretation_start']) if model=='timesfm_2p5' else cfg['test_start']
                        for metric in ['wis','mae']:
                            b=bootstrap(s,metric,start,cfg['test_end'],8,cfg['bootstrap_repetitions'],cfg['seed'])
                            summaries.append(dict(truth_lag=lag,source_age_weeks=age,model=model,transition=transition,stratum=label,n_pairs=len(s),candidate_mean=float(s[metric+'_candidate'].mean()),reference_mean=float(s[metric+'_reference'].mean()),metric=metric,**b))
            ref=z[(z.stage=='fresh')&(z.model=='ensemble')]
            for model in ['chronos_bolt_base','timesfm_2p5']:
                candidate=z[(z.stage=='old')&(z.model==model)]
                pair=candidate.merge(ref,on=KEY,suffixes=('_candidate','_reference'),validate='one_to_one')
                start=max(cfg['test_start'],cfg['timesfm_interpretation_start']) if model=='timesfm_2p5' else cfg['test_start']
                for period in ['all_test','year2026']:
                    first=max(start,'2026-01-02') if period=='year2026' else start
                    pp=pair[pair.issue_date>=first]
                    for label in ['all',*cfg['pathogens'],'new_observations','identical','same_end_revised']:
                        s=pp if label=='all' else pp[pp.pathogen==label] if label in cfg['pathogens'] else pp[pp.info_relation_candidate==label]
                        for metric in ['wis','mae','anchored_wis','anchored_mae']:
                            ss=s[s[metric+'_candidate'].notna()&s[metric+'_reference'].notna()]
                            if ss.empty:continue
                            b=bootstrap(ss,metric,first,cfg['test_end'],8,cfg['bootstrap_repetitions'],cfg['seed'])
                            paired_records.append(dict(truth_lag=lag,source_age_weeks=age,model=model,period=period,stratum=label,n_pairs=len(ss),metric=metric,candidate_mean=float(ss[metric+'_candidate'].mean()),reference_mean=float(ss[metric+'_reference'].mean()),**b))
    steps=pd.DataFrame(summaries);comparison=pd.DataFrame(paired_records)
    steps.to_csv(out/'update-contributions.csv',index=False);comparison.to_csv(out/'anchored-comparisons.csv',index=False)
    agg=d.groupby(['truth_lag','source_age_weeks','stage','model']).agg(n=('wis','size'),mean_abs_anchor_revision=('anchor_revision_log',lambda x:float(x.abs().mean())),median_abs_anchor_revision=('anchor_revision_log',lambda x:float(x.abs().median())),anchor_missing=('anchored_wis',lambda x:int(x.isna().sum()))).reset_index()
    agg.to_csv(out/'anchor-revision-summary.csv',index=False)
    original=pd.read_csv(ROOT/args.primary_dir/'comparisons.csv',dtype={'truth_lag':str})
    differences=[]
    for r in comparison[(comparison.truth_lag=='56')&(comparison.period=='all_test')&(comparison.stratum=='all')&(comparison.metric=='wis')].to_dict('records'):
        old=original[(original.truth_lag=='56')&(original.period=='all_test')&(original.stratum=='all')&(original.metric=='wis')&(original.variant=='native')&(original.block_weeks==8)&(original.model==r['model'])&(original.source_age_weeks==r['source_age_weeks'])]
        assert len(old)==1
        delta=abs(float(old.iloc[0].ratio)-r['ratio']);differences.append(delta)
    summary=dict(case_score_rows=len(d),new_contexts=len(contexts)-386,max_point_error_decomposition_error=max(identity_errors),max_primary_ratio_recalculation_error=max(differences),exploratory=True)
    assert summary['max_point_error_decomposition_error']<1e-12
    assert summary['max_primary_ratio_recalculation_error']<1e-12
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
