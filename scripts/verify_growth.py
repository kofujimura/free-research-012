"""Cross-check saved ROC/AUC with sklearn and original planned alert counts."""
import argparse,json,pathlib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--growth',required=True);ap.add_argument('--panel',required=True);ap.add_argument('--out',required=True);ap.add_argument('--original-alerts');args=ap.parse_args();base=ROOT/args.growth;panel=ROOT/args.panel;out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((panel/'panel-config.json').read_text()) if (panel/'panel-config.json').exists() else json.loads((ROOT/'config/main.json').read_text());d=pd.read_csv(base/'case-growth.csv.gz',float_precision='round_trip');roc=pd.read_csv(base/'roc-summary.csv',float_precision='round_trip');maximum=0.;checked=0
    for period,rows in roc.groupby('period',sort=True):
        start=cfg['test_start'] if period=='all_test' else ('2026-01-05' if cfg.get('issue_frequency')=='W-MON' else '2026-01-02');test=d[d.issue_date.between(start,cfg['test_end'])];test=test[(test.model!='timesfm_2p5')|(test.issue_date>=cfg['timesfm_interpretation_start'])]
        grouped={key:g for key,g in test.groupby(['rise_ratio','model','source_age_weeks','target_offset_days'],sort=False)}
        for r in rows.to_dict('records'):
            g=grouped[(r['rise_ratio'],r['model'],r['source_age_weeks'],r['target_offset_days'])];label=r['stratum']
            if label.startswith('level:'):g=g[g.unit_level==label[6:]]
            elif label!='all':g=g[g.pathogen==label]
            assert len(g)==r['n'] and int(g.event.sum())==r['positive'];actual=float(roc_auc_score(g.event,g.growth_score));difference=abs(actual-r['auc']);assert difference<=1e-12;maximum=max(maximum,difference);checked+=1
    primary=None
    if args.original_alerts:
        old=pd.read_csv(ROOT/args.original_alerts,float_precision='round_trip');new=pd.read_csv(base/'growth-paired.csv',float_precision='round_trip');new=new[(new.rise_ratio==2)&(new.reference_model=='ensemble')&(new.unit_level=='all')];keys=['period','model','source_age_weeks','target_offset_days','side'];p=old.merge(new,on=keys,suffixes=('_old','_new'),validate='one_to_one');assert len(p)==len(old)
        for column in ['n','positive','negative','tp','fp']:
            assert np.array_equal(p[column+'_old'].to_numpy(),p[column+'_new'].to_numpy()),column
        primary=dict(paired_summary_rows=len(p),all_original_planned_twofold_alert_counts_unchanged=True)
    result=dict(roc_summary_rows_verified=checked,maximum_auc_difference_from_sklearn=maximum,original_primary_alert_check=primary,clinical_validation=False,independent_external_replication=False);(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
