"""Official NZ national and preperiod regional panel with actual public vintages."""
import bisect,functools,gzip,hashlib,io,json,os,pathlib,re
import numpy as np
import pandas as pd
from prepare_inputs import ROOT,load_config
from panel_inputs import build_panel

def eligible_archive(raw):
    """Reject whole malformed paired releases; never guess merge-conflict content."""
    rows=[];records=[]
    for record in raw['records']:
        errors=[]
        for source in record['files']:
            d=pd.read_csv(ROOT/source['path'],dtype=str)
            if 'week_end_date' not in d or 'copies_per_day_per_person' not in d:
                errors.append(source['source_path']+': missing required column');continue
            invalid=~d.week_end_date.fillna('').str.fullmatch(r'\d{4}-\d{2}-\d{2}')
            if invalid.any():
                errors.append(source['source_path']+': non-ISO date rows '+str(int(invalid.sum())));continue
            dates=pd.to_datetime(d.week_end_date,format='%Y-%m-%d',errors='coerce')
            if dates.isna().any() or (dates.dt.dayofweek!=6).any():errors.append(source['source_path']+': invalid Sunday grid')
            group=['week_end_date'] if source['source_path'].endswith('ww_national.csv') else ['Region','week_end_date']
            if d.duplicated(group).any():errors.append(source['source_path']+': duplicate unit/week')
            value=pd.to_numeric(d.copies_per_day_per_person,errors='coerce')
            publication=pd.Timestamp(record['commit_time']).tz_convert('UTC').tz_localize(None).normalize()
            if ((dates>publication)&value.notna()&(value>0)).any():errors.append(source['source_path']+': future-labelled positive value')
        rows.append(dict(commit=record['commit'],commit_time=record['commit_time'],eligible=not errors,reasons=errors))
        if not errors:records.append(record)
    return dict(raw,records=records),rows

class NZArchive:
    def __init__(self,raw):
        self.records=sorted(raw['records'],key=lambda r:pd.Timestamp(r['commit_time']));self.times=[pd.Timestamp(r['commit_time']).tz_convert('UTC') for r in self.records];self.freeze=self.times[-1];self.raw=raw
    def asof(self,stamp):
        i=bisect.bisect_right(self.times,pd.Timestamp(stamp))-1
        return self.records[i] if i>=0 else None
    @functools.lru_cache(maxsize=10)
    def release(self,commit):
        record=next(r for r in self.records if r['commit']==commit);result={}
        for f in record['files']:
            d=pd.read_csv(ROOT/f['path']);dates=pd.to_datetime(d.week_end_date,errors='raise')
            if any(dates.dt.dayofweek!=6):raise ValueError('NZ weekly label is not Sunday')
            d['date']=dates;d['value']=pd.to_numeric(d['copies_per_day_per_person'],errors='coerce')
            publication_day=pd.Timestamp(record['commit_time']).tz_convert('UTC').tz_localize(None).normalize()
            if ((d.date>publication_day)&d.value.notna()&(d.value>0)).any():raise ValueError('NZ source contains a future-labelled positive observation; audit before use')
            if f['source_path'].endswith('ww_national.csv'):
                d['population']=pd.to_numeric(d.national_pop,errors='coerce');groups=[('national',d)]
            else:
                d['population']=pd.to_numeric(d.population_covered,errors='coerce') if 'population_covered' in d else np.nan;groups=[('region:'+hashlib.sha256(str(region).encode('utf-8')).hexdigest()[:16],sub) for region,sub in d.groupby('Region',sort=True)]
            for unit,sub in groups:
                frame=sub[['date','value','population']].set_index('date').sort_index()
                if frame.index.duplicated().any():raise ValueError('Duplicate NZ unit/week')
                result[unit]=frame
        return result
    def get_series(self,record,unit):
        return self.release(record['commit']).get(unit,pd.DataFrame(columns=['value','population'],index=pd.DatetimeIndex([],name='date'),dtype=float))

def main():
    out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);cfg=load_config();specific=json.loads((ROOT/'config/nz.json').read_text());cfg.update(specific)
    path=ROOT/cfg['vintage_index'];original=json.loads(path.read_text());raw,audit=eligible_archive(original);archive=NZArchive(raw)
    (out/'release-eligibility.json').write_text(json.dumps(audit,indent=2)+'\n')
    record=archive.asof(cfg['cohort_cutoff']);groups=archive.release(record['commit']);units=[dict(unit_id='national',pathogen='SARS-CoV-2',unit_level='national')];candidates=[]
    end=pd.Timestamp(cfg['cohort_cutoff']).tz_localize(None).normalize();first=end-pd.Timedelta(weeks=cfg['region_recent_window_weeks'])
    for unit,series in sorted(groups.items()):
        if unit=='national':continue
        valid=series.value.notna()&np.isfinite(series.value)&(series.value>0);n=int(valid.sum());recent=int((valid&series.index.to_series().between(first,end)).sum())
        selected=n>=cfg['region_minimum_observed_weeks'] and recent>=cfg['region_recent_minimum_observed_weeks']
        candidates.append(dict(unit_id=unit,observed_weeks=n,recent_weeks=recent,selected=selected))
        if selected:units.append(dict(unit_id=unit,pathogen='SARS-CoV-2',unit_level='regional'))
    pd.DataFrame(candidates).to_csv(out/'regional-cohort.csv',index=False)
    provenance=dict(source_index=cfg['vintage_index'],source_index_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_files={f['path']:f['sha256'] for r in raw['records'] for f in r['files']},frozen_commit=raw['frozen_commit'],cohort_release=record['commit'],license='CC BY4.0',attribution='COVID-19 Data Repository by the New Zealand Institute for Public Health and Forensic Science Ltd (formerly Institute of Environmental Science and Research)',source_url='https://github.com/ESR-NZ/covid_in_wastewater')
    build_panel(archive,units,cfg,out,'W-MON',provenance)

if __name__=='__main__':main()
