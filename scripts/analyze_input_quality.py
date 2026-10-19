"""Audit recorded vs float32 input identity and sensitivity to forward filling."""
import argparse,hashlib,json,pathlib
import numpy as np
import pandas as pd
import panel_analysis as panel
from prepare_inputs import ROOT,load_config

KEY=panel.KEY

def audit(folder):
    base=ROOT/folder;cfg=json.loads((base/'panel-config.json').read_text()) if (base/'panel-config.json').exists() else dict(load_config(),issue_frequency='W-FRI');cases=pd.read_csv(base/'cases.csv');inputs=json.loads((base/'inputs.json').read_text())
    if 'unit_id' not in cases:cases['unit_id']=cases.pathogen;cases['unit_level']='national'
    cases=cases[(cases.input_mode=='actual')&(cases.issue_date>=cfg['test_start'])&(cases.status=='ok')];fresh=cases[cases.source_age_weeks==0][KEY+['input_id','imputed_context','context_length']].rename(columns={'input_id':'fresh_input_id','imputed_context':'fresh_imputed_context','context_length':'fresh_context_length'});joined=cases.merge(fresh,on=KEY,validate='many_to_one');rows=[];cache={}
    for r in joined.to_dict('records'):
        ids=(r['input_id'],r['fresh_input_id'])
        if ids not in cache:
            old,new=[inputs[u] for u in ids];same_grid=old['dates']==new['dates'];x=np.asarray(old['log_values'],dtype=np.float64);y=np.asarray(new['log_values'],dtype=np.float64)
            cache[ids]=dict(same_grid=same_grid,recorded_exact=bool(same_grid and np.array_equal(x,y)),float32_exact=bool(same_grid and np.array_equal(x.astype(np.float32),y.astype(np.float32))),maximum_log_difference=float(np.max(np.abs(x-y))) if same_grid else np.nan,old_constant=bool(np.ptp(x)==0),fresh_constant=bool(np.ptp(y)==0),old_last_two_equal=bool(len(x)>=2 and x[-1]==x[-2]),fresh_last_two_equal=bool(len(y)>=2 and y[-1]==y[-2]))
        # Numeric-history deduplication does not preserve per-release provenance:
        # a newly measured value can equal a previously carried-forward value.
        quality=dict(old_imputed_fraction=r['imputed_context']/r['context_length'],fresh_imputed_fraction=r['fresh_imputed_context']/r['fresh_context_length'],old_real_observations=int(r['context_length']-r['imputed_context']),fresh_real_observations=int(r['fresh_context_length']-r['fresh_imputed_context']))
        rows.append({k:r[k] for k in KEY+['unit_level','source_age_weeks','input_id','fresh_input_id']}|cache[ids]|quality)
    return pd.DataFrame(rows),cfg

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--datasets',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();datasets=json.loads((ROOT/args.datasets).read_text());out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);summaries=[];all_pairs=[];comparisons=[]
    wanted=set(KEY+['model','input_mode','variant','known_target','source_age_weeks','truth_lag','wis','mae'])
    for entry in datasets:
        pairs,cfg=audit(entry['panel']);pairs['dataset']=entry['name'];all_pairs.append(pairs)
        for key,g in pairs.groupby(['unit_level','source_age_weeks'],sort=True):
            level,age=key;record=dict(dataset=entry['name'],unit_level=level,source_age_weeks=age,n_pairs=len(g),n_issue_weeks=g.issue_date.nunique(),recorded_exact=int(g.recorded_exact.sum()),float32_exact=int(g.float32_exact.sum()),additional_float32_identical=int((g.float32_exact&(~g.recorded_exact)).sum()),old_constant=int(g.old_constant.sum()),fresh_constant=int(g.fresh_constant.sum()),both_without_imputation=int((g.old_imputed_fraction.eq(0)&g.fresh_imputed_fraction.eq(0)).sum()),either_imputed_over_point25=int((g.old_imputed_fraction.gt(.25)|g.fresh_imputed_fraction.gt(.25)).sum()))
            for threshold,label in [(0,'0'),(1e-6,'1e-6'),(1e-3,'1e-3'),(.01,'0.01')]:record['same_grid_max_log_difference_le_'+label]=int(g.maximum_log_difference.le(threshold).sum())
            summaries.append(record)
        frames=[]
        for path in entry['scores']:
            d=pd.read_csv(ROOT/path,usecols=lambda c:c in wanted,dtype={'truth_lag':str},float_precision='round_trip');d=d[(d.input_mode=='actual')&(d.variant=='native')&(d.truth_lag=='56')&(~d.known_target)]
            if 'unit_id' not in d:d['unit_id']=d.pathogen
            frames.append(d)
        scores=pd.concat(frames,ignore_index=True);assert not scores.duplicated(KEY+['model','source_age_weeks']).any()
        for reference in ['ensemble','ensemble_extended','rolling_best_classical','pooled_hgb']:
            ref=scores[(scores.model==reference)&(scores.source_age_weeks==0)]
            if ref.empty:continue
            for model in ['chronos_bolt_base','timesfm_2p5']:
                for age in [1,2]:
                    old=scores[(scores.model==model)&(scores.source_age_weeks==age)];p=old.merge(ref,on=KEY,suffixes=('_candidate','_reference'),validate='one_to_one').merge(pairs[pairs.source_age_weeks==age],on=KEY,validate='one_to_one')
                    for period in ['all_test','year2026']:
                        start=cfg['test_start'] if period=='all_test' else ('2026-01-05' if cfg['issue_frequency']=='W-MON' else '2026-01-02')
                        if model=='timesfm_2p5':start=max(start,cfg['timesfm_interpretation_start'])
                        test=p[p.issue_date.between(start,cfg['test_end'])]
                        for level,g in test.groupby('unit_level',sort=True):
                            masks={'all':np.ones(len(g),dtype=bool),'both_without_imputation':g.old_imputed_fraction.eq(0)&g.fresh_imputed_fraction.eq(0),'both_imputed_at_most_point1':g.old_imputed_fraction.le(.1)&g.fresh_imputed_fraction.le(.1),'both_imputed_at_most_point25':g.old_imputed_fraction.le(.25)&g.fresh_imputed_fraction.le(.25),'either_imputed_over_point25':g.old_imputed_fraction.gt(.25)|g.fresh_imputed_fraction.gt(.25),'same_grid_float32_identical':g.float32_exact,'same_grid_max_difference_le_1e-6':g.maximum_log_difference.le(1e-6)}
                            for label,mask in masks.items():
                                sub=g.loc[mask]
                                if sub.empty:continue
                                for metric in ['wis','mae']:
                                    for block in cfg['bootstrap_blocks']:
                                        seed=int.from_bytes(hashlib.sha256(f"{cfg['seed']}|input-quality|{entry['name']}|{level}|{reference}|{model}|{age}|{period}|{label}|{metric}|{block}".encode()).digest()[:8],'little');stats=panel.bootstrap(sub,metric,start,cfg,block,seed);comparisons.append(dict(dataset=entry['name'],unit_level=level,reference_model=reference,model=model,source_age_weeks=age,period=period,stratum=label,metric=metric,block_weeks=block,n_pairs=len(sub),n_issue_weeks=sub.issue_date.nunique(),n_units=sub.unit_id.nunique(),recorded_exact=int(sub.recorded_exact.sum()),float32_exact=int(sub.float32_exact.sum()),**stats))
    pd.concat(all_pairs,ignore_index=True).to_csv(out/'input-pairs.csv.gz',index=False,compression={'method':'gzip','mtime':0});pd.DataFrame(summaries).to_csv(out/'similarity-summary.csv',index=False);pd.DataFrame(comparisons).to_csv(out/'comparisons.csv',index=False);summary=dict(input_pair_rows=sum(len(x) for x in all_pairs),input_summary_rows=len(summaries),comparison_rows=len(comparisons),exploratory=True,similarity_thresholds_not_biological_equivalence=True,imputation_provenance_from_per_release_cases=True,ai_api_required=False,network_required=False);(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
