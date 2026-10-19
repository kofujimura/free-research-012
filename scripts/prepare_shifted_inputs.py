"""Rebuild dated public inputs under explicit positive publication-time shifts."""
import hashlib,json,os,pathlib,shutil
import numpy as np
import pandas as pd
from prepare_inputs import ROOT,Archive,context,load_config
from prepare_nz_inputs import NZArchive,eligible_archive

def main():
    out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);cfg=load_config();nzraw,_=eligible_archive(json.loads((ROOT/'experiments/E020-nz-vintage-audit/archive-index.json').read_text()))
    sources=[('germany_national','experiments/E007-prepare-inputs-fixed',Archive(cfg)),('nz','experiments/E027-nz-panel-inputs-eligible',NZArchive(nzraw))];scenarios=[];all_unseen={}
    for country,folder,archive in sources:
        base=ROOT/folder;original_inputs=json.loads((base/'inputs.json').read_text());original_cases=pd.read_csv(base/'cases.csv');original_truth=pd.read_csv(base/'truth.csv');config=json.loads((base/'panel-config.json').read_text()) if (base/'panel-config.json').exists() else dict(cfg,issue_frequency='W-FRI')
        original_cases=original_cases[original_cases.input_mode=='actual'].copy()
        if 'unit_id' not in original_cases:
            original_cases['unit_id']=original_cases.pathogen;original_cases['unit_level']='national';original_truth['unit_id']=original_truth.pathogen
        for shift in [24,48]:
            target=out/(country+'-shift'+str(shift));target.mkdir();rows=[];inputs={};cache={}
            for r in original_cases.to_dict('records'):
                cutoff=pd.Timestamp(r['source_cutoff'])-pd.Timedelta(hours=shift);record=archive.usable_asof(cutoff,r['pathogen'])[0] if country=='germany_national' else archive.asof(cutoff)
                r.update(availability_shift_hours=shift,source_cutoff=cutoff.isoformat(),source_commit=record['commit'] if record else None,source_commit_time=record['commit_time'] if record else None,input_id=None,last_date=None,context_length=None,imputed_context=None,horizon=None,known_target=False,status='no_source_release')
                if record:
                    unit=r['pathogen'] if country=='germany_national' else r['unit_id'];key=(record['commit'],unit)
                    if key not in cache:
                        series=archive.series_at(record,unit) if country=='germany_national' else archive.get_series(record,unit);ctx,reason=context(series,config);cache[key]=(ctx,reason,series)
                    ctx,reason,series=cache[key];r['status']=reason or 'ok'
                    if ctx:
                        uid=ctx['input_id'];inputs[uid]=ctx;h=(pd.Timestamp(r['target_date'])-pd.Timestamp(ctx['last_date'])).days//7
                        assert (pd.Timestamp(r['target_date'])-pd.Timestamp(ctx['last_date'])).days==7*h
                        r.update({k:ctx[k] for k in ['input_id','last_date','context_length','imputed_context','real_observations_context']});r.update(horizon=h,known_target=h<=0,source_observation_age_days=(pd.Timestamp(r['issue_date'])-pd.Timestamp(ctx['last_date'])).days)
                        if h>config['max_horizon']:r['status']='horizon_outside_plan'
                        latest=series.loc[pd.Timestamp(ctx['last_date'])]
                        for original,dest in [('floor_fraction','source_floor_fraction'),('population','latest_population'),('n_days','latest_n_samples'),('n','latest_n'),('population_share','latest_population_share')]:
                            if original in latest:r[dest]=float(latest[original]) if pd.notna(latest[original]) else None
                rows.append(r)
            used={r['input_id'] for r in rows if r['status']=='ok'};inputs={k:v for k,v in inputs.items() if k in used};unseen={k:v for k,v in inputs.items() if k not in original_inputs};all_unseen.update(unseen)
            pd.DataFrame(rows).to_csv(target/'cases.csv',index=False)
            truth=original_truth.copy();maturity=pd.to_datetime(truth.truth_deadline,utc=True);publication=pd.to_datetime(truth.truth_commit_time,utc=True)+pd.Timedelta(hours=shift)
            truth['training_available_at']=maturity.where(publication.isna()|(maturity>=publication),publication).astype(str)
            truth.to_csv(target/'truth.csv',index=False)
            for name,data in [('inputs.json',inputs),('unseen-inputs.json',unseen),('panel-config.json',dict(config,availability_shift_hours=shift)),('input-manifest.json',dict(original_panel=folder,original_input_sha256=hashlib.sha256((base/'inputs.json').read_bytes()).hexdigest(),publication_availability_assumption='Git timestamp + '+str(shift)+' hours',truth_definition_unchanged=True))]:
                (target/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
            scenario=dict(country=country,shift_hours=shift,panel_path=str(target.relative_to(ROOT)),model_inputs=len(inputs),unseen_inputs=len(unseen),cases=len(rows),ok_cases=sum(r['status']=='ok' for r in rows));scenarios.append(scenario);print(json.dumps(scenario),flush=True)
    (out/'scenarios.json').write_text(json.dumps(scenarios,indent=2)+'\n');(out/'unseen-inputs.json').write_text(json.dumps(all_unseen,separators=(',',':'),allow_nan=False)+'\n');(out/'summary.json').write_text(json.dumps(dict(scenarios=scenarios,unique_unseen_inputs=len(all_unseen)),indent=2)+'\n')

if __name__=='__main__':main()
