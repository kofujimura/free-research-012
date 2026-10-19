"""Publication-time uncertainty: replay matching saved forecasts, no new inference."""
import argparse,json,pathlib
import numpy as np
import pandas as pd
import analyze as a
import panel_analysis as panel
from prepare_inputs import ROOT

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scenarios',required=True);ap.add_argument('--forecast-map',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
    scenarios=json.loads((ROOT/args.scenarios).read_text());mapping=json.loads((ROOT/args.forecast_map).read_text());all_comp=[];summaries=[];a.KEY=panel.KEY;a.MODELS=a.MODELS+panel.EXTRA
    for scenario in scenarios:
        folder=scenario['panel_path'];base=ROOT/folder;cfg=json.loads((base/'panel-config.json').read_text());a.INPUT_DIR=folder;a.FORECAST_DIRS=mapping[scenario['country']]
        cases,truth,native,inputs=a.assemble(cfg,allow_unused_inputs=True)
        if 'truth_floor_fraction' not in truth:truth['truth_floor_fraction']=np.nan
        native,choices=panel.add_competitors(native,truth,cfg);cal,status=panel.calibrate(native,truth,cfg);fc=pd.concat([native,cal],ignore_index=True);scored,check=a.score(fc,truth,cfg);comp=panel.compare(scored,cfg);comp['country']=scenario['country'];comp['availability_shift_hours']=scenario['shift_hours'];all_comp.append(comp)
        child=out/(scenario['country']+'-shift'+str(scenario['shift_hours']));child.mkdir();comp.to_csv(child/'comparisons.csv',index=False);fc.to_csv(child/'case-forecasts.csv.gz',index=False,compression={'method':'gzip','mtime':0});status.to_csv(child/'calibration-status.csv.gz',index=False,compression={'method':'gzip','mtime':0});(child/'selector.jsonl').write_text(''.join(json.dumps(x,default=lambda z:z.item() if isinstance(z,np.generic) else str(z))+'\n' for x in choices))
        summary=dict(scenario,native_case_predictions=len(native),calibrated_case_predictions=len(cal),wis_identity_max_error=check,saved_predictions_reused=True,model_inference_required=False);summaries.append(summary);print(json.dumps(summary),flush=True)
    pd.concat(all_comp,ignore_index=True).to_csv(out/'comparisons.csv',index=False);(out/'summary.json').write_text(json.dumps(dict(scenarios=summaries,exploratory=True,public_timestamp_truth_not_proved=True),indent=2)+'\n')

if __name__=='__main__':main()
