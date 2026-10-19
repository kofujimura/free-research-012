"""Assemble uncorrected history-length forecasts; retain compact case evidence."""
import argparse,gc,gzip,json,pathlib
import numpy as np
import pandas as pd
import analyze as a
import panel_analysis as panel
from prepare_inputs import ROOT

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--preparation',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();prep=ROOT/args.preparation;out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);definitions=json.loads((prep/'panels.json').read_text());jobs=json.loads((prep/'inference-jobs.json').read_text());folders=json.loads((prep/'original-classical-dirs.json').read_text())+[j['forecast_dir'] for j in jobs]
    for j in jobs:assert json.loads((ROOT/j['forecast_dir']/'run.json').read_text())['status']=='completed',j['experiment_id']
    a.KEY=panel.KEY;a.MODELS=['naive','damped_trend','autoarima','autoets','ensemble','chronos_bolt_base','timesfm_2p5',*panel.EXTRA];a.FORECAST_DIRS=folders;summaries=[]
    for definition in definitions:
        name=definition['dataset']+'-'+str(definition['maximum_context']);child=out/name;child.mkdir();base=ROOT/definition['panel'];cfg=json.loads((base/'panel-config.json').read_text());a.INPUT_DIR=definition['panel'];cases,truth,native,inputs=a.assemble(cfg,allow_unused_inputs=True,allow_identical_duplicates=True);audit=dict(a.LAST_ASSEMBLY_AUDIT)
        if 'truth_floor_fraction' not in truth:truth['truth_floor_fraction']=np.nan
        native,choices=panel.add_competitors(native,truth,cfg);scores,check=a.score(native,truth,cfg)
        if 'real_observations_context' not in scores:scores['real_observations_context']=scores.context_length-scores.imputed_context
        wanted=panel.KEY+['unit_level','model','variant','input_mode','source_age_weeks','input_id','last_date','context_length','imputed_context','real_observations_context','known_target','horizon','truth_lag','wis','mae','covered80','width80',*a.QCOLS]
        for optional in ['active2026','truth_floor_fraction']:
            if optional in scores:wanted.append(optional)
        scores[wanted].to_csv(child/'case-scores.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        with gzip.GzipFile(filename=str(child/'selector.jsonl.gz'),mode='wb',mtime=0) as f:f.write(''.join(json.dumps(x,default=lambda v:v.item() if isinstance(v,np.generic) else str(v))+'\n' for x in choices).encode())
        test=scores[(scores.issue_date>=cfg['test_start'])&(~scores.known_target)];test=test[(test.model!='timesfm_2p5')|(test.issue_date>=cfg['timesfm_interpretation_start'])]
        test.groupby(['unit_level','model','source_age_weeks','target_offset_days']).agg(n=('wis','size'),n_issue_weeks=('issue_date','nunique'),n_units=('unit_id','nunique'),wis=('wis','mean'),mae=('mae','mean'),covered80=('covered80','mean')).reset_index().to_csv(child/'model-scores.csv',index=False)
        summary=dict(definition,analysis_directory=name,native_predictions=len(native),scored_rows=len(scores),case_score_columns=wanted,wis_identity_max_error=check,assembly_audit=audit,calibration_performed=False,exploratory=True,model_inference_required=False);(child/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');summaries.append(summary);print(json.dumps(summary),flush=True);del cases,truth,native,scores,inputs;gc.collect()
    (out/'panels.json').write_text(json.dumps(summaries,indent=2)+'\n');(out/'forecast-sources.json').write_text(json.dumps(folders,indent=2)+'\n');(out/'summary.json').write_text(json.dumps(dict(panels=len(summaries),case_score_rows=sum(x['scored_rows'] for x in summaries),exploratory=True,network_required=False,ai_api_required=False),indent=2)+'\n')

if __name__=='__main__':main()
