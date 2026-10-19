"""Freeze the preperiod cohort and derive all weekly raw-measurement vintages."""
import hashlib,json,os,pathlib
import pandas as pd
from record import ROOT,now
from prepare_inputs import load_config
from site_weekly import read_site_raw,weekly,cohort_from_preperiod

def main():
    cfg=load_config();sc=json.loads((ROOT/'config/multisite.json').read_text());out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR'])
    index_path=f"experiments/{sc['raw_archive_experiment']}/archive-index.json"
    records=json.loads((ROOT/index_path).read_text())['records']
    pre=next(r for r in records if r['commit'].startswith(sc['cohort_release_prefix']))
    cohort,preweekly,preaudit=cohort_from_preperiod(read_site_raw(ROOT/pre['path']),pre['commit_time'],cfg,sc)
    cohort.to_csv(out/'cohort-all-candidates.csv',index=False)
    selected=cohort[cohort.selected].copy();selected.to_csv(out/'cohort.csv',index=False)
    names=set(selected.standort);labelmap=dict(zip(selected.standort,selected.site_id));weekly_records=[];audits=[]
    destination=out/'weekly-vintages';destination.mkdir(exist_ok=True)
    for i,r in enumerate(records):
        w,info=weekly(read_site_raw(ROOT/r['path']),r['commit_time'],cfg['pathogens'],names)
        w['site_id']=w.standort.map(labelmap)
        w=w.merge(selected[['site_id','pathogen']],on=['site_id','pathogen'],how='inner',validate='many_to_one').drop(columns='standort').sort_values(['site_id','pathogen','date'])
        p=destination/(r['commit']+'.parquet');w.to_parquet(p,index=False,compression='zstd')
        item=dict(commit=r['commit'],commit_time=r['commit_time'],path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),raw_source_path=r['path'],raw_source_sha256=r['sha256'],weekly_rows=len(w))
        weekly_records.append(item);audits.append(dict(commit=r['commit'],**info))
        if r['commit'].startswith(sc['active_release_prefix']):
            end=pd.Timestamp(r['commit_time']).tz_convert('UTC').tz_localize(None).normalize();first=end-pd.Timedelta(weeks=sc['active_window_weeks']-1)
            active=w[w.date.between(first,end)].groupby(['site_id','pathogen']).size().rename('recent_weeks_2026').reset_index()
            selected=selected.merge(active,on=['site_id','pathogen'],how='left');selected['recent_weeks_2026']=selected.recent_weeks_2026.fillna(0).astype(int);selected['active2026']=selected.recent_weeks_2026>=sc['active_minimum_observed_weeks'];selected.to_csv(out/'cohort.csv',index=False)
        (out/'weekly-index.json').write_text(json.dumps(dict(raw_index=index_path,cohort_release=pre['commit'],records=weekly_records),indent=2)+'\n')
        print(json.dumps(dict(done=i+1,total=len(records),weekly_rows=len(w))),flush=True)
    pd.DataFrame(audits).to_csv(out/'weekly-audit.csv',index=False)
    summary=dict(cohort_release=pre['commit'],candidate_sites=int(cohort.standort.nunique()),historically_eligible_sites=int(cohort[cohort.historically_eligible].standort.nunique()),recently_eligible_sites=int(cohort[cohort.eligible].standort.nunique()),selected_sites=len(names),selected_series=len(selected),series_by_pathogen=selected.pathogen.value_counts().to_dict(),active2026_series=int(selected.active2026.sum()),weekly_vintages=len(weekly_records),derived_weekly_rows=sum(r['weekly_rows'] for r in weekly_records),preperiod_rules_use_no_test_values=True,measured_not_smoothed=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
