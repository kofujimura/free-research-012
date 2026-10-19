"""Matched reference maturity, counterfactual matrix, and transparent input audit."""
import argparse,hashlib,json,pathlib
import numpy as np
import pandas as pd
import analyze as a
from prepare_inputs import ROOT,load_config,Archive,context
from prepare_nz_inputs import NZArchive,eligible_archive

def matched_maturity(out,cfg,primary_dir):
    scores=pd.read_csv(ROOT/primary_dir/'case-scores.csv',dtype={'truth_lag':str})
    d=scores[(scores.input_mode=='actual')&(scores.variant=='native')&(~scores.known_target)&scores.model.isin(['ensemble','chronos_bolt_base','timesfm_2p5'])]
    rows=[]
    for model in ['chronos_bolt_base','timesfm_2p5']:
        for age in cfg['source_age_weeks']:
            candidate=d[(d.model==model)&(d.source_age_weeks==age)];ref=d[(d.model=='ensemble')&(d.source_age_weeks==0)]
            pair=candidate.merge(ref,on=a.KEY+['truth_lag'],suffixes=('_candidate','_reference'),validate='one_to_one')
            counts=pair.groupby(a.KEY).truth_lag.nunique();complete=counts[counts==4].reset_index()[a.KEY];pair=pair.merge(complete,on=a.KEY,validate='many_to_one')
            for period in ['all_test','year2026']:
                start=cfg['test_start'] if period=='all_test' else '2026-01-02'
                if model=='timesfm_2p5':start=max(start,cfg['timesfm_interpretation_start'])
                p=pair[pair.issue_date.between(start,cfg['test_end'])]
                for lag,g in p.groupby('truth_lag',sort=True):
                    for metric in ['wis','mae']:
                        seed=int.from_bytes(hashlib.sha256(f"{cfg['seed']}|maturity|{model}|{age}|{period}|{lag}|{metric}".encode()).digest()[:8],'little')
                        b=a.bootstrap(g,metric,start,cfg['test_end'],8,cfg['bootstrap_repetitions'],seed)
                        rows.append(dict(model=model,source_age_weeks=age,period=period,truth_lag=lag,metric=metric,n_pairs=len(g),n_issue_weeks=g.issue_date.nunique(),candidate_mean=float(g[metric+'_candidate'].mean()),reference_mean=float(g[metric+'_reference'].mean()),**b))
    pd.DataFrame(rows).to_csv(out/'matched-maturity.csv',index=False)
    matrix=[]
    native=scores[(scores.variant=='native')&(~scores.known_target)&scores.truth_lag.isin(['56','latest'])]
    groupkey=a.KEY+['model','source_age_weeks']
    complete=native.groupby(groupkey).size();complete=complete[complete==4].reset_index()[groupkey];native=native.merge(complete,on=groupkey,validate='many_to_one')
    for period in ['all_test','year2026']:
        start=cfg['test_start'] if period=='all_test' else '2026-01-02';test=native[native.issue_date.between(start,cfg['test_end'])];test=test[(test.model!='timesfm_2p5')|(test.issue_date>=cfg['timesfm_interpretation_start'])]
        for key,g in test.groupby(['model','source_age_weeks','input_mode','truth_lag'],sort=True):
            matrix.append(dict(zip(['model','source_age_weeks','input_mode','truth_lag'],key))|dict(period=period,n=len(g),n_weeks=g.issue_date.nunique(),wis=float(g.wis.mean()),mae=float(g.mae.mean())))
    pd.DataFrame(matrix).to_csv(out/'matched-input-reference-matrix.csv',index=False)

def input_audit(out):
    rows=[];contexts=[];availability=[]
    for name,folder,start in [('germany_national','experiments/E007-prepare-inputs-fixed','2025-07-04'),('germany_sites','experiments/E024-site-panel-inputs','2025-07-04'),('nz','experiments/E027-nz-panel-inputs-eligible','2025-07-07')]:
        base=ROOT/folder;cases=pd.read_csv(base/'cases.csv');inputs=json.loads((base/'inputs.json').read_text())
        if 'unit_id' not in cases:cases['unit_id']=cases.pathogen
        c=cases[(cases.input_mode=='actual')&(cases.issue_date>=start)];availability.extend(dict(dataset=name,status=status,n=len(g),known_target=int(g.known_target.sum())) for status,g in c.groupby('status'))
        keys=['issue_date','unit_id','pathogen','target_date','target_offset_days'];fresh=c[(c.source_age_weeks==0)&(c.status=='ok')]
        for age in [0,1,2]:
            old=c[(c.source_age_weeks==age)&(c.status=='ok')];pair=old.merge(fresh,on=keys,suffixes=('_old','_fresh'),validate='one_to_one');pair['advance_weeks']=(pd.to_datetime(pair.last_date_fresh)-pd.to_datetime(pair.last_date_old)).dt.days/7
            pair['information']=np.select([pair.input_id_old==pair.input_id_fresh,pair.last_date_old==pair.last_date_fresh,pair.last_date_old<pair.last_date_fresh],['identical','same_end_revised','new_observations'],default='fresh_end_older')
            for key,g in pair.groupby(['information','advance_weeks'],sort=True):rows.append(dict(dataset=name,source_age_weeks=age,information=key[0],advance_weeks=key[1],n=len(g),n_issue_weeks=g.issue_date.nunique(),known_target=int(g.known_target_old.sum()|g.known_target_fresh.sum())))
        for uid,ctx in inputs.items():
            v=np.asarray(ctx['log_values']);contexts.append(dict(dataset=name,input_id=uid,context_length=len(v),imputed_context=ctx['imputed_context'],real_observations=ctx['real_observations_context'],imputed_fraction=ctx['imputed_context']/len(v),constant=bool(np.ptp(v)<=1e-12),last_two_equal=bool(abs(v[-1]-v[-2])<=1e-12),log_range=float(np.ptp(v))))
    pd.DataFrame(rows).to_csv(out/'information-advance-counts.csv',index=False);pd.DataFrame(contexts).to_csv(out/'context-audit.csv',index=False);pd.DataFrame(availability).to_csv(out/'intended-case-availability.csv',index=False)

def timestamp_audit(out,cfg):
    rows=[]
    for dataset,base,archive in [('germany_national','experiments/E007-prepare-inputs-fixed',Archive(cfg)),('nz','experiments/E027-nz-panel-inputs-eligible',NZArchive(eligible_archive(json.loads((ROOT/'experiments/E020-nz-vintage-audit/archive-index.json').read_text()))[0]))]:
        cases=pd.read_csv(ROOT/base/'cases.csv');cases=cases[(cases.input_mode=='actual')&(cases.status=='ok')&(cases.issue_date>= ('2025-07-04' if dataset=='germany_national' else '2025-07-07'))].drop_duplicates(['issue_date','pathogen','source_age_weeks']+(['unit_id'] if dataset=='nz' else []))
        cache={}
        for shift in [-48,-24,24,48]:
            # Availability=Git time+shift, hence query the original archive at cutoff-shift.
            changed_release=changed_input=missing=0
            for r in cases.to_dict('records'):
                cutoff=pd.Timestamp(r['source_cutoff'])-pd.Timedelta(hours=shift)
                record=archive.usable_asof(cutoff,r['pathogen'])[0] if dataset=='germany_national' else archive.asof(cutoff)
                if record is None:missing+=1;continue
                changed_release+=record['commit']!=r['source_commit'];unit=r['pathogen'] if dataset=='germany_national' else r['unit_id'];key=(record['commit'],unit)
                if key not in cache:
                    series=archive.series_at(record,unit) if dataset=='germany_national' else archive.get_series(record,unit);ctx,_=context(series,cfg);cache[key]=ctx['input_id'] if ctx else None
                if cache[key] is None:missing+=1
                changed_input+=cache[key]!=r['input_id']
            rows.append(dict(dataset=dataset,availability_shift_hours=shift,n_unit_issue_age_conditions=len(cases),changed_source_release=int(changed_release),changed_numeric_dated_input=int(changed_input),unavailable_after_shift=missing,performance_reestimated=False))
    pd.DataFrame(rows).to_csv(out/'timestamp-proxy-sensitivity.csv',index=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--primary-dir',default='experiments/E011-primary-analysis/results');args=ap.parse_args();out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);cfg=load_config()
    matched_maturity(out,cfg,args.primary_dir);input_audit(out);timestamp_audit(out,cfg)
    result=dict(exploratory=True,reference_maturity_matched_on_four_available_versions=True,public_time_proved=False,ai_api_required=False,network_required=False,model_inference_required=False)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
