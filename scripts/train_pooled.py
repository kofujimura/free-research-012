"""Bounded weekly quantile boosting using only already-matured public labels."""
import argparse,hashlib,json,os,pathlib,time
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from prepare_inputs import ROOT

PARAMS=dict(learning_rate=.05,max_iter=120,max_leaf_nodes=15,min_samples_leaf=50,l2_regularization=1.,max_bins=255,categorical_features=None,early_stopping=False,random_state=12012)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--features',required=True);ap.add_argument('--start',type=int,default=0);ap.add_argument('--stop',type=int,required=True);args=ap.parse_args();base=ROOT/args.features;out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);folder=out/'models';folder.mkdir();cfg=json.loads((base/'panel-config.json').read_text());issues=json.loads((base/'test-issues.json').read_text())[args.start:args.stop]
    if len(issues)>12:raise ValueError('At most twelve issue weeks per bounded fit job')
    data=np.load(base/'features.npz');x=data['X'];y=data['y'];meta=pd.read_csv(base/'rows.csv');case_columns=json.loads((base/'case-columns.json').read_text());names=json.loads((base/'feature-names.json').read_text());deadlines=pd.to_datetime(meta.truth_deadline,utc=True).to_numpy();predictions=[];records=[];storage=0
    for issue in issues:
        tick=time.monotonic();stamp=pd.Timestamp(issue,tz='UTC')+pd.Timedelta(hours=cfg['issue_hour_utc']);eligible=np.where((deadlines<stamp)&np.isfinite(y))[0];recent=sorted(meta.iloc[eligible].issue_date.unique())[-52:];train=eligible[np.isin(meta.issue_date.to_numpy()[eligible],recent)].astype(np.int32);predict=np.where(meta.issue_date.to_numpy()==issue)[0]
        record=dict(issue_date=issue,issue_at_utc=stamp.isoformat(),train_rows=len(train),training_issue_weeks=len(recent),prediction_rows=len(predict),model='pooled_hgb',params=PARAMS,feature_matrix_sha256=digest(base/'features.npz'),status='insufficient_history')
        if len(train)<500 or len(recent)<12:
            records.append(record);print(json.dumps(record),flush=True);continue
        latest=max(deadlines[train]);assert latest<stamp;estimators=[];delta=[]
        for quantile in cfg['quantiles']:
            model=HistGradientBoostingRegressor(loss='quantile',quantile=quantile,**PARAMS);model.fit(x[train],y[train]);estimators.append(model);delta.append(model.predict(x[predict]))
        # The feature column is the observed last log concentration; no future labels.
        q=np.stack(delta,axis=1)+x[predict,names.index('last_log_value')][:,None];crossings=int((np.diff(q,axis=1)<0).sum());q=np.sort(q,axis=1);assert np.isfinite(q).all()
        frame=meta.iloc[predict][case_columns].copy();frame['model']='pooled_hgb';frame['variant']='native';frame['growth_score']=np.nan
        for j,name in enumerate(['q10','q20','q30','q40','q50','q60','q70','q80','q90']):frame[name]=q[:,j]
        frame['training_n']=len(train);frame['training_latest_deadline']=str(latest);predictions.append(frame)
        artifact=folder/(issue+'.joblib');joblib.dump(dict(estimators=estimators,feature_names=names,train_indices=train,predict_indices=predict,issue_date=issue,params=PARAMS),artifact,compress=3);storage+=artifact.stat().st_size
        model_path=str(artifact.relative_to(ROOT)) if artifact.is_relative_to(ROOT) else str(artifact.resolve())
        record.update(status='completed',latest_training_reference_deadline=str(latest),training_indices_sha256=hashlib.sha256(train.tobytes()).hexdigest(),model_path=model_path,model_sha256=digest(artifact),native_quantile_crossings=crossings,elapsed_seconds=time.monotonic()-tick);records.append(record)
        pd.concat(predictions,ignore_index=True).to_csv(out/'case-forecasts.csv.gz',index=False,compression={'method':'gzip','mtime':0});(out/'model-records.jsonl').write_text(''.join(json.dumps(r,default=lambda z:z.item() if isinstance(z,np.generic) else str(z))+'\n' for r in records));print(json.dumps(record),flush=True)
    (out/'model-records.jsonl').write_text(''.join(json.dumps(r,default=lambda z:z.item() if isinstance(z,np.generic) else str(z))+'\n' for r in records))
    if not predictions:pd.DataFrame(columns=case_columns+['model','variant','growth_score','q10','q20','q30','q40','q50','q60','q70','q80','q90']).to_csv(out/'case-forecasts.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    result=dict(issue_weeks=len(issues),completed_weeks=sum(r['status']=='completed' for r in records),predicted_rows=sum(len(z) for z in predictions),model_bytes=storage,model_inference_local=True,training_uses_only_matured_labels=True,exploratory=True);(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
