"""Exploratory, jointly paired model-by-information-age loss comparisons."""
import argparse,hashlib,json,math,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT,load_config

KEY=['issue_date','unit_id','pathogen','target_date','target_offset_days']
Q=['q10','q20','q30','q40','q50','q60','q70','q80','q90']
MODELS=['chronos_bolt_base','timesfm_2p5']
REFS=['ensemble','ensemble_extended','rolling_best_classical','pooled_hgb']

def ratio(a,b):
    a,b=np.broadcast_arrays(a,b);return np.divide(a,b,out=np.full(a.shape,np.nan),where=b>0)

def statistics(sums,count):
    fo,ff,ro,rf=np.moveaxis(sums,-1,0)
    fpen=ratio(fo,ff);rpen=ratio(ro,rf)
    return dict(foundation_freshness_ratio=fpen,classical_freshness_ratio=rpen,ratio_of_freshness_ratios=ratio(fpen,rpen),loss_increase_interaction=np.divide((fo-ff)-(ro-rf),count,out=np.full_like(fo,np.nan,dtype=float),where=count>0),replacement_ratio=ratio(fo,rf),fresh_skill_ratio=ratio(ff,rf))

def boot(g,metric,start,cfg,block,seed):
    cols=[metric+'_'+x for x in ['fo','ff','ro','rf']];weeks=pd.date_range(start,cfg['test_end'],freq=cfg['issue_frequency']).strftime('%Y-%m-%d');group=g.groupby('issue_date')[cols].sum().reindex(weeks,fill_value=0);counts=g.groupby('issue_date').size().reindex(weeks,fill_value=0).to_numpy();assert int(counts.sum())==len(g)
    values=group.to_numpy();length=min(block,len(weeks));rng=np.random.default_rng(seed);starts=rng.integers(0,len(weeks)-length+1,size=(cfg['bootstrap_repetitions'],math.ceil(len(weeks)/length)));indices=(starts[:,:,None]+np.arange(length)).reshape(cfg['bootstrap_repetitions'],-1)[:,:len(weeks)];draw=statistics(values[indices].sum(axis=1),counts[indices].sum(axis=1));point=statistics(values.sum(axis=0),counts.sum());result={}
    for name,x in point.items():
        sample=draw[name];valid=np.isfinite(sample);bounds=np.quantile(sample[valid],[.025,.975]) if valid.any() else [np.nan,np.nan];result.update({name:float(x),name+'_low':float(bounds[0]),name+'_high':float(bounds[1]),name+'_invalid_bootstrap':int((~valid).sum())})
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--panel',required=True);ap.add_argument('--scores',action='append',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();base=ROOT/args.panel;out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);cfg=json.loads((base/'panel-config.json').read_text()) if (base/'panel-config.json').exists() else dict(load_config(),issue_frequency='W-FRI');parts=[]
    for path in args.scores:
        d=pd.read_csv(ROOT/path,dtype={'truth_lag':str},float_precision='round_trip');d=d[(d.truth_lag=='56')&(d.input_mode=='actual')&(d.variant=='native')&(~d.known_target)]
        if 'unit_id' not in d:d['unit_id']=d.pathogen;d['unit_level']='national'
        for c in ['active2026','source_floor_fraction','truth_floor_fraction']:
            if c not in d:d[c]=np.nan
        parts.append(d)
    data=pd.concat(parts,ignore_index=True);assert not data.duplicated(KEY+['model','source_age_weeks']).any();rows=[];coverage=[];checks=[]
    meta=['unit_level','input_id','last_date','active2026','source_floor_fraction','truth_floor_fraction']
    def frame(model,age,suffix,metadata=False):
        d=data[(data.model==model)&(data.source_age_weeks==age)][KEY+['wis','mae']+Q+(meta if metadata else [])].copy()
        return d.rename(columns={c:c+'_'+suffix for c in d if c not in KEY})
    for model in MODELS:
        for reference in [r for r in REFS if r in set(data.model)]:
            for age in [1,2]:
                old=frame(model,age,'fo',True);fresh=frame(model,0,'ff',True);p=old.merge(fresh,on=KEY,validate='one_to_one').merge(frame(reference,age,'ro'),on=KEY,validate='one_to_one').merge(frame(reference,0,'rf'),on=KEY,validate='one_to_one')
                p['information']=np.select([p.input_id_fo==p.input_id_ff,p.last_date_fo==p.last_date_ff,p.last_date_fo<p.last_date_ff],['identical','same_end_revised','new_observations'],default='fresh_end_older');p['advance']=(pd.to_datetime(p.last_date_ff)-pd.to_datetime(p.last_date_fo)).dt.days/7
                p['same_foundation_prediction']=(np.max(np.abs(p[[c+'_fo' for c in Q]].to_numpy()-p[[c+'_ff' for c in Q]].to_numpy()),axis=1)<=1e-7);p['same_classical_prediction']=(np.max(np.abs(p[[c+'_ro' for c in Q]].to_numpy()-p[[c+'_rf' for c in Q]].to_numpy()),axis=1)<=1e-7)
                identical=p.information=='identical';assert p.loc[identical,'same_foundation_prediction'].all()
                if reference!='rolling_best_classical':assert p.loc[identical,'same_classical_prediction'].all()
                checks.append(dict(model=model,reference_model=reference,source_age_weeks=age,same_input_cases=int(identical.sum()),same_input_foundation_predictions_match=True,same_input_reference_predictions_match=bool(p.loc[identical,'same_classical_prediction'].all()),reference_strategy_can_select_different_models=reference=='rolling_best_classical'))
                for period in ['all_test','year2026']:
                    start=cfg['test_start'] if period=='all_test' else ('2026-01-05' if cfg['issue_frequency']=='W-MON' else '2026-01-02')
                    if model=='timesfm_2p5':start=max(start,cfg['timesfm_interpretation_start'])
                    candidate=old[old.issue_date.between(start,cfg['test_end'])];test=p[p.issue_date.between(start,cfg['test_end'])]
                    coverage.append(dict(model=model,reference_model=reference,source_age_weeks=age,period=period,eligible_old_foundation_scores=len(candidate),four_prediction_pairs=len(test),excluded_without_all_four=len(candidate)-len(test)))
                    for level,g in test.groupby('unit_level_fo',sort=True):
                        strata={'all':np.ones(len(g),dtype=bool)}
                        for info in ['identical','same_end_revised','new_observations','fresh_end_older']:strata['information:'+info]=g.information==info
                        for advance in [0,1,2]:strata['advance_weeks:'+str(advance)]=g.advance==advance
                        strata['advance_weeks:3+']=g.advance>=3
                        for pathogen in sorted(g.pathogen.unique()):strata['pathogen:'+pathogen]=g.pathogen==pathogen
                        if level=='site':
                            strata['active2026']=g.active2026_fo.fillna(False).astype(bool);strata['reference_above_floor']=g.truth_floor_fraction_fo.eq(0);strata['reference_floor_majority']=g.truth_floor_fraction_fo.ge(.5)
                        for label,mask in strata.items():
                            sub=g.loc[mask]
                            if sub.empty:continue
                            for metric in ['wis','mae']:
                                for block in cfg['bootstrap_blocks']:
                                    seed=int.from_bytes(hashlib.sha256(f"{cfg['seed']}|freshness-interaction|{model}|{reference}|{age}|{period}|{level}|{label}|{metric}|{block}".encode()).digest()[:8],'little');stats=boot(sub,metric,start,cfg,block,seed);means={x:float(sub[metric+'_'+x].mean()) for x in ['fo','ff','ro','rf']};error=abs(stats['replacement_ratio']-stats['foundation_freshness_ratio']*stats['fresh_skill_ratio'])
                                    assert not np.isfinite(error) or error<=1e-12
                                    rows.append(dict(model=model,reference_model=reference,source_age_weeks=age,period=period,unit_level=level,stratum=label,metric=metric,block_weeks=block,n_pairs=len(sub),n_units=sub.unit_id.nunique(),n_issue_weeks=sub.issue_date.nunique(),same_input_count=int((sub.information=='identical').sum()),same_foundation_prediction_count=int(sub.same_foundation_prediction.sum()),same_classical_prediction_count=int(sub.same_classical_prediction.sum()),**{x+'_mean_loss':v for x,v in means.items()},**{x+'_zero_losses':int(sub[metric+'_'+x].eq(0).sum()) for x in means},decomposition_identity_error=error,**stats))
    pd.DataFrame(rows).to_csv(out/'comparisons.csv',index=False);pd.DataFrame(coverage).to_csv(out/'four-prediction-availability.csv',index=False);(out/'same-input-checks.json').write_text(json.dumps(checks,indent=2)+'\n');result=dict(comparison_rows=len(rows),four_prediction_availability_rows=len(coverage),same_input_checks=len(checks),exploratory=True,joint_four_prediction_week_block_bootstrap=True,causal_effect_claimed=False,ai_api_required=False,network_required=False);(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
