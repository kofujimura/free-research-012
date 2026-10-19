"""Expanded fixed ensemble and genuine past-outcome classical selection."""
import argparse,json,pathlib
import numpy as np
import pandas as pd
import analyze as a
from prepare_inputs import ROOT,load_config

POOL=['autoarima','autoets','damped_trend','autotheta','seasonal_naive','harmonic_arima']

def json_scalar(x):
    if isinstance(x,np.generic):return x.item()
    raise TypeError('Unsupported JSON type: '+type(x).__name__)

def add_competitors(native,truth,cfg):
    keys=a.KEY+['input_mode','source_age_weeks'];expanded=[]
    for key,g in native.groupby(keys,sort=True):
        selected=g[g.model.isin(POOL)]
        if set(selected.model)!=set(POOL):continue
        r=g[g.model=='ensemble'].iloc[0].to_dict();r['model']='ensemble_extended'
        values=selected[a.QCOLS].mean(axis=0).to_numpy();r.update(dict(zip(a.QCOLS,map(float,values))))
        # Average of forecast paths is compatible with average of the two medians.
        r['growth_score']=float(selected.growth_score.mean());expanded.append(r)
    native=pd.concat([native,pd.DataFrame(expanded)],ignore_index=True)
    scored,_=a.score(native[(native.input_mode=='actual')&native.model.isin(POOL+['naive'])],truth[truth.truth_lag=='56'],cfg)
    selected_rows=[];logs=[]
    group=['pathogen','source_age_weeks','target_offset_days']
    available=native[(native.input_mode=='actual')&native.model.isin(POOL+['naive'])]
    for key,current_group in available.groupby(group,sort=True):
        g=scored[(scored.pathogen==key[0])&(scored.source_age_weeks==key[1])&(scored.target_offset_days==key[2])].sort_values(['issue_date','model'])
        deadline=pd.to_datetime(g.truth_deadline,utc=True)
        for issue in sorted(current_group.issue_date.unique()):
            current=current_group[current_group.issue_date==issue];issue_stamp=pd.Timestamp(current.iloc[0].issue_at_utc)
            past=g[deadline<issue_stamp];dates=sorted(past.issue_date.unique())[-26:];past=past[past.issue_date.isin(dates)]
            if len(dates)<12:
                logs.append(dict(zip(group,key))|dict(issue_date=issue,n_past_cases=len(dates),status='insufficient_history'));continue
            scores=past.groupby('model').wis.mean().sort_index().sort_values(kind='stable')
            chosen=str(scores.index[0]);row=current[current.model==chosen]
            if len(row)!=1:raise ValueError('Current classical candidate unavailable')
            # Take only native forecast columns: reference values must not leak into output.
            r=native[(native.input_mode=='actual')&(native.model==chosen)&(native.issue_date==issue)&(native.pathogen==key[0])&(native.source_age_weeks==key[1])&(native.target_offset_days==key[2])].iloc[0].to_dict()
            r['model']='rolling_best_classical';selected_rows.append(r)
            logs.append(dict(zip(group,key))|dict(issue_date=issue,n_past_cases=len(dates),status='ok',chosen_model=chosen,past_scores=scores.to_dict(),latest_reference_deadline=str(pd.to_datetime(past.truth_deadline,utc=True).max())))
    return pd.concat([native,pd.DataFrame(selected_rows)],ignore_index=True),logs

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args();out=pathlib.Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True);cfg=load_config()
    a.MODELS=a.MODELS+['autotheta','seasonal_naive','harmonic_arima'];a.FORECAST_DIRS=a.FORECAST_DIRS+['experiments/E013-extra-classical']
    cases,truth,native,inputs=a.assemble(cfg)
    native,choices=add_competitors(native,truth,cfg)
    (out/'selector.jsonl').write_text(''.join(json.dumps(r,allow_nan=False,default=json_scalar)+'\n' for r in choices))
    cal,status=a.calibrate(native,truth,cfg);fc=pd.concat([native,cal],ignore_index=True)
    fc.to_csv(out/'case-forecasts.csv.gz',index=False,compression={'method':'gzip','mtime':0});status.to_csv(out/'calibration-status.csv',index=False)
    scored,wischeck=a.score(fc,truth,cfg)
    # Retain only newly added competitors in the case score artifact; originals reproduce in E011.
    extra_names=['autotheta','seasonal_naive','harmonic_arima','ensemble_extended','rolling_best_classical']
    scored[scored.model.isin(extra_names)].to_csv(out/'case-extra-scores.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    results=[]
    for reference in ['ensemble_extended','rolling_best_classical']:
        temporary=scored.copy();temporary.loc[temporary.model=='ensemble','model']='original_ensemble';temporary.loc[temporary.model==reference,'model']='ensemble'
        comp=a.comparisons(temporary,cfg);comp['reference_model']=reference
        comp.loc[comp.model=='ensemble','model']=reference
        results.append(comp)
    comparisons=pd.concat(results,ignore_index=True);comparisons.to_csv(out/'comparisons.csv',index=False)
    d=scored[(scored.issue_date>=cfg['test_start'])&(~scored.known_target)]
    d=d[(d.model!='timesfm_2p5')|(d.issue_date>=cfg['timesfm_interpretation_start'])]
    group=['truth_lag','input_mode','variant','model','source_age_weeks','target_offset_days']
    aggregate=d.groupby(group).agg(n=('wis','size'),wis=('wis','mean'),mae=('mae','mean'),covered80=('covered80','mean'),growth_mae=('growth_mae','mean')).reset_index()
    aggregate.to_csv(out/'model-scores.csv',index=False)
    summary=dict(extended_native_rows=len(native),calibrated_rows=len(cal),selector_rows=len(choices),selected_rows=int((native.model=='rolling_best_classical').sum()),comparison_rows=len(comparisons),wis_identity_max_error=wischeck,exploratory=True,selection_uses_only_previously_matured_references=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
