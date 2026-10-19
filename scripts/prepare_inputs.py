"""Build strictly dated source contexts and later publication reference values."""
from __future__ import annotations
import bisect,hashlib,json,os,pathlib,warnings
import numpy as np
import pandas as pd
from record import ROOT

warnings.filterwarnings('once',message="The 'generic' unit for NumPy timedelta is deprecated",category=DeprecationWarning)

def load_config():return json.loads((ROOT/'config/main.json').read_text())

def canonical(frame,pathogen):
    d=frame.copy()
    if 'typ' not in d:d['typ']='SARS-CoV-2'
    d['typ']=d['typ'].replace({'Influenza-A':'Influenza A','Influenza-B':'Influenza B','Influenza-Gesamt':'Influenza A+B'})
    d=d[d['typ']==pathogen].copy()
    if d.empty:return pd.DataFrame(columns=['value','n','population_share'],index=pd.DatetimeIndex([],name='date'),dtype=float)
    if pathogen=='SARS-CoV-2' and 'viruslast_normalisiert' in d:col='viruslast_normalisiert'
    else:
        col='viruslast'
        if 'normalisierung' in d:
            expected='ja' if pathogen=='SARS-CoV-2' else 'nein'
            if set(d['normalisierung'].dropna())!={expected}:raise ValueError('Normalization semantics not as preregistered')
    out=pd.DataFrame({'date':pd.to_datetime(d['datum']), 'value':pd.to_numeric(d[col],errors='coerce'),'n':pd.to_numeric(d['n'],errors='coerce'),'population_share':pd.to_numeric(d['anteil_bev'],errors='coerce')}).set_index('date').sort_index()
    if out.index.duplicated().any():raise ValueError('Duplicate pathogen/date')
    return out

class Archive:
    def __init__(self,config):
        raw=json.loads((ROOT/config['vintage_index']).read_text())
        self.records=sorted(raw['records'],key=lambda r:pd.Timestamp(r['commit_time']))
        self.times=[pd.Timestamp(r['commit_time']).tz_convert('UTC') for r in self.records]
        self.frames={r['commit']:pd.read_csv(ROOT/r['path'],sep='\t') for r in self.records}
        self.series={(r['commit'],p):canonical(self.frames[r['commit']],p) for r in self.records for p in config['pathogens']}
        self.freeze=self.times[-1]
    def asof(self,stamp):
        i=bisect.bisect_right(self.times,pd.Timestamp(stamp))-1
        return self.records[i] if i>=0 else None
    def series_at(self,record,pathogen):return self.series[(record['commit'],pathogen)]
    def usable_asof(self,stamp,pathogen):
        i=bisect.bisect_right(self.times,pd.Timestamp(stamp))-1
        skipped=[]
        while i>=0:
            r=self.records[i];s=self.series_at(r,pathogen)
            valid=s['value'].notna()&np.isfinite(s['value'])&(s['value']>0)
            if valid.any() and all(s.index[valid].dayofweek==2):return r,skipped
            skipped.append(dict(commit=r['commit'],reason='pathogen_absent' if not valid.any() else 'non_wednesday_grid'))
            i-=1
        return None,skipped

def context(series,config):
    vals=series['value']
    good=vals.notna()&np.isfinite(vals)&(vals>0)
    if int(good.sum())<config['min_observed']:return None,'insufficient_real_observations'
    good_values=vals[good]
    grid=pd.date_range(good_values.index.min(),good_values.index.max(),freq='7D')
    values=good_values.reindex(grid)
    observed=values.notna()
    values=values.ffill().iloc[-config['max_context']:]
    dates=[str(x.date()) for x in values.index]
    logs=np.log10(values.to_numpy(dtype=float)).tolist()
    signature=json.dumps([dates,logs],separators=(',',':'),allow_nan=False)
    uid=hashlib.sha256(signature.encode()).hexdigest()[:24]
    return dict(input_id=uid,dates=dates,log_values=logs,last_date=dates[-1],context_length=len(logs),imputed_context=int((~observed.reindex(values.index)).sum()),real_observations_context=int(observed.reindex(values.index).sum()),nonpositive_original=int((vals<=0).sum()),missing_original=int(vals.isna().sum())),None

def build_inputs(cfg,a,out):
    all_inputs={};cases=[];truths=[];quality=[];cached={}
    issues=pd.date_range(cfg['calibration_start'],cfg['test_end'],freq='W-FRI',tz='UTC')+pd.Timedelta(hours=cfg['issue_hour_utc'])
    for issue in issues:
        for pathogen in cfg['pathogens']:
            for offset in cfg['target_offsets_days']:
                target=(issue.tz_localize(None).normalize()+pd.Timedelta(days=offset))
                for lag in [*cfg['truth_lags_days'],'latest']:
                    if lag=='latest':ref,skipped=a.usable_asof(a.freeze,pathogen);deadline=a.freeze
                    else:
                        deadline=target.tz_localize('UTC')+pd.Timedelta(days=lag+1)-pd.Timedelta(seconds=1)
                        ref,skipped=a.usable_asof(deadline,pathogen) if deadline<=a.freeze else (None,[])
                    record=dict(issue_date=str(issue.date()),pathogen=pathogen,target_date=str(target.date()),target_offset_days=offset,truth_lag=str(lag),truth_deadline=str(deadline),truth_commit=ref['commit'] if ref else None,truth_commit_time=ref['commit_time'] if ref else None,skipped_releases=json.dumps(skipped),y_log=None,growth_log=None)
                    if ref:
                        s=a.series_at(ref,pathogen)['value'];v=s.get(target,np.nan);old=s.get(target-pd.Timedelta(days=14),np.nan)
                        if pd.notna(v) and np.isfinite(v) and v>0:record['y_log']=float(np.log10(v))
                        if record['y_log'] is not None and pd.notna(old) and np.isfinite(old) and old>0:record['growth_log']=float(np.log10(v)-np.log10(old))
                    truths.append(record)
            for age in cfg['source_age_weeks']:
                cutoff=issue-pd.Timedelta(weeks=age);ref,skipped=a.usable_asof(cutoff,pathogen)
                for mode in cfg['input_modes']:
                    base=dict(issue_date=str(issue.date()),issue_at_utc=issue.isoformat(),pathogen=pathogen,source_age_weeks=age,input_mode=mode,source_cutoff=cutoff.isoformat(),source_commit=ref['commit'] if ref else None,source_commit_time=ref['commit_time'] if ref else None,skipped_releases=json.dumps(skipped))
                    ctx=None;why=None;s=None
                    if not ref:why='no_source_release'
                    else:
                        key=(ref['commit'],pathogen,mode)
                        if key not in cached:
                            actual=a.series_at(ref,pathogen)
                            valid=actual['value'].notna()&np.isfinite(actual['value'])&(actual['value']>0)
                            if not valid.any():cached[key]=(None,'pathogen_not_available',None)
                            else:
                                end=actual.index[valid].max()
                                s=actual if mode=='actual' else a.series_at(a.records[-1],pathogen).loc[:end]
                                cc,reason=context(s,cfg);cached[key]=(cc,reason,s)
                                quality.append(dict(source_commit=ref['commit'],pathogen=pathogen,input_mode=mode,status=reason or 'ok',**({k:v for k,v in cc.items() if k not in ['dates','log_values']} if cc else {})))
                        ctx,why,s=cached[key]
                    if ctx:
                        uid=ctx['input_id']
                        if uid in all_inputs and all_inputs[uid]['log_values']!=ctx['log_values']:raise ValueError('Input hash collision')
                        all_inputs[uid]=ctx
                        base.update({k:ctx[k] for k in ['input_id','last_date','context_length','imputed_context']})
                        endrow=s.loc[pd.Timestamp(ctx['last_date'])]
                        base.update(latest_n=float(endrow['n']),latest_population_share=float(endrow['population_share']))
                    for offset in cfg['target_offsets_days']:
                        target=issue.tz_localize(None).normalize()+pd.Timedelta(days=offset)
                        r=dict(base,target_date=str(target.date()),target_offset_days=offset,status=why or 'ok',known_target=False)
                        if ctx:
                            step=(target-pd.Timestamp(ctx['last_date'])).days//7
                            if (target-pd.Timestamp(ctx['last_date'])).days%7:raise ValueError('Off-grid forecast target')
                            r.update(horizon=step,known_target=step<=0)
                            if step>cfg['max_horizon']:r['status']='horizon_outside_plan'
                        cases.append(r)
    pd.DataFrame(cases).to_csv(out/'cases.csv',index=False)
    pd.DataFrame(truths).to_csv(out/'truth.csv',index=False)
    pd.DataFrame(quality).to_csv(out/'input-quality.csv',index=False)
    (out/'inputs.json').write_text(json.dumps(all_inputs,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
    provenance=dict(source_index=cfg['vintage_index'],source_files={r['path']:r['sha256'] for r in a.records},frozen_commit=a.records[-1]['commit'],configuration_sha256=hashlib.sha256((ROOT/'config/main.json').read_bytes()).hexdigest())
    (out/'input-manifest.json').write_text(json.dumps(provenance,indent=2)+'\n')
    c=pd.DataFrame(cases);tr=pd.DataFrame(truths)
    summary=dict(issues=len(issues),unique_inputs=len(all_inputs),case_rows=len(cases),case_status=c['status'].value_counts().to_dict(),known_target_cases=int(c.known_target.sum()),horizon_max=float(c.horizon.max()),truth_missing_by_lag=tr.groupby('truth_lag').y_log.apply(lambda x:int(x.isna().sum())).to_dict(),freeze=str(a.freeze))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))

def main():
    cfg=load_config();build_inputs(cfg,Archive(cfg),pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']))

if __name__=='__main__':main()
