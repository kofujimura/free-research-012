"""Common-period, jointly resampled max-log-deviation sensitivity."""
import argparse,hashlib,json,math,pathlib
import numpy as np
import pandas as pd
from prepare_inputs import ROOT
from analyze_freshness_interaction import KEY,ratio

def read(paths):
    parts=[];wanted=set(KEY+['truth_lag','model','source_age_weeks','input_mode','variant','known_target','unit_level','last_date','wis'])
    for p in paths:
        d=pd.read_csv(ROOT/p,usecols=lambda c:c in wanted,dtype={'truth_lag':str},float_precision='round_trip');d=d[(d.truth_lag=='56')&(d.input_mode=='actual')&(d.variant=='native')&(~d.known_target)]
        if 'unit_id' not in d:d['unit_id']=d.pathogen;d['unit_level']='national'
        parts.append(d)
    data=pd.concat(parts,ignore_index=True);assert not data.duplicated(KEY+['model','source_age_weeks']).any();return data

def estimates(v):
    fo,ff,ro,rf=np.moveaxis(v,-1,0)
    return np.stack([ratio(ratio(fo,ff),ratio(ro,rf)),ratio(fo,rf)],axis=-1)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--datasets',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();definitions=json.loads((ROOT/args.datasets).read_text());out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);results=[];families=[];members=[]
    for country in ['Germany','NZ']:
        config=[d for d in definitions if d['country']==country];start='2025-10-03' if country=='Germany' else '2025-10-06';end='2026-08-07' if country=='Germany' else '2026-08-03';frequency='W-FRI' if country=='Germany' else 'W-MON';weeks=pd.date_range(start,end,freq=frequency).strftime('%Y-%m-%d');matrices=[];metadata=[]
        for definition in config:
            data=read(definition['scores'])
            def frame(model,age,suffix):
                d=data[(data.model==model)&(data.source_age_weeks==age)][KEY+['unit_level','last_date','wis']];return d.rename(columns={c:c+'_'+suffix for c in d if c not in KEY})
            for model in ['chronos_bolt_base','timesfm_2p5']:
                for ref in ['ensemble','ensemble_extended']:
                    for age in [1,2]:
                        p=frame(model,age,'fo').merge(frame(model,0,'ff'),on=KEY,validate='one_to_one').merge(frame(ref,age,'ro'),on=KEY,validate='one_to_one').merge(frame(ref,0,'rf'),on=KEY,validate='one_to_one');p=p[p.issue_date.between(start,end)&(p.last_date_fo<p.last_date_ff)]
                        for level,g in p.groupby('unit_level_fo',sort=True):
                            m=dict(country=country,dataset=definition['name'],unit_level=level,model=model,reference_model=ref,source_age_weeks=age,analysis_start=start,analysis_end=end,n_pairs=len(g),n_units=g.unit_id.nunique(),n_issue_weeks=g.issue_date.nunique());metadata.append(m);group=g.groupby('issue_date')[[f'wis_{x}' for x in ['fo','ff','ro','rf']]].sum().reindex(weeks,fill_value=0);assert int(g.groupby('issue_date').size().reindex(weeks,fill_value=0).sum())==len(g);matrices.append(group.to_numpy());members.append(m)
        assert len(metadata)==16,(country,len(metadata));weekly=np.stack(matrices,axis=1);point=estimates(weekly.sum(axis=0));assert np.isfinite(point).all() and (point>0).all();logs=np.log(point)
        for block in [4,8,12]:
            seed=int.from_bytes(hashlib.sha256(f'12012|joint-comparison-sensitivity|{country}|{block}'.encode()).digest()[:8],'little');rng=np.random.default_rng(seed);length=min(block,len(weeks));ix=(rng.integers(0,len(weeks)-length+1,size=(10000,math.ceil(len(weeks)/length)))[:,:,None]+np.arange(length)).reshape(10000,-1)[:,:len(weeks)];counts=np.zeros((len(ix),len(weeks)),dtype=np.int32);np.add.at(counts,(np.repeat(np.arange(len(ix)),len(weeks)),ix.ravel()),1);assert (counts.sum(axis=1)==len(weeks)).all();draw=estimates((counts@weekly.reshape(len(weeks),-1)).reshape(10000,len(metadata),4));valid=(np.isfinite(draw)&(draw>0)).all(axis=(1,2));assert valid.any();logdraw=np.log(draw[valid]);critical=float(np.quantile(np.abs(logdraw-logs).max(axis=(1,2)),.95));nominal=np.quantile(draw[valid],[.025,.975],axis=0);simlo=np.exp(logs-critical);simhi=np.exp(logs+critical);nomcount=simcount=0
            for j,m in enumerate(metadata):
                for k,name in enumerate(['ratio_of_freshness_ratios','replacement_ratio']):
                    lo=float(nominal[0,j,k]);hi=float(nominal[1,j,k]);sl=float(simlo[j,k]);sh=float(simhi[j,k]);nomoutside=lo>1 or hi<1;simoutside=sl>1 or sh<1;nomcount+=nomoutside;simcount+=simoutside;results.append(dict(**m,statistic=name,block_weeks=block,value=float(point[j,k]),nominal_low=lo,nominal_high=hi,simultaneous_low=sl,simultaneous_high=sh,nominal_excludes_one=nomoutside,simultaneous_excludes_one=simoutside,family_statistics=int(point.size),valid_bootstrap=int(valid.sum()),invalid_bootstrap=int((~valid).sum()),critical_max_absolute_log_deviation=critical))
            families.append(dict(country=country,analysis_start=start,analysis_end=end,block_weeks=block,comparisons=len(metadata),statistics=int(point.size),bootstrap_repetitions=10000,valid_bootstrap=int(valid.sum()),invalid_bootstrap=int((~valid).sum()),nominal_intervals_excluding_one=int(nomcount),simultaneous_intervals_excluding_one=int(simcount),critical_max_absolute_log_deviation=critical))
    pd.DataFrame(results).to_csv(out/'comparisons.csv',index=False);pd.DataFrame(families).to_csv(out/'family-summary.csv',index=False);(out/'comparison-members.json').write_text(json.dumps(members,indent=2)+'\n');result=dict(comparison_rows=len(results),families=len(families),exploratory=True,common_post_publication_period=True,strict_familywise_coverage_guarantee_claimed=False,independent_validation=False);(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
