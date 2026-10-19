"""Score saved weekly pooled predictions against the same site forecast cases."""
import argparse,json,pathlib
import numpy as np
import pandas as pd
import analyze as a
import panel_analysis as panel
from prepare_inputs import ROOT

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--site-forecasts',required=True);ap.add_argument('--panel',default='experiments/E024-site-panel-inputs');ap.add_argument('--fit-dir',action='append',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);base=ROOT/args.panel;cfg=json.loads((base/'panel-config.json').read_text());truth=pd.read_csv(base/'truth.csv',dtype={'truth_lag':str});original=pd.read_csv(ROOT/args.site_forecasts);original=original[original.variant=='native'];predictions=[];models=[]
    for folder in args.fit_dir:
        p=ROOT/folder;run=json.loads((p/'run.json').read_text());assert run['status']=='completed';predictions.append(pd.read_csv(p/'case-forecasts.csv.gz'));models.extend(json.loads(line) for line in (p/'model-records.jsonl').read_text().splitlines())
    pooled=pd.concat(predictions,ignore_index=True);key=panel.KEY+['source_age_weeks'];assert not pooled.duplicated(key).any()
    cases=pd.read_csv(base/'cases.csv');intended=cases[(cases.status=='ok')&(cases.issue_date>=cfg['test_start'])];completed={r['issue_date'] for r in models if r['status']=='completed'}
    expected=intended[intended.issue_date.isin(completed)];assert set(map(tuple,pooled[key].to_numpy()))==set(map(tuple,expected[key].to_numpy()))
    fc=pd.concat([original,pooled],ignore_index=True);a.KEY=panel.KEY;scored,check=a.score(fc,truth,cfg);cfg['comparison_reference_models']=['pooled_hgb'];comp=panel.compare(scored,cfg);comp.to_csv(out/'comparisons.csv',index=False)
    scored[scored.model=='pooled_hgb'].to_csv(out/'pooled-case-scores.csv.gz',index=False,compression={'method':'gzip','mtime':0});pooled.to_csv(out/'pooled-case-forecasts.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    test=scored[(scored.issue_date>=cfg['test_start'])&(~scored.known_target)];test=test[(test.model!='timesfm_2p5')|(test.issue_date>=cfg['timesfm_interpretation_start'])]
    test.groupby(['truth_lag','model','source_age_weeks','target_offset_days']).agg(n=('wis','size'),n_weeks=('issue_date','nunique'),n_units=('unit_id','nunique'),wis=('wis','mean'),mae=('mae','mean'),covered80=('covered80','mean'),width80=('width80','mean')).reset_index().to_csv(out/'model-scores.csv',index=False)
    summary=dict(pooled_prediction_rows=len(pooled),intended_test_rows=len(intended),completed_issue_weeks=len(completed),model_fits=len(cfg['quantiles'])*len(completed),comparison_rows=len(comp),wis_identity_max_error=check,exploratory=True,additional_pathogen_and_calendar_features_used=True,clinical_or_growth_detection_effect_not_evaluated=True);(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
