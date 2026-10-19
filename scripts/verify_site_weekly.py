"""Independent stdlib raw aggregation check; no forecasting or fitted labels."""
import argparse,csv,datetime as dt,gzip,json,math,os,pathlib,statistics
from collections import defaultdict
import pandas as pd
from prepare_inputs import ROOT,load_config

def number(s):
    try:
        v=float(s)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):return None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--all-series',action='store_true');ap.add_argument('--all-versions',action='store_true');args=ap.parse_args()
    out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);cfg=load_config();root=ROOT/'experiments/E023-site-weekly-cohort'
    cohort=pd.read_csv(root/'cohort.csv',dtype={'site_id':str})
    chosen=cohort.sort_values('site_id') if args.all_series else cohort.sort_values('site_id').groupby('pathogen',sort=True).head(2)
    names={(r.standort,r.pathogen):r.site_id for r in chosen.itertuples()}
    records=json.loads((root/'weekly-index.json').read_text())['records'];prefixes=['6f630bf','0ebb01d','97087a2','6586326']
    differences=[];floor_differences=[];rows=0;versions=[]
    for rec in records:
        if not args.all_versions and not any(rec['commit'].startswith(p) for p in prefixes):continue
        publication=dt.datetime.fromisoformat(rec['commit_time']).astimezone(dt.timezone.utc).date()
        daily=defaultdict(list);floors=defaultdict(list)
        with gzip.open(ROOT/rec['raw_source_path'],'rt',encoding='utf-8',newline='') as f:
            for r in csv.DictReader(f,delimiter='\t'):
                group=(r['standort'],r['typ'])
                if group not in names:continue
                value=number(r.get('viruslast_normalisiert') if r['typ']=='SARS-CoV-2' and 'viruslast_normalisiert' in r else r['viruslast'])
                if value is None or value<=0:continue
                day=dt.date.fromisoformat(r['datum'])
                if day>publication:continue
                ending=day+dt.timedelta(days=(2-day.weekday())%7)
                if ending>publication:continue
                key=(*group,day,ending);daily[key].append(math.log10(value))
                if r.get('unter_bg') in ['ja','nein']:floors[key].append(float(r['unter_bg']=='ja'))
        weekly=defaultdict(list);weekly_floor=defaultdict(list)
        for key,values in daily.items():
            site,pathogen,day,ending=key;wk=(names[(site,pathogen)],pathogen,ending)
            weekly[wk].append(math.fsum(values)/len(values))
            if floors[key]:weekly_floor[wk].append(math.fsum(floors[key])/len(floors[key]))
        actual=pd.read_parquet(ROOT/rec['path']);lookup={(r.site_id,r.pathogen,r.date.date()):r for r in actual.itertuples()}
        for key,values in weekly.items():
            r=lookup[key];expected=math.fsum(values)/len(values);differences.append(abs(expected-r.log_value));assert r.n_days==len(values)
            assert key[2].weekday()==2 and key[2]<=publication
            if weekly_floor[key]:floor_differences.append(abs(math.fsum(weekly_floor[key])/len(weekly_floor[key])-r.floor_fraction))
            rows+=1
        versions.append(rec['commit'])
    assert len(versions)==(len(records) if args.all_versions else len(prefixes))
    summary=dict(source_versions=versions,series_checked=len(chosen),weekly_values_checked=rows,max_absolute_log_difference=max(differences),max_absolute_floor_flag_difference=max(floor_differences),stdlib_date_labels_and_measurement_day_counts_match=True,independent_implementation_by_same_researcher=True,independent_external_replication=False,all_cohort_series=args.all_series,all_saved_versions=args.all_versions)
    assert summary['max_absolute_log_difference']<1e-12 and summary['max_absolute_floor_flag_difference']<1e-12
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
