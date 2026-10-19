"""Actual-publication non-normalized SARS-CoV-2 sensitivity, no semantic splicing."""
import hashlib,json,os,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT,Archive,load_config,build_inputs

def raw_sars(frame):
    d=frame.copy()
    if 'typ' not in d:d['typ']='SARS-CoV-2'
    d=d[d.typ=='SARS-CoV-2']
    if 'viruslast_normalisiert' not in frame:
        d=d[d.normalisierung=='nein'] if 'normalisierung' in d else d.iloc[:0]
    if d.empty:return pd.DataFrame(columns=['value','n','population_share'],index=pd.DatetimeIndex([],name='date'),dtype=float)
    out=pd.DataFrame(dict(date=pd.to_datetime(d.datum),value=pd.to_numeric(d.viruslast,errors='coerce'),n=pd.to_numeric(d.n,errors='coerce'),population_share=pd.to_numeric(d.anteil_bev,errors='coerce'))).set_index('date').sort_index()
    if out.index.duplicated().any():raise ValueError('Duplicate raw national SARS date')
    return out

def main():
    out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);cfg=dict(load_config(),pathogens=['SARS-CoV-2'],input_modes=['actual'],issue_frequency='W-FRI',measurement_variant='non_normalized_SARS_CoV_2')
    archive=Archive(cfg)
    for record in archive.records:archive.series[(record['commit'],'SARS-CoV-2')]=raw_sars(archive.frames[record['commit']])
    eligibility=[dict(commit=r['commit'],commit_time=r['commit_time'],positive_measured_weeks=int((archive.series_at(r,'SARS-CoV-2').value>0).sum())) for r in archive.records]
    (out/'raw-availability.json').write_text(json.dumps(eligibility,indent=2)+'\n');build_inputs(cfg,archive,out)
    cases=pd.read_csv(out/'cases.csv');truth=pd.read_csv(out/'truth.csv');cases['unit_id']=cases.pathogen;cases['unit_level']='national';truth['unit_id']=truth.pathogen;cases.to_csv(out/'cases.csv',index=False);truth.to_csv(out/'truth.csv',index=False)
    (out/'panel-config.json').write_text(json.dumps(cfg,indent=2)+'\n');(out/'units.json').write_text(json.dumps([dict(unit_id='SARS-CoV-2',pathogen='SARS-CoV-2',unit_level='national')],indent=2)+'\n')
    manifest=json.loads((out/'input-manifest.json').read_text());manifest.update(measurement_variant=cfg['measurement_variant'],variant_configuration_sha256=hashlib.sha256((out/'panel-config.json').read_bytes()).hexdigest(),ambiguous_older_normalized_values_not_treated_as_raw=True);(out/'input-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':main()
