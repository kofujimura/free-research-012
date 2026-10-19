"""Only past numeric context, target calendar and pathogen flags as features."""
import argparse,json,os,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT
from panel_analysis import KEY

def features(ctx,row):
    y=np.asarray(ctx['log_values'],dtype=float);last=float(y[-1]);result=dict(context_length=len(y),last_log_value=last,horizon=float(row['horizon']))
    for lag in [1,2,4,8,13,26,52]:result['lag_difference_'+str(lag)]=float(last-y[-1-lag]) if len(y)>lag else np.nan
    for k in [4,8,13,26,52]:
        v=y[-k:] if len(y)>=k else None;x=np.arange(k,dtype=float)-(k-1)/2
        values=[float(v.mean()-last),float(v.std(ddof=0)),float(np.dot(x,v-v.mean())/np.dot(x,x)),float(np.ptp(v))] if v is not None else [np.nan]*4
        for name,value in zip(['mean_minus_last','std','slope','range'],values):result[name+'_'+str(k)]=value
    phase=2*np.pi*(pd.Timestamp(row['target_date'])-pd.Timestamp('2000-01-01')).days/365.2425;result.update(target_sin=float(np.sin(phase)),target_cos=float(np.cos(phase)))
    for pathogen in ['SARS-CoV-2','Influenza A','RSV A/B']:result['pathogen_'+pathogen]=float(row['pathogen']==pathogen)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--panel',default='experiments/E024-site-panel-inputs');args=ap.parse_args()
    out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);base=ROOT/args.panel;cfg=json.loads((base/'panel-config.json').read_text());inputs=json.loads((base/'inputs.json').read_text());cases=pd.read_csv(base/'cases.csv');cases=cases[(cases.input_mode=='actual')&(cases.status=='ok')].reset_index(drop=True);case_columns=list(cases.columns)
    cases['_feature_row']=np.arange(len(cases))
    truth=pd.read_csv(base/'truth.csv',dtype={'truth_lag':str});truth=truth[truth.truth_lag=='56'][KEY+['y_log','truth_deadline','truth_commit_time']];meta=cases.merge(truth,on=KEY,how='left',sort=False,validate='many_to_one').sort_values('_feature_row').reset_index(drop=True);assert np.array_equal(meta._feature_row.to_numpy(),np.arange(len(cases)))
    rows=[features(inputs[r['input_id']],r) for r in cases.to_dict('records')];frame=pd.DataFrame(rows);x=frame.to_numpy(dtype=np.float64);assert not np.isinf(x).any();target=meta.y_log.to_numpy()-frame.last_log_value.to_numpy();meta['row_index']=np.arange(len(meta));meta['target_change']=target
    meta.to_csv(out/'rows.csv',index=False);np.savez_compressed(out/'features.npz',X=x,y=target);(out/'feature-names.json').write_text(json.dumps(list(frame.columns),indent=2)+'\n');(out/'case-columns.json').write_text(json.dumps(case_columns,indent=2)+'\n');(out/'panel-config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    issues=sorted(cases.loc[cases.issue_date>=cfg['test_start'],'issue_date'].unique());(out/'test-issues.json').write_text(json.dumps(issues,indent=2)+'\n');summary=dict(rows=len(meta),features=x.shape[1],test_issue_weeks=len(issues),feature_names=list(frame.columns),no_future_response_in_features=True,labels_filtered_by_maturity_during_each_fit=True);(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
