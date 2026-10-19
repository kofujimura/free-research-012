"""Recalculate scores, calibration and paired comparisons from saved forecasts only."""
from __future__ import annotations
import argparse,hashlib,json,math,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT,load_config

QCOLS=['q10','q20','q30','q40','q50','q60','q70','q80','q90']
KEY=['issue_date','pathogen','target_date','target_offset_days']
INPUT_DIR='experiments/E007-prepare-inputs-fixed'
FORECAST_DIRS=['experiments/E008-statistical','experiments/E009-chronos','experiments/E010-timesfm']
MODELS=['naive','damped_trend','autoarima','autoets','ensemble','chronos_bolt_base','timesfm_2p5']

def assemble(cfg,allow_unused_inputs=False,allow_identical_duplicates=False):
    global LAST_ASSEMBLY_AUDIT
    base=ROOT/INPUT_DIR
    cases=pd.read_csv(base/'cases.csv');truth=pd.read_csv(base/'truth.csv',dtype={'truth_lag':str})
    inputs=json.loads((base/'inputs.json').read_text());raw={};duplicate_count=0
    for directory in FORECAST_DIRS:
        p=ROOT/directory
        run=json.loads((p/'run.json').read_text())
        if run['status']!='completed':raise ValueError('Incomplete native generation: '+directory)
        for line in (p/'forecasts.jsonl').read_text().splitlines():
            f=json.loads(line);k=(f['input_id'],f['model'])
            if allow_unused_inputs and f['input_id'] not in inputs:continue
            values=np.asarray(f['quantiles'],dtype=float)
            if k in raw:
                if not allow_identical_duplicates or not np.array_equal(raw[k],values):raise ValueError('Duplicate raw prediction with no authorized exact reuse')
                duplicate_count+=1;continue
            raw[k]=values
    if set(raw)!=set((uid,m) for uid in inputs for m in MODELS):raise ValueError('Native forecast coverage is incomplete')
    rows=[]
    for r in cases.to_dict('records'):
        if r['status']!='ok':continue
        ctx=inputs[r['input_id']];h=int(r['horizon'])
        for model in MODELS:
            q=raw[(r['input_id'],model)]
            def point_at(step):
                return float(q[step-1,4]) if step>0 else float(ctx['log_values'][len(ctx['log_values'])-1+step])
            targetq=q[h-1] if h>0 else np.repeat(point_at(h),9)
            row=dict(r,model=model,variant='native',growth_score=point_at(h)-point_at(h-2))
            row.update(dict(zip(QCOLS,map(float,targetq))));rows.append(row)
    LAST_ASSEMBLY_AUDIT=dict(allow_unused_inputs=allow_unused_inputs,allow_identical_duplicates=allow_identical_duplicates,identical_duplicate_records_skipped=duplicate_count,unique_native_forecasts=len(raw))
    return cases,truth,pd.DataFrame(rows),inputs

def calibrate(fc,truth,cfg):
    maintruth=truth[truth.truth_lag==str(cfg['primary_truth_lag_days'])]
    a=fc[fc.input_mode=='actual'].merge(maintruth[KEY+['y_log','truth_deadline']],on=KEY,how='left',validate='many_to_one')
    calibrated=[];statuses=[]
    groupcols=['model','pathogen','source_age_weeks','target_offset_days']
    for key,g in a.groupby(groupcols,sort=True):
        g=g.sort_values('issue_date').copy();deadlines=pd.to_datetime(g.truth_deadline,utc=True)
        for r in g.to_dict('records'):
            issue=pd.Timestamp(r['issue_at_utc'])
            previous=g[(deadlines<issue)&g.y_log.notna()].tail(cfg['calibration_maximum'])
            count=len(previous)
            statuses.append({**dict(zip(groupcols,key)),**{k:r[k] for k in KEY if k not in groupcols},'n_calibration':count,'calibration_available':count>=cfg['calibration_minimum']})
            if count<cfg['calibration_minimum']:continue
            residual=previous.y_log.to_numpy()-previous.q50.to_numpy()
            values=r['q50']+np.quantile(residual,cfg['quantiles'],method='linear')
            new=dict(r,variant='calibrated',calibration_n=count)
            new.pop('y_log');new.pop('truth_deadline');new.update(dict(zip(QCOLS,map(float,values))))
            calibrated.append(new)
    return pd.DataFrame(calibrated),pd.DataFrame(statuses)

def score(fc,truth,cfg):
    d=fc.merge(truth,on=KEY,how='left',validate='many_to_many')
    d=d[d.y_log.notna()].copy();qs=np.asarray(cfg['quantiles']);q=d[QCOLS].to_numpy();y=d.y_log.to_numpy()
    error=y[:,None]-q;pinball=np.maximum(qs*error,(qs-1)*error)
    d['pinball']=pinball.mean(axis=1);d['wis']=2*d.pinball
    d['mae']=np.abs(d.q50-d.y_log);d['covered80']=(d.y_log>=d.q10)&(d.y_log<=d.q90);d['width80']=d.q90-d.q10
    d['growth_mae']=np.abs(d.growth_score-d.growth_log)
    threshold=np.log10(cfg['rise_ratio'])
    d['phase']=np.select([d.growth_log>=threshold,d.growth_log<=-threshold,d.growth_log.isna()],['rise','decline','unknown'],default='middle')
    # Independently implement WIS from central intervals, not the pinball identity.
    total=.5*np.abs(y-q[:,4])
    for lower,upper,alpha in [(0,8,.2),(1,7,.4),(2,6,.6),(3,5,.8)]:
        lo=q[:,lower];hi=q[:,upper]
        interval=hi-lo+(2/alpha)*(lo-y)*(y<lo)+(2/alpha)*(y-hi)*(y>hi)
        total+=(alpha/2)*interval
    alternative=total/4.5
    check=float(np.max(np.abs(alternative-d.wis.to_numpy())))
    if check>1e-12:raise ValueError('WIS implementations disagree')
    return d,check

def bootstrap(pairs,metric,start,end,block,reps,seed):
    weeks=pd.date_range(start,end,freq='W-FRI').strftime('%Y-%m-%d')
    g=pairs.groupby('issue_date').agg(a=(metric+'_candidate','sum'),b=(metric+'_reference','sum'),n=(metric+'_candidate','size')).reindex(weeks,fill_value=0)
    if g.n.sum()==0:return dict(ratio=np.nan,difference=np.nan,ratio_low=np.nan,ratio_high=np.nan,difference_low=np.nan,difference_high=np.nan,invalid_bootstrap=reps)
    aa=g.a.to_numpy();bb=g.b.to_numpy();nn=g.n.to_numpy()
    length=min(block,len(g));rng=np.random.default_rng(seed)
    starts=rng.integers(0,len(g)-length+1,size=(reps,math.ceil(len(g)/length)))
    ix=(starts[:,:,None]+np.arange(length)).reshape(reps,-1)[:,:len(g)]
    ra=aa[ix].sum(axis=1);rb=bb[ix].sum(axis=1);rn=nn[ix].sum(axis=1)
    good=(rb>0)&(rn>0)
    ratios=ra[good]/rb[good];diffs=(ra[good]-rb[good])/rn[good]
    def bounds(x):return np.quantile(x,[.025,.975]).tolist() if len(x) else [np.nan,np.nan]
    rl,rh=bounds(ratios);dl,dh=bounds(diffs)
    return dict(ratio=float(aa.sum()/bb.sum()) if bb.sum()>0 else np.nan,difference=float((aa.sum()-bb.sum())/nn.sum()),ratio_low=rl,ratio_high=rh,difference_low=dl,difference_high=dh,invalid_bootstrap=int((~good).sum()))

def comparisons(scored,cfg):
    rows=[]
    for lag in ['56','28','84','latest']:
        d=scored[(scored.input_mode=='actual')&(scored.truth_lag==lag)&(~scored.known_target)]
        for variant in ['native','calibrated']:
            v=d[d.variant==variant];ref=v[(v.model=='ensemble')&(v.source_age_weeks==0)]
            for model in ['ensemble','chronos_bolt_base','timesfm_2p5']:
                for age in cfg['source_age_weeks']:
                    candidate=v[(v.model==model)&(v.source_age_weeks==age)]
                    pair=candidate.merge(ref,on=KEY,suffixes=('_candidate','_reference'),validate='one_to_one')
                    for period in ['all_test','year2026']:
                        start=cfg['test_start'] if period=='all_test' else '2026-01-02'
                        if model=='timesfm_2p5':start=max(start,cfg['timesfm_interpretation_start'])
                        p=pair[(pair.issue_date>=start)&(pair.issue_date<=cfg['test_end'])].copy()
                        if p.empty:continue
                        p['info_relation']=np.select([p.input_id_candidate==p.input_id_reference,p.last_date_candidate==p.last_date_reference,p.last_date_candidate<p.last_date_reference],['identical','same_end_revised','new_observations'],default='fresh_end_older')
                        strata={'all':np.ones(len(p),dtype=bool)}
                        for pathogen in cfg['pathogens']:strata['pathogen:'+pathogen]=(p.pathogen==pathogen).to_numpy()
                        for offset in cfg['target_offsets_days']:strata['target_offset:'+str(offset)]=(p.target_offset_days==offset).to_numpy()
                        if lag=='56':
                            for phase in ['rise','middle','decline']:strata['phase:'+phase]=(p.phase_reference==phase).to_numpy()
                            for rel in ['identical','same_end_revised','new_observations','fresh_end_older']:strata['information:'+rel]=(p.info_relation==rel).to_numpy()
                        for label,mask in strata.items():
                            s=p.loc[mask]
                            if s.empty:continue
                            for metric in ['wis','mae']:
                                for block in cfg['bootstrap_blocks'] if lag=='56' else [cfg['bootstrap_primary_block']]:
                                    seedmaterial=f"{cfg['seed']}|{lag}|{variant}|{model}|{age}|{period}|{label}|{metric}|{block}"
                                    seed=int.from_bytes(hashlib.sha256(seedmaterial.encode()).digest()[:8],'little')
                                    b=bootstrap(s,metric,start,cfg['test_end'],block,cfg['bootstrap_repetitions'],seed)
                                    equal=np.max(np.abs(s[[x+'_candidate' for x in QCOLS]].to_numpy()-s[[x+'_reference' for x in QCOLS]].to_numpy()),axis=1)<=1e-7
                                    rows.append(dict(truth_lag=lag,variant=variant,model=model,source_age_weeks=age,period=period,analysis_start=start,analysis_end=cfg['test_end'],stratum=label,metric=metric,block_weeks=block,n_pairs=len(s),n_issue_weeks=s.issue_date.nunique(),candidate_mean=float(s[metric+'_candidate'].mean()),reference_mean=float(s[metric+'_reference'].mean()),same_input_count=int((s.info_relation=='identical').sum()),same_end_revised_count=int((s.info_relation=='same_end_revised').sum()),new_observations_count=int((s.info_relation=='new_observations').sum()),fresh_end_older_count=int((s.info_relation=='fresh_end_older').sum()),same_prediction_count=int(equal.sum()),known_target_count=int(s.known_target_candidate.sum()|s.known_target_reference.sum()),**b))
    return pd.DataFrame(rows)

def alert_analysis(fc,truth,cfg):
    primary=truth[truth.truth_lag=='56']
    a=fc[(fc.input_mode=='actual')&(fc.variant=='native')&(~fc.known_target)].merge(primary,on=KEY,validate='many_to_one')
    a['event']=a.growth_log>=np.log10(cfg['rise_ratio']);a=a[a.growth_log.notna()].copy()
    rows=[]
    groupcols=['model','pathogen','source_age_weeks','target_offset_days']
    for key,g in a.groupby(groupcols,sort=True):
        g=g.sort_values('issue_date').copy();deadline=pd.to_datetime(g.truth_deadline,utc=True)
        for r in g.to_dict('records'):
            previous=g[(deadline<pd.Timestamp(r['issue_at_utc']))&(~g.event)].tail(cfg['calibration_maximum'])
            count=len(previous);threshold=float(np.quantile(previous.growth_score,1-cfg['false_positive_target'])) if count>=cfg['calibration_minimum'] else np.nan
            rows.append(dict(r,threshold=threshold,threshold_n=count,alarm=bool(r['growth_score']>threshold) if np.isfinite(threshold) else None))
    predictions=pd.DataFrame(rows);summaries=[];paired=[]
    for period in ['all_test','year2026']:
        d=predictions[(predictions.issue_date>= (cfg['test_start'] if period=='all_test' else '2026-01-02'))&(predictions.issue_date<=cfg['test_end'])&predictions.threshold.notna()].copy()
        d=d[(d.model!='timesfm_2p5')|(d.issue_date>=cfg['timesfm_interpretation_start'])]
        for (model,age,offset),g in d.groupby(['model','source_age_weeks','target_offset_days']):
            for label,sub in [('all',g),*[(p,g[g.pathogen==p]) for p in cfg['pathogens']]]:
                tp=int((sub.event&sub.alarm.astype(bool)).sum());fp=int((~sub.event&sub.alarm.astype(bool)).sum());pos=int(sub.event.sum());neg=len(sub)-pos
                summaries.append(dict(period=period,model=model,source_age_weeks=int(age),target_offset_days=int(offset),stratum=label,n=len(sub),n_weeks=sub.issue_date.nunique(),positive=pos,negative=neg,tp=tp,fp=fp,false_positive_rate=fp/neg if neg else np.nan,miss_rate=1-tp/pos if pos else np.nan))
        ref=d[(d.model=='ensemble')&(d.source_age_weeks==0)]
        for model in ['chronos_bolt_base','timesfm_2p5']:
            for age in cfg['source_age_weeks']:
                c=d[(d.model==model)&(d.source_age_weeks==age)]
                p=c.merge(ref,on=KEY,suffixes=('_candidate','_reference'),validate='one_to_one')
                for offset in cfg['target_offsets_days']:
                    s=p[p.target_offset_days==offset]
                    for name in ['candidate','reference']:
                        pos=s['event_'+name].astype(bool);alarm=s['alarm_'+name].astype(bool);tp=int((pos&alarm).sum());fp=int((~pos&alarm).sum());npos=int(pos.sum());nneg=len(s)-npos
                        paired.append(dict(period=period,model=model,source_age_weeks=age,target_offset_days=offset,side=name,n=len(s),positive=npos,negative=nneg,tp=tp,fp=fp,miss_rate=1-tp/npos if npos else np.nan,false_positive_rate=fp/nneg if nneg else np.nan))
    return predictions,pd.DataFrame(summaries),pd.DataFrame(paired)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args();out=pathlib.Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    cfg=load_config();cases,truth,native,inputs=assemble(cfg)
    cal,status=calibrate(native,truth,cfg);fc=pd.concat([native,cal],ignore_index=True)
    fc.to_csv(out/'case-forecasts.csv',index=False);status.to_csv(out/'calibration-status.csv',index=False)
    scored,wischeck=score(fc,truth,cfg);scored.to_csv(out/'case-scores.csv',index=False)
    comp=comparisons(scored,cfg);comp.to_csv(out/'comparisons.csv',index=False)
    alerts,alarm_summary,alarm_paired=alert_analysis(native,truth,cfg)
    alerts.to_csv(out/'case-alerts.csv',index=False);alarm_summary.to_csv(out/'alerts.csv',index=False);alarm_paired.to_csv(out/'alerts-paired.csv',index=False)
    # No post-publication interpretation of a model before its checkpoint existed.
    d=scored[(scored.issue_date>=cfg['test_start'])&(scored.issue_date<=cfg['test_end'])&(~scored.known_target)]
    d=d[(d.model!='timesfm_2p5')|(d.issue_date>=cfg['timesfm_interpretation_start'])]
    groups=['truth_lag','input_mode','variant','model','source_age_weeks','target_offset_days']
    agg=d.groupby(groups).agg(n=('wis','size'),n_weeks=('issue_date','nunique'),wis=('wis','mean'),mae=('mae','mean'),covered80=('covered80','mean'),width80=('width80','mean'),growth_mae=('growth_mae','mean')).reset_index()
    agg.to_csv(out/'model-scores.csv',index=False)
    summary=dict(unique_inputs=len(inputs),native_case_predictions=len(native),calibrated_case_predictions=len(cal),scored_rows=len(scored),comparison_rows=len(comp),max_wis_identity_error=wischeck,main_test_issue_weeks=int(cases[cases.issue_date>=cfg['test_start']].issue_date.nunique()),known_target_cases=int(cases.known_target.sum()),primary_reference_missing_cases=int(truth[(truth.issue_date>=cfg['test_start'])&(truth.truth_lag=='56')].y_log.isna().sum()),network_required=False,ai_api_required=False,model_inference_required=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
