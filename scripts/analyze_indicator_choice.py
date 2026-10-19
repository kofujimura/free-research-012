"""Compare indicator-specific model ratios on exactly matched SARS forecast cases."""
import argparse,hashlib,json,math,pathlib
import numpy as np
import pandas as pd
import analyze as a
import panel_analysis as panel
from prepare_inputs import ROOT,load_config

def scored(path,truthpath,cfg):
    fc=pd.read_csv(path);truth=pd.read_csv(truthpath,dtype={'truth_lag':str});fc=fc[(fc.input_mode=='actual')&(fc.pathogen=='SARS-CoV-2')];truth=truth[(truth.pathogen=='SARS-CoV-2')&(truth.truth_lag=='56')]
    if 'unit_id' not in fc:fc['unit_id']=fc.pathogen;truth['unit_id']=truth.pathogen
    a.KEY=panel.KEY;result,_=a.score(fc,truth,cfg);return result[~result.known_target]

def paired(d,model,reference,age,variant):
    v=d[d.variant==variant];c=v[(v.model==model)&(v.source_age_weeks==age)];r=v[(v.model==reference)&(v.source_age_weeks==0)]
    return c.merge(r,on=panel.KEY,suffixes=('_candidate','_reference'),validate='one_to_one')

def boot(p,metric,start,cfg,block,seed):
    columns=[metric+'_'+side+'_'+variant for variant in ['raw','normalized'] for side in ['candidate','reference']]
    weeks=pd.date_range(start,cfg['test_end'],freq='W-FRI').strftime('%Y-%m-%d');g=p.groupby('issue_date')[columns].sum().reindex(weeks,fill_value=0);values=g.to_numpy();rng=np.random.default_rng(seed);length=min(block,len(g));reps=cfg['bootstrap_repetitions'];starts=rng.integers(0,len(g)-length+1,size=(reps,math.ceil(len(g)/length)));ix=(starts[:,:,None]+np.arange(length)).reshape(reps,-1)[:,:len(g)];sums=values[ix].sum(axis=1);valid=(sums[:,1]>0)&(sums[:,3]>0)
    raw=sums[valid,0]/sums[valid,1];normal=sums[valid,2]/sums[valid,3];total=values.sum(axis=0)
    def bounds(x):return list(map(float,np.quantile(x,[.025,.975]))) if len(x) else [np.nan,np.nan]
    rl,rh=bounds(raw);nl,nh=bounds(normal);dl,dh=bounds(raw-normal)
    return dict(raw_ratio=float(total[0]/total[1]),normalized_ratio=float(total[2]/total[3]),ratio_difference=float(total[0]/total[1]-total[2]/total[3]),raw_ratio_low=rl,raw_ratio_high=rh,normalized_ratio_low=nl,normalized_ratio_high=nh,ratio_difference_low=dl,ratio_difference_high=dh,invalid_bootstrap=int((~valid).sum()))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--raw-forecasts',required=True);ap.add_argument('--raw-panel',required=True);ap.add_argument('--normalized-forecasts',default='experiments/E022-extra-analysis-fixed/results/case-forecasts.csv.gz');ap.add_argument('--out',required=True);args=ap.parse_args();out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);cfg=load_config()
    raw=scored(ROOT/args.raw_forecasts,ROOT/args.raw_panel/'truth.csv',cfg);normal=scored(ROOT/args.normalized_forecasts,ROOT/'experiments/E007-prepare-inputs-fixed/truth.csv',cfg);rows=[];pairs=[]
    for variant in ['native','calibrated']:
        for reference in ['ensemble','ensemble_extended','rolling_best_classical']:
            for model in ['chronos_bolt_base','timesfm_2p5']:
                for age in cfg['source_age_weeks']:
                    p=paired(raw,model,reference,age,variant).merge(paired(normal,model,reference,age,variant),on=panel.KEY,suffixes=('_raw','_normalized'),validate='one_to_one')
                    for period in ['all_test','year2026']:
                        start=cfg['test_start'] if period=='all_test' else '2026-01-02'
                        if model=='timesfm_2p5':start=max(start,cfg['timesfm_interpretation_start'])
                        z=p[p.issue_date.between(start,cfg['test_end'])]
                        if z.empty:continue
                        for metric in ['wis','mae']:
                            for block in cfg['bootstrap_blocks']:
                                seed=int.from_bytes(hashlib.sha256(f"{cfg['seed']}|indicator|{variant}|{reference}|{model}|{age}|{period}|{metric}|{block}".encode()).digest()[:8],'little');stats=boot(z,metric,start,cfg,block,seed)
                                rows.append(dict(variant=variant,reference_model=reference,model=model,source_age_weeks=age,period=period,metric=metric,block_weeks=block,n_pairs=len(z),n_issue_weeks=z.issue_date.nunique(),**stats))
                        if period=='all_test':
                            cols=panel.KEY+[m+'_'+s+'_'+v for m in ['wis','mae'] for v in ['raw','normalized'] for s in ['candidate','reference']];save=z[cols].copy();save['variant']=variant;save['reference_model']=reference;save['model']=model;save['source_age_weeks']=age;pairs.append(save)
    pd.DataFrame(rows).to_csv(out/'matched-indicator-ratios.csv',index=False);pd.concat(pairs,ignore_index=True).to_csv(out/'matched-case-losses.csv.gz',index=False,compression={'method':'gzip','mtime':0});(out/'summary.json').write_text(json.dumps(dict(comparison_rows=len(rows),exploratory=True,matched_case_definitions=True,causal_normalization_effect_claimed=False,network_required=False,model_inference_required=False),indent=2)+'\n')

if __name__=='__main__':main()
