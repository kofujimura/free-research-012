"""Check every registered numerical claim against its uniquely selected evidence."""
import argparse,json,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--claims',default='claims.jsonl');ap.add_argument('--out',required=True);ap.add_argument('--results-manifest');args=ap.parse_args();claims=[json.loads(s) for s in (ROOT/args.claims).read_text().splitlines() if s.strip()];cache={};checked=[];rewrite={}
    if args.results_manifest:
        original=json.loads((ROOT/'config/report-results.json').read_text());actual=json.loads(pathlib.Path(args.results_manifest).read_text());rewrite={v:actual[k] for k,v in original.items() if k in actual}
    required={'claim_id','text','status','evidence_paths','source_ids','experiment_ids','scope','verify','expected','exploratory','reader_implication'}
    for claim in claims:
        assert required<=claim.keys()
        for check in claim['verify']['checks']:
            path=check['path']
            for old,new in rewrite.items():
                if path.startswith(old+'/'):path=new+path[len(old):];break
            if path not in cache:cache[path]=pd.read_csv(ROOT/path,dtype={'truth_lag':str},float_precision='round_trip')
            d=cache[path];mask=np.ones(len(d),bool)
            for key,value in check['filters'].items():mask&=d[key].eq(value).to_numpy()
            g=d.loc[mask];assert len(g)==1,(claim['claim_id'],check['filters'],len(g));r=g.iloc[0]
            for key,value in check['values'].items():
                if isinstance(value,(int,float)):assert np.isclose(r[key],value,rtol=1e-12,atol=1e-14), (claim['claim_id'],key)
                else:assert r[key]==value
            checked.append(dict(claim_id=claim['claim_id'],path=path,fields=len(check['values']),passed=True))
    result=dict(claims=len(claims),checks=checked,all_registered_values_match=True,scope='Numerical evidence correspondence only; interpretations still require scientific review.');p=pathlib.Path(args.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(claims=len(claims),evidence_rows=len(checked),passed=True)))

if __name__=='__main__':main()
