"""Revision-only prefixes from the current issue's actual publication, never final data."""
import hashlib,json,os,pathlib
import pandas as pd
from prepare_inputs import ROOT,Archive,context,load_config

cfg=load_config();archive=Archive(cfg);out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR'])
base=ROOT/'experiments/E007-prepare-inputs-fixed';cases=pd.read_csv(base/'cases.csv')
original=json.loads((base/'inputs.json').read_text());newinputs={};allinputs=dict(original);records=[]
actual=cases[(cases.input_mode=='actual')&(cases.status=='ok')]
fresh=actual[actual.source_age_weeks==0]
for age in [1,2]:
    stale=actual[actual.source_age_weeks==age]
    pairs=stale.merge(fresh,on=['issue_date','pathogen','target_date','target_offset_days'],suffixes=('_old','_fresh'),validate='one_to_one')
    for r in pairs.to_dict('records'):
        source={'commit':r['source_commit_fresh']}
        s=archive.series_at(source,r['pathogen']).loc[:r['last_date_old']]
        ctx,reason=context(s,cfg)
        item={k:r[k] for k in ['issue_date','pathogen','target_date','target_offset_days']}
        item.update(source_age_weeks=age,old_input_id=r['input_id_old'],fresh_input_id=r['input_id_fresh'],old_source_commit=r['source_commit_old'],fresh_source_commit=r['source_commit_fresh'],anchor_date=r['last_date_old'],status=reason or 'ok')
        if ctx:
            uid=ctx['input_id'];allinputs[uid]=ctx
            if uid not in original:newinputs[uid]=ctx
            item.update(revised_input_id=uid,revised_last_date=ctx['last_date'],revised_horizon=(pd.Timestamp(r['target_date'])-pd.Timestamp(ctx['last_date'])).days//7)
        records.append(item)
pd.DataFrame(records).to_csv(out/'cases.csv',index=False)
(out/'new-inputs.json').write_text(json.dumps(newinputs,separators=(',',':'),allow_nan=False)+'\n')
(out/'all-inputs.json').write_text(json.dumps(allinputs,separators=(',',':'),allow_nan=False)+'\n')
summary={'paired_cases':len(records),'new_unique_contexts':len(newinputs),'all_unique_contexts':len(allinputs),'status_counts':pd.DataFrame(records).status.value_counts().to_dict(),'source_provenance':'Same source manifests as E007; current issue fresh source commit clipped to old endpoint. No later publication used.'}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
