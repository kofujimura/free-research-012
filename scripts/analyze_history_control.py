"""Matched four-forecast history-length sensitivity; saved predictions only."""
import argparse,hashlib,json,math,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT
from analyze_freshness_interaction import KEY,Q,ratio

MODELS=['chronos_bolt_base','timesfm_2p5']
REFS=['ensemble','ensemble_extended','rolling_best_classical']

def statistics(v,n):
    fs,fl,rs,rl=np.moveaxis(v,-1,0)
    return dict(baseline_ratio=ratio(fs,rs),extended_candidate_ratio=ratio(fl,rs),extended_both_ratio=ratio(fl,rl),candidate_long_short_ratio=ratio(fl,fs),reference_long_short_ratio=ratio(rl,rs),change_same_reference_ratio=ratio(fl-fs,rs),change_both_ratio=ratio(fl,rl)-ratio(fs,rs))

def bootstrap(d,metric,start,cfg,block,seed):
    cols=[metric+'_'+x for x in ['fs','fl','rs','rl']];weeks=pd.date_range(start,cfg['test_end'],freq=cfg['issue_frequency']).strftime('%Y-%m-%d');v=d.groupby('issue_date')[cols].sum().reindex(weeks,fill_value=0).to_numpy();n=d.groupby('issue_date').size().reindex(weeks,fill_value=0).to_numpy();assert n.sum()==len(d)
    length=min(block,len(weeks));rng=np.random.default_rng(seed);ix=(rng.integers(0,len(weeks)-length+1,size=(cfg['bootstrap_repetitions'],math.ceil(len(weeks)/length)))[:,:,None]+np.arange(length)).reshape(cfg['bootstrap_repetitions'],-1)[:,:len(weeks)]
    point=statistics(v.sum(axis=0),n.sum());draw=statistics(v[ix].sum(axis=1),n[ix].sum(axis=1));out={}
    for k,value in point.items():
        valid=np.isfinite(draw[k]);bounds=np.quantile(draw[k][valid],[.025,.975]) if valid.any() else [np.nan,np.nan];out.update({k:float(value),k+'_low':float(bounds[0]),k+'_high':float(bounds[1]),k+'_invalid_bootstrap':int((~valid).sum())})
    return out

def read(paths):
    frames=[]
    for p in paths:
        d=pd.read_csv(ROOT/p,dtype={'truth_lag':str},float_precision='round_trip');d=d[(d.truth_lag=='56')&(d.input_mode=='actual')&(d.variant=='native')&(~d.known_target)]
        if 'unit_id' not in d:d['unit_id']=d.pathogen;d['unit_level']='national'
        frames.append(d)
    result=pd.concat(frames,ignore_index=True);assert not result.duplicated(KEY+['model','source_age_weeks']).any();return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--assembled',required=True);ap.add_argument('--original-map',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();assembled=pathlib.Path(args.assembled);out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);defs=json.loads((assembled/'panels.json').read_text());original_map=json.loads((ROOT/args.original_map).read_text());rows=[];availability=[];compatibility=[];checks=[]
    for dataset in sorted({x['dataset'] for x in defs}):
        definitions={x['maximum_context']:x for x in defs if x['dataset']==dataset};cfg=json.loads((ROOT/definitions[104]['panel']/'panel-config.json').read_text());short=read([str(assembled/definitions[104]['analysis_directory']/'case-scores.csv.gz')]);long=read([str(assembled/definitions[256]['analysis_directory']/'case-scores.csv.gz')]);original=read(original_map[dataset]);pooled=original[original.model=='pooled_hgb'];refs=REFS+(['pooled_hgb'] if len(pooled) else [])
        # This diagnostic separates the TF compile-limit change from history length.
        old=original[original.model.isin(MODELS)];new=short[short.model.isin(MODELS)];oldnew=new.merge(old,on=KEY+['model','source_age_weeks'],suffixes=('_new','_old'),validate='one_to_one')
        for model,g in oldnew.groupby('model'):
            qdiff=np.max(np.abs(g[[c+'_new' for c in Q]].to_numpy()-g[[c+'_old' for c in Q]].to_numpy()),axis=1);compatibility.append(dict(dataset=dataset,model=model,n_pairs=len(g),max_quantile_absolute_difference=float(qdiff.max()),changed_predictions_over_1e7=int((qdiff>1e-7).sum()),mean_wis_new_minus_old=float((g.wis_new-g.wis_old).mean()),timesfm_compile_limit_old=128 if model=='timesfm_2p5' else None,timesfm_compile_limit_new=256 if model=='timesfm_2p5' else None))
        def frame(data,model,age,suffix):
            cols=KEY+['wis','mae',*Q,'unit_level','input_id','last_date','context_length'];d=data[(data.model==model)&(data.source_age_weeks==age)][cols].copy();return d.rename(columns={c:c+'_'+suffix for c in d if c not in KEY})
        for model in MODELS:
            for reference in refs:
                refshort=pooled if reference=='pooled_hgb' else short;reflong=pooled if reference=='pooled_hgb' else long
                for age in [0,1,2]:
                    fs=frame(short,model,age,'fs');p=fs.merge(frame(long,model,age,'fl'),on=KEY,validate='one_to_one').merge(frame(refshort,reference,0,'rs'),on=KEY,validate='one_to_one').merge(frame(reflong,reference,0,'rl'),on=KEY,validate='one_to_one')
                    p['candidate_extended']=p.input_id_fs!=p.input_id_fl;p['reference_extended']=p.input_id_rs!=p.input_id_rl;p['new_observations']=p.last_date_fs<p.last_date_rs
                    for side in ['candidate','reference']:
                        s,l=('fs','fl') if side=='candidate' else ('rs','rl');p['same_'+side+'_prediction']=np.max(np.abs(p[[q+'_'+s for q in Q]].to_numpy()-p[[q+'_'+l for q in Q]].to_numpy()),axis=1)<=1e-7
                        same=p.input_id_fs==p.input_id_fl if side=='candidate' else p.input_id_rs==p.input_id_rl
                        # Rolling selection may differ because past long histories differ.
                        must_match=side=='candidate' or reference not in ['rolling_best_classical']
                        if must_match:assert p.loc[same,'same_'+side+'_prediction'].all()
                        checks.append(dict(dataset=dataset,model=model,reference_model=reference,source_age_weeks=age,side=side,unchanged_input_count=int(same.sum()),unchanged_input_prediction_mismatch=int((~p.loc[same,'same_'+side+'_prediction']).sum()),matching_required=must_match))
                    for period in ['all_test','year2026']:
                        start=cfg['test_start'] if period=='all_test' else ('2026-01-05' if cfg['issue_frequency']=='W-MON' else '2026-01-02')
                        if model=='timesfm_2p5':start=max(start,cfg['timesfm_interpretation_start'])
                        test=p[p.issue_date.between(start,cfg['test_end'])];eligible=fs.issue_date.between(start,cfg['test_end']).sum();availability.append(dict(dataset=dataset,model=model,reference_model=reference,source_age_weeks=age,period=period,eligible_short_candidate_scores=int(eligible),four_prediction_pairs=len(test),missing_any_pair=int(eligible)-len(test)))
                        for level,g in test.groupby('unit_level_fs',sort=True):
                            strata={'all':np.ones(len(g),dtype=bool),'candidate_extended':g.candidate_extended,'candidate_unchanged':~g.candidate_extended,'both_extended':g.candidate_extended&g.reference_extended,'new_observations':g.new_observations,'extended_and_new_observations':g.candidate_extended&g.new_observations}
                            for pathogen in sorted(g.pathogen.unique()):strata['pathogen:'+pathogen]=g.pathogen==pathogen
                            for label,mask in strata.items():
                                sub=g.loc[mask]
                                if sub.empty:continue
                                for metric in ['wis','mae']:
                                    for block in cfg['bootstrap_blocks']:
                                        seed=int.from_bytes(hashlib.sha256(f"{cfg['seed']}|history-control|{dataset}|{model}|{reference}|{age}|{period}|{level}|{label}|{metric}|{block}".encode()).digest()[:8],'little');stats=bootstrap(sub,metric,start,cfg,block,seed)
                                        rows.append(dict(dataset=dataset,unit_level=level,model=model,reference_model=reference,source_age_weeks=age,period=period,stratum=label,metric=metric,block_weeks=block,n_pairs=len(sub),n_units=sub.unit_id.nunique(),n_issue_weeks=sub.issue_date.nunique(),candidate_extended_count=int(sub.candidate_extended.sum()),reference_extended_count=int(sub.reference_extended.sum()),same_candidate_prediction_count=int(sub.same_candidate_prediction.sum()),same_reference_prediction_count=int(sub.same_reference_prediction.sum()),**{side+'_mean_loss':float(sub[metric+'_'+side].mean()) for side in ['fs','fl','rs','rl']},**stats))
    pd.DataFrame(rows).to_csv(out/'comparisons.csv',index=False);pd.DataFrame(availability).to_csv(out/'availability.csv',index=False);pd.DataFrame(compatibility).to_csv(out/'original-short-compatibility.csv',index=False);(out/'unchanged-input-checks.json').write_text(json.dumps(checks,indent=2)+'\n');result=dict(comparison_rows=len(rows),availability_rows=len(availability),compatibility_rows=len(compatibility),exploratory=True,causal_effect_claimed=False,pooled_history_unchanged_supplementary=True);(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
