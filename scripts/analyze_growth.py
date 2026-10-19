"""Saved-output growth detection: prospective thresholds and retrospective ROC."""
import argparse,hashlib,json,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT

RATIOS=[1.1,1.25,1.5,2.,3.]
ORIGINAL_MODELS=['naive','damped_trend','autoarima','autoets','ensemble','chronos_bolt_base','timesfm_2p5']
MODELS=ORIGINAL_MODELS+['autotheta','seasonal_naive','harmonic_arima','ensemble_extended','rolling_best_classical']
BASEKEY=['issue_date','unit_id','pathogen','target_date','target_offset_days']

def roc(event,score):
    event=np.asarray(event,dtype=bool);score=np.asarray(score,dtype=float);pos=int(event.sum());neg=len(event)-pos
    if not pos or not neg:return None,[]
    order=np.argsort(-score,kind='stable');y=event[order];s=score[order];ends=np.r_[np.where(np.diff(s)!=0)[0],len(s)-1]
    tp=np.r_[0,np.cumsum(y)[ends]];fp=np.r_[0,np.cumsum(~y)[ends]];tpr=tp/pos;fpr=fp/neg
    auc=float(np.trapezoid(tpr,fpr));at=float(max(tpr[fpr<=.1]));vertices=[dict(threshold=None if i==0 else float(s[ends[i-1]]),false_positive_rate=float(x),true_positive_rate=float(z)) for i,(x,z) in enumerate(zip(fpr,tpr))]
    return dict(auc=auc,retrospective_best_tpr_at_fpr_at_most_point1=at,positive=pos,negative=neg),vertices

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--forecast-csv',required=True);ap.add_argument('--panel',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();base=ROOT/args.panel;out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((base/'panel-config.json').read_text()) if (base/'panel-config.json').exists() else json.loads((ROOT/'config/main.json').read_text());primary_panel=base.resolve()==(ROOT/'experiments/E007-prepare-inputs-fixed').resolve()
    truth=pd.read_csv(base/'truth.csv',dtype={'truth_lag':str});fc=pd.read_csv(ROOT/args.forecast_csv,float_precision='round_trip')
    if 'unit_id' not in fc:fc['unit_id']=fc.pathogen;truth['unit_id']=truth.pathogen;fc['unit_level']='national'
    keys=BASEKEY;native=fc[(fc.variant=='native')&(fc.input_mode=='actual')&fc.model.isin(MODELS)&(~fc.known_target)]
    d=native.merge(truth[truth.truth_lag=='56'],on=keys,validate='many_to_one');d=d[d.growth_log.notna()].copy()
    rows=[]
    group=['model','unit_id','pathogen','source_age_weeks','target_offset_days']
    for key,g in d.groupby(group,sort=True):
        g=g.sort_values('issue_date');deadline=pd.to_datetime(g.truth_deadline,utc=True).to_numpy();growth=g.growth_log.to_numpy();scores=g.growth_score.to_numpy();records=g.to_dict('records')
        for ratio in RATIOS:
            event=growth>=np.log10(ratio)
            for i,r in enumerate(records):
                previous=np.where((deadline<pd.Timestamp(r['issue_at_utc']))&(~event))[0][-cfg['calibration_maximum']:];n=len(previous)
                threshold=float(np.quantile(scores[previous],1-cfg['false_positive_target'])) if n>=cfg['calibration_minimum'] else np.nan
                rows.append({k:r[k] for k in keys+['issue_at_utc','unit_level','model','source_age_weeks','growth_score','growth_log']}|dict(rise_ratio=ratio,event=bool(event[i]),threshold=threshold,threshold_n=n,alarm=bool(scores[i]>threshold) if np.isfinite(threshold) else None))
    predictions=pd.DataFrame(rows);predictions.to_csv(out/'case-growth.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    summary=[];paired=[];rocrows=[];curves=[];bootstraprows=[]
    for period in ['all_test','year2026']:
        start=cfg['test_start'] if period=='all_test' else ('2026-01-05' if cfg.get('issue_frequency')=='W-MON' else '2026-01-02')
        test=predictions[predictions.issue_date.between(start,cfg['test_end'])];test=test[(test.model!='timesfm_2p5')|(test.issue_date>=cfg['timesfm_interpretation_start'])]
        for key,g in test.groupby(['rise_ratio','model','source_age_weeks','target_offset_days'],sort=True):
            ratio,model,age,offset=key
            for label,sub in [('all',g),*[(p,g[g.pathogen==p]) for p in sorted(g.pathogen.unique())],*[("level:"+p,g[g.unit_level==p]) for p in sorted(g.unit_level.unique())]]:
                if sub.empty:continue
                metadata=dict(period=period,rise_ratio=ratio,model=model,source_age_weeks=age,target_offset_days=offset,stratum=label,roc_curve_prespecified=bool(primary_panel and ratio==2 and model in ORIGINAL_MODELS),auc_exploratory=True)
                rocresult,vertices=roc(sub.event,sub.growth_score)
                if rocresult:rocrows.append(metadata|rocresult|dict(n=len(sub),n_units=sub.unit_id.nunique(),positive_issue_weeks=sub.loc[sub.event,'issue_date'].nunique(),retrospective=True));curves.extend(metadata|v for v in vertices)
                available=sub[sub.threshold.notna()];event=available.event.astype(bool);alarm=available.alarm.astype(bool);pos=int(event.sum());neg=len(available)-pos;tp=int((event&alarm).sum());fp=int((~event&alarm).sum())
                summary.append(metadata|dict(n_intended=len(sub),n=len(available),n_units=available.unit_id.nunique(),n_weeks=available.issue_date.nunique(),positive=pos,negative=neg,positive_issue_weeks=available.loc[event,'issue_date'].nunique(),tp=tp,fp=fp,miss_rate=1-tp/pos if pos else np.nan,false_positive_rate=fp/neg if neg else np.nan,threshold_estimated_only_from_matured_past=True))
        valid=test[test.threshold.notna()]
        for ratio in RATIOS:
            for reference in ['ensemble','ensemble_extended','rolling_best_classical']:
                ref=valid[(valid.model==reference)&(valid.source_age_weeks==0)&(valid.rise_ratio==ratio)]
                for model in ['chronos_bolt_base','timesfm_2p5']:
                    for age in cfg['source_age_weeks']:
                        candidate=valid[(valid.model==model)&(valid.source_age_weeks==age)&(valid.rise_ratio==ratio)]
                        p=candidate.merge(ref,on=keys,suffixes=('_candidate','_reference'),validate='one_to_one')
                        for offset in cfg['target_offsets_days']:
                            z=p[p.target_offset_days==offset]
                            for level in ['all',*sorted(z.unit_level_candidate.unique())]:
                                sub=z if level=='all' else z[z.unit_level_candidate==level]
                                if sub.empty:continue
                                for side in ['candidate','reference']:
                                    event=sub['event_'+side].astype(bool);alarm=sub['alarm_'+side].astype(bool);pos=int(event.sum());neg=len(sub)-pos;tp=int((event&alarm).sum());fp=int((~event&alarm).sum())
                                    paired.append(dict(period=period,rise_ratio=ratio,reference_model=reference,model=model,source_age_weeks=age,target_offset_days=offset,unit_level=level,side=side,n=len(sub),n_units=sub.unit_id.nunique(),positive=pos,negative=neg,positive_issue_weeks=sub.loc[event,'issue_date'].nunique(),tp=tp,fp=fp,miss_rate=1-tp/pos if pos else np.nan,false_positive_rate=fp/neg if neg else np.nan))
    pd.DataFrame(summary).to_csv(out/'growth-summary.csv',index=False);pd.DataFrame(paired).to_csv(out/'growth-paired.csv',index=False);pd.DataFrame(rocrows).to_csv(out/'roc-summary.csv',index=False);pd.DataFrame(curves).to_csv(out/'roc-curves.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    result=dict(prediction_rows=len(predictions),summary_rows=len(summary),paired_rows=len(paired),roc_summary_rows=len(rocrows),growth_ratios=RATIOS,prospective_thresholds=True,retrospective_roc=True,clinical_outcomes_measured=False,original_twofold_roc_prespecified=primary_panel,other_ratios_new_models_and_auc_exploratory=True,network_required=False)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
