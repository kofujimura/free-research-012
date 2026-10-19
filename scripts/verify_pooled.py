"""Replay saved local models and independently check maturity of every training row."""
import argparse,datetime as dt,hashlib,json,pathlib
import joblib
import numpy as np
import pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[1]

def stamp(x):return dt.datetime.fromisoformat(x.replace('Z','+00:00'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--features',required=True);ap.add_argument('--fit-dir',action='append',required=True);ap.add_argument('--out',required=True);ap.add_argument('--expected-features');args=ap.parse_args();out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);base=ROOT/args.features;data=np.load(base/'features.npz');x=data['X'];meta=pd.read_csv(base/'rows.csv');names=json.loads((base/'feature-names.json').read_text());records=[];maximum=0.;total=0
    if args.expected_features:
        expected=ROOT/args.expected_features;old=np.load(expected/'features.npz');np.testing.assert_array_equal(x,old['X']);np.testing.assert_array_equal(data['y'],old['y']);assert names==json.loads((expected/'feature-names.json').read_text());pd.testing.assert_frame_equal(meta,pd.read_csv(expected/'rows.csv'),check_dtype=False)
    for directory in args.fit_dir:
        p=ROOT/directory;saved=pd.read_csv(p/'case-forecasts.csv.gz',float_precision='round_trip')
        for line in (p/'model-records.jsonl').read_text().splitlines():
            r=json.loads(line)
            if r['status']!='completed':continue
            path=ROOT/r['model_path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==r['model_sha256'];model=joblib.load(path);indices=model['train_indices'];pred=model['predict_indices'];assert hashlib.sha256(indices.tobytes()).hexdigest()==r['training_indices_sha256'];issue=stamp(r['issue_at_utc'])
            assert all(stamp(meta.iloc[int(i)].truth_deadline)<issue for i in indices)
            assert len(indices)>=500 and meta.iloc[indices].issue_date.nunique()>=12
            values=np.sort(np.stack([m.predict(x[pred]) for m in model['estimators']],axis=1)+x[pred,names.index('last_log_value')][:,None],axis=1)
            old=saved[saved.issue_date==r['issue_date']][['q10','q20','q30','q40','q50','q60','q70','q80','q90']].to_numpy();assert values.shape==old.shape;diff=float(np.max(np.abs(values-old)));assert diff<=1e-12;maximum=max(maximum,diff);total+=len(pred);records.append(dict(issue_date=r['issue_date'],training_rows=len(indices),prediction_rows=len(pred),max_absolute_quantile_difference=diff,all_training_labels_matured_before_issue=True))
    result=dict(weeks=len(records),prediction_rows=total,max_absolute_quantile_difference=maximum,past_label_checks_pass=True,regenerated_features_match_expected=True if args.expected_features else None,network_required=False,ai_api_required=False,models_replayed_without_refitting=True,independent_external_replication=False);(out/'weeks.json').write_text(json.dumps(records,indent=2)+'\n');(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
