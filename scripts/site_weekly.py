"""Weekly measured site indicators and pre-test cohort, excluding smoothed rows."""
import hashlib,json,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT,load_config

NEEDED=['standort','datum','viruslast','viruslast_normalisiert','einwohner','laborwechsel','normalisierung','typ','unter_bg']

def read_site_raw(path):
    return pd.read_csv(path,sep='\t',usecols=lambda x:x in NEEDED,low_memory=False)

def weekly(frame,release_time,pathogens,site_names=None):
    d=frame.copy();total=len(d)
    d['typ']=d['typ'].replace({'Influenza-A':'Influenza A','Influenza-B':'Influenza B','Influenza-Gesamt':'Influenza A+B'})
    d=d[d.typ.isin(pathogens)]
    if site_names is not None:d=d[d.standort.isin(site_names)]
    date=pd.to_datetime(d.datum,errors='coerce');raw=pd.to_numeric(d.viruslast,errors='coerce')
    if 'viruslast_normalisiert' in d:value=raw.where(d.typ!='SARS-CoV-2',pd.to_numeric(d.viruslast_normalisiert,errors='coerce'))
    else:
        value=raw
        expected=np.where(d.typ=='SARS-CoV-2','ja','nein')
        wrong=value.notna()&d.normalisierung.ne(expected)
        if wrong.any():raise ValueError('Measured rows have unexpected normalization semantics')
    release_day=pd.Timestamp(release_time).tz_convert('UTC').tz_localize(None).normalize()
    future=date>release_day;nonpositive=(value<=0);missing=value.isna()|(~np.isfinite(value))
    valid=date.notna()&(~future)&(~nonpositive)&(~missing)
    info=dict(total_raw_rows=total,selected_rows=len(d),future_dated_rows=int(future.sum()),nonpositive_rows=int(nonpositive.sum()),missing_value_rows=int(missing.sum()),measured_rows=int(valid.sum()))
    d=d.loc[valid].copy();d['date']=date[valid];d['log_value']=np.log10(value[valid]);d['population']=pd.to_numeric(d.einwohner,errors='coerce')
    d['below']=d.unter_bg.map({'ja':1.,'nein':0.});d['lab']=d.laborwechsel.map({'ja':1.,'nein':0.})
    group=['standort','typ','date'];info['duplicate_measured_day_rows']=int(d.duplicated(group).sum())
    daily=d.groupby(group,sort=True).agg(log_value=('log_value','mean'),population=('population','median'),floor_fraction=('below','mean'),lab_change=('lab','max'),n_rows=('log_value','size')).reset_index()
    # Thursday..Wednesday, labelled by its ending Wednesday.
    daily['week']=daily.date+pd.to_timedelta((2-daily.date.dt.dayofweek)%7,unit='D')
    info['future_week_rows']=int((daily.week>release_day).sum());daily=daily[daily.week<=release_day]
    w=daily.groupby(['standort','typ','week'],sort=True).agg(log_value=('log_value','mean'),population=('population','median'),floor_fraction=('floor_fraction','mean'),lab_change=('lab_change','max'),n_days=('date','size'),n_rows=('n_rows','sum')).reset_index()
    w['value']=np.power(10.,w.log_value);w=w.rename(columns={'typ':'pathogen','week':'date'})
    info['weekly_observations']=len(w);return w,info

def cohort_from_preperiod(frame,release_time,cfg,sitecfg):
    allweekly,info=weekly(frame,release_time,cfg['pathogens'])
    populations=pd.to_numeric(frame.einwohner,errors='coerce').groupby(frame.standort).median()
    end=pd.Timestamp(release_time).tz_convert('UTC').tz_localize(None).normalize()
    first=end-pd.Timedelta(weeks=sitecfg['cohort_recent_window_weeks']-1)
    counts=allweekly.groupby(['standort','pathogen']).size().rename('observed_weeks').reset_index()
    recent=allweekly[allweekly.date.between(first,end)].groupby(['standort','pathogen']).size().rename('recent_weeks').reset_index()
    counts=counts.merge(recent,on=['standort','pathogen'],how='left');counts['recent_weeks']=counts.recent_weeks.fillna(0).astype(int)
    counts['population']=counts.standort.map(populations)
    counts['historically_eligible']=(counts.observed_weeks>=sitecfg['cohort_minimum_observed_weeks'])&(counts.population>=sitecfg['population_minimum'])
    counts['eligible']=counts.historically_eligible&(counts.recent_weeks>=sitecfg['cohort_recent_minimum_observed_weeks'])
    names=sorted(counts[counts.eligible].standort.unique(),key=lambda x:hashlib.sha256(x.encode('utf-8')).hexdigest())[:sitecfg['cohort_maximum_sites']]
    counts['site_id']=counts.standort.map(lambda x:hashlib.sha256(x.encode('utf-8')).hexdigest()[:16]);counts['selected']=counts.eligible&counts.standort.isin(names)
    if counts[['standort','site_id']].drop_duplicates().site_id.duplicated().any():raise ValueError('Site label collision')
    return counts,allweekly,info
