"""Check newly refitted issue-week predictions against the original saved fit."""
import argparse,json,pathlib
import numpy as np
import pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--original',required=True);ap.add_argument('--refit',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();old=ROOT/args.original;new=ROOT/args.refit;out=pathlib.Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);a=pd.read_csv(old/'case-forecasts.csv.gz',float_precision='round_trip');b=pd.read_csv(new/'case-forecasts.csv.gz',float_precision='round_trip');a=a[a.issue_date.isin(b.issue_date.unique())];keys=['issue_date','unit_id','pathogen','target_date','target_offset_days','source_age_weeks'];p=a.merge(b,on=keys,suffixes=('_original','_refit'),validate='one_to_one');assert len(p)==len(a)==len(b)
    names=['q10','q20','q30','q40','q50','q60','q70','q80','q90'];difference=float(np.max(np.abs(p[[q+'_original' for q in names]].to_numpy()-p[[q+'_refit' for q in names]].to_numpy())));assert difference<=1e-12
    result=dict(issue_weeks=int(b.issue_date.nunique()),prediction_rows=len(b),quantiles_per_row=len(names),max_absolute_quantile_difference=difference,refitted_from_features=True,independent_external_replication=False);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
