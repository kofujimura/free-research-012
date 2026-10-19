"""Common dated input construction for explicitly defined panel archives."""
import hashlib,json,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import context

def scalar_json(x):
    if isinstance(x,np.generic):return x.item()
    raise TypeError('Unexpected JSON type '+type(x).__name__)

def build_panel(archive,units,cfg,out,frequency,provenance):
    out=pathlib.Path(out);all_inputs={};contexts={};cases=[];truths=[];quality=[]
    issues=pd.date_range(cfg['calibration_start'],cfg['test_end'],freq=frequency,tz='UTC')+pd.Timedelta(hours=cfg['issue_hour_utc'])
    for issue in issues:
        for unit in units:
            for offset in cfg['target_offsets_days']:
                target=issue.tz_localize(None).normalize()+pd.Timedelta(days=offset)
                for lag in cfg['truth_lags_days']:
                    if lag=='latest':deadline=archive.freeze;record=archive.asof(deadline)
                    else:
                        deadline=target.tz_localize('UTC')+pd.Timedelta(days=int(lag)+1)-pd.Timedelta(seconds=1)
                        record=archive.asof(deadline) if deadline<=archive.freeze else None
                    row=dict(issue_date=str(issue.date()),unit_id=unit['unit_id'],pathogen=unit['pathogen'],target_date=str(target.date()),target_offset_days=offset,truth_lag=str(lag),truth_deadline=str(deadline),truth_commit=record['commit'] if record else None,truth_commit_time=record['commit_time'] if record else None,y_log=None,growth_log=None,truth_floor_fraction=None,truth_population=None,truth_n_samples=None)
                    if record:
                        s=archive.get_series(record,unit['unit_id'])
                        if target in s.index:
                            r=s.loc[target];value=float(r['value'])
                            if np.isfinite(value) and value>0:row['y_log']=float(np.log10(value))
                            for original,dest in [('floor_fraction','truth_floor_fraction'),('population','truth_population'),('n_days','truth_n_samples')]:
                                if original in r and pd.notna(r[original]):row[dest]=float(r[original])
                            previous=s['value'].get(target-pd.Timedelta(days=14),np.nan)
                            if row['y_log'] is not None and pd.notna(previous) and previous>0:row['growth_log']=row['y_log']-float(np.log10(previous))
                    truths.append(row)
            for age in cfg['source_age_weeks']:
                cutoff=issue-pd.Timedelta(weeks=age);record=archive.asof(cutoff)
                base=dict(unit,issue_date=str(issue.date()),issue_at_utc=issue.isoformat(),source_age_weeks=age,input_mode='actual',source_cutoff=cutoff.isoformat(),source_commit=record['commit'] if record else None,source_commit_time=record['commit_time'] if record else None)
                ctx=None;reason='no_source_release' if record is None else None;s=None
                if record:
                    key=(record['commit'],unit['unit_id'])
                    if key not in contexts:
                        s=archive.get_series(record,unit['unit_id']);cc,why=context(s,cfg)
                        if cc and cc['real_observations_context']<cfg['min_observed']:
                            cc=None;why='insufficient_real_observations_in_context'
                        contexts[key]=(cc,why)
                        quality.append(dict(unit_id=unit['unit_id'],source_commit=record['commit'],status=why or 'ok',**({k:v for k,v in cc.items() if k not in ['dates','log_values']} if cc else {})))
                    ctx,reason=contexts[key]
                    if s is None:s=archive.get_series(record,unit['unit_id'])
                if ctx:
                    uid=ctx['input_id'];all_inputs[uid]=ctx
                    base.update({k:ctx[k] for k in ['input_id','last_date','context_length','imputed_context','real_observations_context']})
                    latest=s.loc[pd.Timestamp(ctx['last_date'])]
                    base.update(source_observation_age_days=(issue.tz_localize(None).normalize()-pd.Timestamp(ctx['last_date'])).days)
                    for original,dest in [('floor_fraction','source_floor_fraction'),('population','latest_population'),('n_days','latest_n_samples'),('lab_change','source_lab_change')]:
                        base[dest]=float(latest[original]) if original in latest and pd.notna(latest[original]) else None
                for offset in cfg['target_offsets_days']:
                    target=issue.tz_localize(None).normalize()+pd.Timedelta(days=offset)
                    r=dict(base,target_date=str(target.date()),target_offset_days=offset,status=reason or 'ok',known_target=False)
                    if ctx:
                        difference=(target-pd.Timestamp(ctx['last_date'])).days
                        if difference%7:raise ValueError('Target is not on the source weekly grid')
                        horizon=difference//7;r.update(horizon=horizon,known_target=horizon<=0)
                        if horizon>cfg['max_horizon']:r['status']='horizon_outside_plan'
                    cases.append(r)
        print(json.dumps(dict(issue=str(issue.date()),cases=len(cases),unique_inputs=len(all_inputs))),flush=True)
    needed={r['input_id'] for r in cases if r['status']=='ok'};inputs={uid:all_inputs[uid] for uid in sorted(needed)}
    pd.DataFrame(cases).to_csv(out/'cases.csv',index=False);pd.DataFrame(truths).to_csv(out/'truth.csv',index=False);pd.DataFrame(quality).to_csv(out/'context-quality.csv',index=False)
    (out/'inputs.json').write_text(json.dumps(inputs,separators=(',',':'),allow_nan=False,default=scalar_json)+'\n')
    (out/'units.json').write_text(json.dumps(units,indent=2,allow_nan=False,default=scalar_json)+'\n')
    (out/'panel-config.json').write_text(json.dumps(dict(cfg,issue_frequency=frequency),indent=2)+'\n')
    chunks=[];folder=out/'input-chunks';folder.mkdir(exist_ok=True)
    items=sorted(inputs.items());size=cfg['forecast_chunk_size']
    for first in range(0,len(items),size):
        p=folder/f'chunk-{first//size:03d}.json';p.write_text(json.dumps(dict(items[first:first+size]),separators=(',',':'),allow_nan=False)+'\n')
        chunks.append(dict(path=str(p.relative_to(out)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),inputs=min(size,len(items)-first),index=first//size))
    (out/'chunks.json').write_text(json.dumps(chunks,indent=2)+'\n');(out/'input-manifest.json').write_text(json.dumps(provenance,indent=2,default=scalar_json)+'\n')
    c=pd.DataFrame(cases);t=pd.DataFrame(truths)
    summary=dict(units=len(units),issues=len(issues),test_issue_weeks=int(c[c.issue_date>=cfg['test_start']].issue_date.nunique()),cases=len(cases),status_counts=c.status.value_counts().to_dict(),unique_model_inputs=len(inputs),model_chunks=len(chunks),known_target_cases=int(c.known_target.sum()),maximum_horizon=float(c.horizon.max()),reference_missing_by_lag=t.groupby('truth_lag').y_log.apply(lambda x:int(x.isna().sum())).to_dict(),freeze=str(archive.freeze),network_required_for_saved_output_analysis=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
