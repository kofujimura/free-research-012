"""CQR-derived rolling interval corrections; explicitly no coverage theorem claim."""
import argparse,json,pathlib
import numpy as np
import pandas as pd
import analyze as a
import panel_analysis as panel
from prepare_inputs import ROOT,load_config

MODELS=['ensemble','ensemble_extended','rolling_best_classical','chronos_bolt_base','timesfm_2p5']

def correct(native,truth,cfg,window):
    merged=native.merge(truth[truth.truth_lag=='56'][panel.KEY+['y_log','truth_deadline']],on=panel.KEY,validate='many_to_one');rows=[];crossings=0;max_median=0.
    for _,g in merged.groupby(['model']+panel.GROUP,sort=True):
        g=g.sort_values('issue_date');deadlines=pd.to_datetime(g.truth_deadline,utc=True).to_numpy();y=g.y_log.to_numpy();q=g[a.QCOLS].to_numpy();records=g.to_dict('records')
        errors=np.stack([np.maximum(q[:,lo]-y,y-q[:,hi]) for lo,hi in [(0,8),(1,7),(2,6),(3,5)]],axis=1)
        for r in records:
            past=np.where((deadlines<pd.Timestamp(r['issue_at_utc']))&np.isfinite(y))[0][-window:];n=len(past)
            if n<cfg['calibration_minimum']:continue
            current=np.asarray([r[x] for x in a.QCOLS],dtype=float);median=current[4];deltas=[]
            for j,(lo,hi,alpha) in enumerate([(0,8,20),(1,7,40),(2,6,60),(3,5,80)]):
                rank=((n+1)*(100-alpha)+99)//100
                if not 1<=rank<=n:raise ValueError('Insufficient finite-sample rank')
                delta=float(np.sort(errors[past,j])[rank-1]);current[lo]-=delta;current[hi]+=delta;deltas.append(delta)
            before=current.copy();current[:4]=np.minimum.accumulate(np.minimum(current[:4],median)[::-1])[::-1];current[5:]=np.maximum.accumulate(np.maximum(current[5:],median))
            crossings+=int(np.any(before!=current));max_median=max(max_median,abs(current[4]-r['q50']))
            assert np.isfinite(current).all() and (np.diff(current)>=0).all()
            new={k:v for k,v in r.items() if k not in ['y_log','truth_deadline']};new.update(dict(zip(a.QCOLS,map(float,current))));new.update(variant='calibrated',calibration_n=n,calibration_window=window,cqr_delta80=deltas[0],cqr_delta60=deltas[1],cqr_delta40=deltas[2],cqr_delta20=deltas[3],nesting_adjusted=bool(np.any(before!=current)));rows.append(new)
    assert max_median==0
    return pd.DataFrame(rows),dict(window=window,calibrated_rows=len(rows),nesting_adjusted_rows=crossings,max_median_change=max_median)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--forecast-csv',required=True);ap.add_argument('--panel',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);base=ROOT/args.panel
    cfg=json.loads((base/'panel-config.json').read_text()) if (base/'panel-config.json').exists() else dict(load_config(),issue_frequency='W-FRI')
    fc=pd.read_csv(ROOT/args.forecast_csv);truth=pd.read_csv(base/'truth.csv',dtype={'truth_lag':str})
    if 'unit_id' not in fc:fc['unit_id']=fc.pathogen;truth['unit_id']=truth.pathogen;fc['unit_level']='national'
    if 'truth_floor_fraction' not in truth:truth['truth_floor_fraction']=np.nan
    native=fc[(fc.input_mode=='actual')&(fc.variant=='native')&fc.model.isin(MODELS)].copy();a.KEY=panel.KEY;results=[];quality=[];metrics=[];case_outputs=[]
    for window in [12,26,52]:
        cal,check=correct(native,truth,cfg,window);quality.append(check);scored,wischeck=a.score(cal,truth,cfg);comp=panel.compare(scored,cfg);comp['reference_interval']='same_correction';comp['calibration_window']=window;results.append(comp)
        native_scores,_=a.score(native,truth,cfg);mixed=pd.concat([scored[scored.model.isin(['chronos_bolt_base','timesfm_2p5'])],native_scores[native_scores.model.isin(['ensemble','ensemble_extended','rolling_best_classical'])].assign(variant='calibrated')],ignore_index=True)
        cross=panel.compare(mixed,cfg);cross['reference_interval']='native';cross['calibration_window']=window;results.append(cross)
        key=panel.KEY+['model','source_age_weeks','truth_lag'];paired=scored.merge(native_scores,on=key,suffixes=('_cal','_native'),validate='one_to_one');difference=float(np.max(np.abs(paired.mae_cal-paired.mae_native))) if len(paired) else 0.
        assert difference==0;check.update(max_paired_point_mae_change=difference,wis_identity_max_error=wischeck)
        test=scored[(scored.issue_date>=cfg['test_start'])&(~scored.known_target)];test=test[(test.model!='timesfm_2p5')|(test.issue_date>=cfg['timesfm_interpretation_start'])]
        group=['truth_lag','model','source_age_weeks','target_offset_days','unit_level'];agg=test.groupby(group).agg(n=('wis','size'),wis=('wis','mean'),mae=('mae','mean'),covered80=('covered80','mean'),width80=('width80','mean')).reset_index();agg['calibration_window']=window;metrics.append(agg);case_outputs.append(cal)
    pd.concat(results,ignore_index=True).to_csv(out/'comparisons.csv',index=False);pd.concat(metrics,ignore_index=True).to_csv(out/'model-scores.csv',index=False);pd.concat(case_outputs,ignore_index=True).to_csv(out/'case-forecasts.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    result=dict(exploratory=True,windows=quality,formal_coverage_guarantee_claimed=False,model_inference_required=False,network_required=False,ai_api_required=False)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
