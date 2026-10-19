"""Independent stdlib checks of saved input signatures and timing constraints."""
import argparse,csv,datetime as dt,hashlib,json,math,pathlib
from prepare_inputs import ROOT

def stamp(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def check(folder):
    base=ROOT/folder;inputs=json.loads((base/'inputs.json').read_text());n_actual=n_truth=n_ok=0;max_h=0
    for uid,ctx in inputs.items():
        signature=json.dumps([ctx['dates'],ctx['log_values']],separators=(',',':'),allow_nan=False)
        assert hashlib.sha256(signature.encode()).hexdigest()[:24]==uid
        dates=list(map(dt.date.fromisoformat,ctx['dates']));assert len(dates)==len(ctx['log_values'])
        assert dates[-1].isoformat()==ctx['last_date'] and all((b-a).days==7 for a,b in zip(dates,dates[1:]))
        assert all(math.isfinite(x) for x in ctx['log_values'])
    with (base/'cases.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            if r['input_mode']!='actual':continue
            if r.get('source_commit_time'):assert stamp(r['source_commit_time'])<=stamp(r['source_cutoff'])
            n_actual+=1
            if r['status']!='ok':continue
            ctx=inputs[r['input_id']];last=dt.date.fromisoformat(ctx['last_date']);target=dt.date.fromisoformat(r['target_date']);h=int(float(r['horizon']))
            assert (target-last).days==7*h and last<=stamp(r['source_cutoff']).date()
            assert (h<=0)==(r['known_target']=='True') and h<=16
            max_h=max(max_h,h);n_ok+=1
    with (base/'truth.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            if r.get('truth_commit_time'):assert stamp(r['truth_commit_time'])<=stamp(r['truth_deadline'])
            if r['truth_lag']!='latest':
                expected=dt.datetime.combine(dt.date.fromisoformat(r['target_date']),dt.time(),dt.timezone.utc)+dt.timedelta(days=int(r['truth_lag'])+1,seconds=-1)
                assert stamp(r['truth_deadline'])==expected
            n_truth+=1
    return dict(panel=folder,unique_inputs=len(inputs),actual_intended_cases=n_actual,actual_ok_cases=n_ok,truth_rows=n_truth,maximum_valid_horizon=max_h,signature_date_spacing_source_cutoffs_and_truth_deadlines_pass=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--panel',action='append');args=ap.parse_args();out=pathlib.Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    result=[check(x) for x in (args.panel or ['experiments/E007-prepare-inputs-fixed','experiments/E024-site-panel-inputs','experiments/E027-nz-panel-inputs-eligible','experiments/E045-raw-sars-inputs'])]
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
