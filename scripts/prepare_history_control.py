"""Prepare fixed-cohort 104/256-week histories and finite native-inference jobs."""
import hashlib,itertools,json,os,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT,Archive,build_inputs,load_config
from prepare_site_inputs import SiteArchive
from prepare_nz_inputs import NZArchive,eligible_archive
from panel_inputs import build_panel

PANELS={'national':'experiments/E007-prepare-inputs-fixed','site':'experiments/E024-site-panel-inputs','nz':'experiments/E027-nz-panel-inputs-eligible'}
KEY=['issue_date','unit_id','pathogen','target_date','target_offset_days']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,value):p.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def directory(prefix):
    items=list((ROOT/'experiments').glob(prefix+'-*'));assert len(items)==1,(prefix,items);return str(items[0].relative_to(ROOT))

def short_panel(source,out,name):
    source=ROOT/source;out.mkdir();cfg=json.loads((source/'panel-config.json').read_text()) if (source/'panel-config.json').exists() else dict(load_config(),issue_frequency='W-FRI');cfg.update(max_context=104,input_modes=['actual'],truth_lags_days=[56])
    cases=pd.read_csv(source/'cases.csv');cases=cases[cases.input_mode=='actual'].copy();truth=pd.read_csv(source/'truth.csv',dtype={'truth_lag':str});truth=truth[truth.truth_lag=='56'].copy()
    if 'unit_id' not in cases:cases['unit_id']=cases.pathogen;cases['unit_level']='national';truth['unit_id']=truth.pathogen
    if (source/'units.json').exists():units=json.loads((source/'units.json').read_text())
    else:units=[dict(unit_id=p,pathogen=p,unit_level='national') for p in cfg['pathogens']]
    needed=set(cases.loc[cases.status=='ok','input_id']);inputs=json.loads((source/'inputs.json').read_text());inputs={u:inputs[u] for u in sorted(needed)};cases.to_csv(out/'cases.csv',index=False);truth.to_csv(out/'truth.csv',index=False);dump(out/'panel-config.json',cfg);dump(out/'units.json',units);(out/'inputs.json').write_text(json.dumps(inputs,separators=(',',':'),allow_nan=False)+'\n')
    dump(out/'source-provenance.json',dict(source_panel=str(source.relative_to(ROOT)),source_files={str(p.relative_to(ROOT)):sha(p) for p in [source/'cases.csv',source/'truth.csv',source/'inputs.json']},changes='Actual inputs only;56-day reference only; numerical histories unchanged.'))
    return cfg,units

def available_history(archive,cases,name):
    records={r['commit']:r for r in archive.records};counts={}
    for r in cases[cases.status=='ok'].drop_duplicates(['source_commit','unit_id']).sort_values(['source_commit','unit_id']).to_dict('records'):
        record=records[r['source_commit']];s=archive.series_at(record,r['pathogen']) if name=='national' else archive.get_series(record,r['unit_id']);valid=s.value.notna()&np.isfinite(s.value)&s.value.gt(0);dates=s.index[valid];counts[(r['source_commit'],r['unit_id'])]=(dates.max()-dates.min()).days//7+1
    return np.asarray([counts.get((r.source_commit,r.unit_id),np.nan) for r in cases.itertuples()])

def main():
    out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);panels=[];inputs={};checks=[]
    for name,source in PANELS.items():
        short=out/(name+'-104');long=out/(name+'-256');cfg,units=short_panel(source,short,name);long.mkdir();cfg=dict(cfg,max_context=256,forecast_chunk_size=1000)
        if name=='national':
            archive=Archive(cfg);build_inputs(cfg,archive,long);c=pd.read_csv(long/'cases.csv');t=pd.read_csv(long/'truth.csv',dtype={'truth_lag':str});t=t[t.truth_lag=='56'].copy();c['unit_id']=c.pathogen;c['unit_level']='national';t['unit_id']=t.pathogen;c.to_csv(long/'cases.csv',index=False);t.to_csv(long/'truth.csv',index=False);dump(long/'panel-config.json',cfg);dump(long/'units.json',units)
            original_summary=json.loads((long/'summary.json').read_text());dump(long/'build-summary-before-reference-filter.json',original_summary);original_summary['truth_missing_by_lag']={'56':int(t.y_log.isna().sum())};original_summary['reference_filter']='Core national builder adds latest unconditionally; filtered to prespecified56-day reference before control use.';dump(long/'summary.json',original_summary)
        elif name=='site':
            index=json.loads((ROOT/'experiments/E023-site-weekly-cohort/weekly-index.json').read_text());archive=SiteArchive(index['records']);build_panel(archive,units,cfg,long,'W-FRI',dict(original_panel=source,weekly_index='experiments/E023-site-weekly-cohort/weekly-index.json',maximum_context=256,cohort_unchanged=True))
        else:
            raw,audit=eligible_archive(json.loads((ROOT/cfg['vintage_index']).read_text()));dump(long/'release-eligibility.json',audit);archive=NZArchive(raw);build_panel(archive,units,cfg,long,'W-MON',dict(original_panel=source,source_index=cfg['vintage_index'],maximum_context=256,cohort_unchanged=True))
        old=pd.read_csv(short/'cases.csv');new=pd.read_csv(long/'cases.csv');new['available_calendar_weeks']=available_history(archive,new,name);new.to_csv(long/'cases.csv',index=False);keys=KEY+['source_age_weeks'];p=old.merge(new,on=keys,suffixes=('_104','_256'),validate='one_to_one');assert len(p)==len(old)==len(new);both=p[(p.status_104=='ok')&(p.status_256=='ok')]
        manifest=json.loads((long/'input-manifest.json').read_text());manifest.update(applied_configuration_path=str((long/'panel-config.json').relative_to(ROOT)),applied_configuration_sha256=sha(long/'panel-config.json'),reference_lags_used=[56]);dump(long/'input-manifest.json',manifest)
        for column in ['source_commit','last_date','horizon']:assert np.array_equal(both[column+'_104'].to_numpy(),both[column+'_256'].to_numpy()),(name,column)
        a=pd.read_csv(short/'truth.csv').sort_values(KEY);b=pd.read_csv(long/'truth.csv').sort_values(KEY);assert np.array_equal(a[KEY].to_numpy(),b[KEY].to_numpy());np.testing.assert_allclose(a.y_log.to_numpy(),b.y_log.to_numpy(),rtol=0,atol=1e-12,equal_nan=True)
        record=dict(dataset=name,short_panel=str(short.relative_to(ROOT)),long_panel=str(long.relative_to(ROOT)),intended_cases=len(p),both_inputs_available=len(both),maximum_available_calendar_weeks=int(new.available_calendar_weeks.max()),cases_with_available_history_over_256=int(new.available_calendar_weeks.gt(256).sum()),source_and_last_dates_and_horizons_unchanged_on_common_cases=True,numeric_histories_unchanged=int((both.input_id_104==both.input_id_256).sum()),only_long_available=int(((p.status_104!='ok')&(p.status_256=='ok')).sum()),only_short_available=int(((p.status_104=='ok')&(p.status_256!='ok')).sum()));checks.append(record)
        for length,folder in [(104,short),(256,long)]:
            contexts=json.loads((folder/'inputs.json').read_text());maximum=max(len(x['log_values']) for x in contexts.values());assert maximum<=length;panels.append(dict(dataset=name,maximum_context=length,panel=str(folder.relative_to(ROOT)),unique_inputs=len(contexts),maximum_actual_context_length=maximum))
            for uid,ctx in contexts.items():
                if uid in inputs:assert inputs[uid]['dates']==ctx['dates'] and inputs[uid]['log_values']==ctx['log_values']
                else:inputs[uid]=ctx
        print(json.dumps(record),flush=True)
    dump(out/'panels.json',panels);dump(out/'input-comparison.json',checks);(out/'union-inputs.json').write_text(json.dumps(dict(sorted(inputs.items())),separators=(',',':'),allow_nan=False)+'\n')
    prefixes={'statistical':['E008','E028','E032','E036','E058','E065','E039'],'extra':['E013','E029','E033','E042','E051','E059','E043']};models={'statistical':{'naive','damped_trend','autoarima','autoets','ensemble'},'extra':{'autotheta','seasonal_naive','harmonic_arima'}};cached={};coverage=[];original_dirs=[]
    for engine,ids in prefixes.items():
        found={};duplicates=0;dirs=[directory(i) for i in ids];original_dirs.extend(dirs)
        for folder in dirs:
            p=ROOT/folder;assert json.loads((p/'run.json').read_text())['status']=='completed'
            for line in (p/'forecasts.jsonl').read_text().splitlines():
                f=json.loads(line);key=(f['input_id'],f['model'])
                if key[0] not in inputs:continue
                assert f['model'] in models[engine]
                if key in found:assert found[key]==f['quantiles'];duplicates+=1
                else:found[key]=f['quantiles']
        available={u for u in inputs if all((u,m) in found for m in models[engine])};assert all((u,m) not in found for u in set(inputs)-available for m in models[engine]);cached[engine]=available;coverage.append(dict(engine=engine,original_forecast_dirs=dirs,source_files={d+'/forecasts.jsonl':sha(ROOT/d/'forecasts.jsonl') for d in dirs},cached_inputs=len(available),new_inputs=len(inputs)-len(available),exact_duplicate_records=duplicates))
    dump(out/'cache-coverage.json',coverage);dump(out/'original-classical-dirs.json',original_dirs)
    chunkdir=out/'inference-inputs';chunkdir.mkdir();groups={}
    for engine in ['timesfm','chronos','statistical','extra']:
        items=sorted((u,c) for u,c in inputs.items() if engine not in cached or u not in cached[engine]);groups[engine]=[]
        for start in range(0,len(items),1000):
            p=chunkdir/(engine+'-'+str(start//1000).zfill(3)+'.json');p.write_text(json.dumps(dict(items[start:start+1000]),separators=(',',':'),allow_nan=False)+'\n');groups[engine].append(dict(engine=engine,path=str(p.relative_to(ROOT)),inputs=min(1000,len(items)-start),sha256=sha(p)))
    queue=[];counter=int(out.name.split('-')[0][1:])+1
    for batch in itertools.zip_longest(*[groups[e] for e in ['timesfm','chronos','statistical','extra']]):
        for chunk in batch:
            if chunk is None:continue
            engine=chunk['engine'];eid=f'E{counter:03d}-history-{engine}-{pathlib.Path(chunk["path"]).stem.rsplit("-",1)[1]}';counter+=1;directory_name='experiments/'+eid
            command=['.venv/bin/python','scripts/run_experiment.py','--id',eid,'--plan','protocol/history-length-control-v1.md','--timeout','1800','--input',chunk['path']]
            if engine in ['chronos','timesfm']:command+=['--input','data/models/'+('chronos-bolt-base' if engine=='chronos' else 'timesfm-2.5-200m-pytorch')+'/model.safetensors']
            command+=['--','.venv/bin/python','scripts/extra_baselines.py' if engine=='extra' else 'scripts/generate_forecasts.py','--inputs',chunk['path']]
            if engine!='extra':command+=['--engine',engine]
            if engine=='timesfm':command+=['--timesfm-max-context','256']
            queue.append(dict(experiment_id=eid,forecast_dir=directory_name,engine=engine,inputs=chunk['inputs'],command=command))
    dump(out/'inference-jobs.json',queue);dump(out/'summary.json',dict(panels=panels,union_inputs=len(inputs),jobs=len(queue),cached_classical_forecast_coverage=coverage,all_contexts_at_most_256=True,per_release_provenance_in_cases_not_deduplicated_context_metadata=True,new_data_downloads=0,exploratory=True));print(json.dumps(dict(panels=len(panels),union_inputs=len(inputs),jobs=len(queue))),flush=True)

if __name__=='__main__':main()
