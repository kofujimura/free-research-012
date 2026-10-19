"""Compare complete regenerated numerical tables with their frozen expected files."""
import argparse,json,pathlib
import numpy as np
import pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--config',default='config/reproduction.json');ap.add_argument('--quick',action='store_true');args=ap.parse_args();out=pathlib.Path(args.out);cfg=json.loads((ROOT/args.config).read_text());checks=[]
    for item in cfg['compare_tables']:
        if args.quick and item.get('large_optional',False):continue
        expected=pd.read_csv(ROOT/item['expected'],float_precision='round_trip');actual=pd.read_csv(out/item['actual'],float_precision='round_trip');pd.testing.assert_frame_equal(actual,expected,check_exact=False,rtol=1e-9,atol=1e-11,check_dtype=False)
        differences=[]
        for c in expected.select_dtypes(include='number').columns:
            aa=actual[c].to_numpy(dtype=float);ee=expected[c].to_numpy(dtype=float);valid=np.isfinite(aa)&np.isfinite(ee)
            if valid.any():differences.append(float(np.max(np.abs(aa[valid]-ee[valid]))))
        checks.append(dict(expected=item['expected'],actual=item['actual'],rows=len(expected),columns=len(expected.columns),max_absolute_numeric_difference=max(differences,default=0.),all_values_and_labels_match=True))
    result=dict(checks=checks,passed=True,comparison_relative_tolerance=1e-9,comparison_absolute_tolerance=1e-11,independent_reproduction=False,saved_output_recalculation_by_same_researcher=True);(out/'expected-comparison.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,tables=len(checks),rows=sum(x['rows'] for x in checks),max_absolute_numeric_difference=max((x['max_absolute_numeric_difference'] for x in checks),default=0.))))

if __name__=='__main__':main()
