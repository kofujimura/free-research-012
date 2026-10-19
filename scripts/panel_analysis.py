"""Exploratory panel comparisons, calibrated and selected within each unit only."""
import argparse,hashlib,json,math,pathlib
import numpy as np
import pandas as pd
import analyze as a
from analyze_extra_baselines import POOL
from prepare_inputs import ROOT

KEY=['issue_date','unit_id','pathogen','target_date','target_offset_days']
GROUP=['unit_id','pathogen','source_age_weeks','target_offset_days']
EXTRA=['autotheta','seasonal_naive','harmonic_arima']

def learning_truth(truth):
    d=truth[truth.truth_lag=='56'].copy()
    if 'training_available_at' in d:d['truth_deadline']=d['training_available_at']
    return d[KEY+['y_log','truth_deadline']]

def add_competitors(native,truth,cfg):
    keys=KEY+['input_mode','source_age_weeks']
    means=native[native.model.isin(POOL)].groupby(keys,sort=True)[a.QCOLS+['growth_score']].mean().reset_index()
    counts=native[native.model.isin(POOL)].groupby(keys).model.nunique()
    if not (counts==len(POOL)).all():raise ValueError('Incomplete fixed-ensemble components')
    meta=native[native.model=='ensemble'].drop(columns=a.QCOLS+['growth_score'])
    extended=meta.merge(means,on=keys,validate='one_to_one');extended['model']='ensemble_extended'
    native=pd.concat([native,extended],ignore_index=True)
    prior=native[native.model.isin(POOL+['naive'])].merge(learning_truth(truth),on=KEY,validate='many_to_one')
    error=prior.y_log.to_numpy()[:,None]-prior[a.QCOLS].to_numpy();qs=np.asarray(cfg['quantiles'])
    prior['wis']=2*np.maximum(qs*error,(qs-1)*error).mean(axis=1)
    selected=[];logs=[]
    for key,g in prior.groupby(GROUP,sort=True):
        wide=g.pivot(index='issue_date',columns='model',values='wis').sort_index();names=sorted(wide.columns);wide=wide[names]
        info=g.drop_duplicates('issue_date').set_index('issue_date').loc[wide.index]
        deadlines=pd.to_datetime(info.truth_deadline,utc=True).to_numpy();values=wide.to_numpy()
        current={(r['issue_date'],r['model']):r for r in g.drop(columns=['y_log','truth_deadline','wis']).to_dict('records')}
        for i,date in enumerate(wide.index):
            stamp=pd.Timestamp(info.iloc[i].issue_at_utc);past=np.where((deadlines<stamp)&np.isfinite(values).all(axis=1))[0][-26:]
            log=dict(zip(GROUP,key));log.update(issue_date=date,n_past_cases=len(past),status='insufficient_history')
            if len(past)>=12:
                scores=values[past].mean(axis=0);j=int(np.argmin(scores));chosen=names[j]
                row=dict(current[(date,chosen)],model='rolling_best_classical');selected.append(row)
                log.update(status='ok',chosen_model=chosen,past_scores=dict(zip(names,map(float,scores))),latest_reference_deadline=str(max(deadlines[past])))
            logs.append(log)
    return pd.concat([native,pd.DataFrame(selected)],ignore_index=True),logs

def calibrate(native,truth,cfg):
    merged=native.merge(learning_truth(truth),on=KEY,validate='many_to_one')
    output=[];statuses=[]
    for key,g in merged.groupby(['model']+GROUP,sort=True):
        g=g.sort_values('issue_date');deadlines=pd.to_datetime(g.truth_deadline,utc=True).to_numpy();y=g.y_log.to_numpy();point=g.q50.to_numpy();residual=y-point
        rows=g.to_dict('records')
        for row in rows:
            selected=np.where((deadlines<pd.Timestamp(row['issue_at_utc']))&np.isfinite(residual))[0][-cfg['calibration_maximum']:]
            n=len(selected);statuses.append({k:row[k] for k in KEY+['model','source_age_weeks']}|dict(n_calibration=n,calibration_available=n>=cfg['calibration_minimum']))
            if n<cfg['calibration_minimum']:continue
            new=dict(row,variant='calibrated',calibration_n=n);new.pop('y_log');new.pop('truth_deadline')
            new.update(dict(zip(a.QCOLS,map(float,row['q50']+np.quantile(residual[selected],cfg['quantiles'],method='linear')))));output.append(new)
    return pd.DataFrame(output),pd.DataFrame(statuses)

def bootstrap(pairs,metric,start,cfg,block,seed):
    weeks=pd.date_range(start,cfg['test_end'],freq=cfg['issue_frequency']).strftime('%Y-%m-%d')
    g=pairs.groupby('issue_date').agg(a=(metric+'_candidate','sum'),b=(metric+'_reference','sum'),n=(metric+'_candidate','size')).reindex(weeks,fill_value=0)
    if int(g.n.sum())!=len(pairs):raise ValueError('Bootstrap calendar omits paired cases')
    aa=g.a.to_numpy();bb=g.b.to_numpy();nn=g.n.to_numpy();length=min(block,len(g));reps=cfg['bootstrap_repetitions'];rng=np.random.default_rng(seed)
    starts=rng.integers(0,len(g)-length+1,size=(reps,math.ceil(len(g)/length)));ix=(starts[:,:,None]+np.arange(length)).reshape(reps,-1)[:,:len(g)]
    ra=aa[ix].sum(axis=1);rb=bb[ix].sum(axis=1);rn=nn[ix].sum(axis=1);good=(rb>0)&(rn>0)
    def bounds(x):return list(map(float,np.quantile(x,[.025,.975]))) if len(x) else [np.nan,np.nan]
    rl,rh=bounds(ra[good]/rb[good]);dl,dh=bounds((ra[good]-rb[good])/rn[good])
    return dict(ratio=float(aa.sum()/bb.sum()) if bb.sum()>0 else np.nan,difference=float((aa.sum()-bb.sum())/nn.sum()),ratio_low=rl,ratio_high=rh,difference_low=dl,difference_high=dh,invalid_bootstrap=int((~good).sum()))

def compare(scored,cfg):
    output=[]
    for lag in sorted(scored.truth_lag.unique()):
        for variant in ['native','calibrated']:
            d=scored[(scored.truth_lag==lag)&(scored.variant==variant)&(~scored.known_target)]
            for reference in cfg.get('comparison_reference_models',['ensemble','ensemble_extended','rolling_best_classical']):
                ref=d[(d.model==reference)&(d.source_age_weeks==0)]
                for model in ['chronos_bolt_base','timesfm_2p5']:
                    for age in cfg['source_age_weeks']:
                        candidate=d[(d.model==model)&(d.source_age_weeks==age)]
                        p=candidate.merge(ref,on=KEY,suffixes=('_candidate','_reference'),validate='one_to_one')
                        for period in ['all_test','year2026']:
                            start=cfg['test_start'] if period=='all_test' else ('2026-01-05' if cfg['issue_frequency']=='W-MON' else '2026-01-02')
                            if model=='timesfm_2p5':start=max(start,cfg['timesfm_interpretation_start'])
                            s=p[p.issue_date.between(start,cfg['test_end'])].copy()
                            if s.empty:continue
                            s['information']=np.select([s.input_id_candidate==s.input_id_reference,s.last_date_candidate==s.last_date_reference,s.last_date_candidate<s.last_date_reference],['identical','same_end_revised','new_observations'],default='fresh_end_older')
                            s['advance_weeks']=(pd.to_datetime(s.last_date_reference)-pd.to_datetime(s.last_date_candidate)).dt.days/7
                            strata={'all':np.ones(len(s),dtype=bool)}
                            for level in sorted(s.unit_level_candidate.unique()):strata['level:'+level]=s.unit_level_candidate==level
                            for pathogen in cfg['pathogens']:strata['pathogen:'+pathogen]=s.pathogen==pathogen
                            for offset in cfg['target_offsets_days']:strata['target_offset:'+str(offset)]=s.target_offset_days==offset
                            if lag=='56':
                                for label in ['identical','same_end_revised','new_observations','fresh_end_older']:strata['information:'+label]=s.information==label
                                for n in [0,1,2]:strata['advance_weeks:'+str(n)]=s.advance_weeks==n
                                strata['advance_weeks:3+']=s.advance_weeks>=3
                                if 'active2026_candidate' in s:strata['active2026']=s.active2026_candidate.fillna(False).astype(bool)
                                strata['reference_above_floor']=s.truth_floor_fraction_reference.eq(0)
                                strata['reference_floor_majority']=s.truth_floor_fraction_reference.ge(.5)
                                strata['source_floor_majority']=s.source_floor_fraction_candidate.ge(.5) if 'source_floor_fraction_candidate' in s else np.zeros(len(s),dtype=bool)
                            for label,mask in strata.items():
                                sub=s.loc[mask]
                                if sub.empty:continue
                                for metric in ['wis','mae']:
                                    for block in cfg['bootstrap_blocks'] if lag=='56' else [cfg['bootstrap_primary_block']]:
                                        seed=int.from_bytes(hashlib.sha256(f"{cfg['seed']}|panel|{lag}|{variant}|{reference}|{model}|{age}|{period}|{label}|{metric}|{block}".encode()).digest()[:8],'little')
                                        stats=bootstrap(sub,metric,start,cfg,block,seed)
                                        same=np.max(np.abs(sub[[q+'_candidate' for q in a.QCOLS]].to_numpy()-sub[[q+'_reference' for q in a.QCOLS]].to_numpy()),axis=1)<=1e-7
                                        output.append(dict(truth_lag=lag,variant=variant,reference_model=reference,model=model,source_age_weeks=age,period=period,stratum=label,metric=metric,block_weeks=block,n_pairs=len(sub),n_issue_weeks=sub.issue_date.nunique(),n_units=sub.unit_id.nunique(),candidate_mean=float(sub[metric+'_candidate'].mean()),reference_mean=float(sub[metric+'_reference'].mean()),same_input_count=int((sub.information=='identical').sum()),same_end_revised_count=int((sub.information=='same_end_revised').sum()),new_observations_count=int((sub.information=='new_observations').sum()),same_prediction_count=int(same.sum()),known_target_count=int(sub.known_target_candidate.sum()|sub.known_target_reference.sum()),**stats))
    return pd.DataFrame(output)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--panel',required=True);ap.add_argument('--forecast-dir',action='append',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();base=ROOT/args.panel;out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((base/'panel-config.json').read_text());a.KEY=KEY;a.INPUT_DIR=args.panel;a.FORECAST_DIRS=args.forecast_dir;a.MODELS=a.MODELS+EXTRA
    cases,truth,native,inputs=a.assemble(cfg)
    if 'truth_floor_fraction' not in truth:truth['truth_floor_fraction']=np.nan
    native,logs=add_competitors(native,truth,cfg)
    (out/'selector.jsonl').write_text(''.join(json.dumps(x,default=lambda v:v.item() if isinstance(v,np.generic) else str(v))+'\n' for x in logs))
    cal,status=calibrate(native,truth,cfg);fc=pd.concat([native,cal],ignore_index=True);scored,check=a.score(fc,truth,cfg)
    fc.to_csv(out/'case-forecasts.csv.gz',index=False,compression={'method':'gzip','mtime':0});status.to_csv(out/'calibration-status.csv.gz',index=False,compression={'method':'gzip','mtime':0});scored.to_csv(out/'case-scores.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    comparisons=compare(scored,cfg);comparisons.to_csv(out/'comparisons.csv',index=False)
    d=scored[scored.issue_date.between(cfg['test_start'],cfg['test_end'])&(~scored.known_target)];d=d[(d.model!='timesfm_2p5')|(d.issue_date>=cfg['timesfm_interpretation_start'])]
    keys=['truth_lag','variant','model','source_age_weeks','target_offset_days','unit_level']
    d.groupby(keys).agg(n=('wis','size'),n_units=('unit_id','nunique'),n_weeks=('issue_date','nunique'),wis=('wis','mean'),mae=('mae','mean'),covered80=('covered80','mean'),width80=('width80','mean'),growth_mae=('growth_mae','mean')).reset_index().to_csv(out/'model-scores.csv',index=False)
    test=cases[cases.issue_date>=cfg['test_start']];test.groupby(['unit_level','source_age_weeks','target_offset_days','status']).size().rename('n').reset_index().to_csv(out/'case-availability.csv',index=False)
    summary=dict(units=len(json.loads((base/'units.json').read_text())),unique_inputs=len(inputs),native_case_predictions=len(native),calibrated_case_predictions=len(cal),scored_rows=len(scored),comparison_rows=len(comparisons),max_wis_identity_error=check,known_target_cases=int(cases.known_target.sum()),exploratory=True,calibration_and_selection_within_unit=True,bootstrap_frequency=cfg['issue_frequency'],ai_api_required=False,network_required=False,model_inference_required=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
