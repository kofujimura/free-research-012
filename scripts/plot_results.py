"""Publication plots generated exclusively from saved comparison tables."""
import argparse,json,pathlib,os
os.environ.setdefault('MPLCONFIGDIR',str(pathlib.Path(__file__).resolve().parents[1]/'.cache/matplotlib'))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from prepare_inputs import ROOT

COLORS={'chronos_bolt_base':'#13757d','timesfm_2p5':'#b64c2f'}
NAMES={'chronos_bolt_base':'Chronos-Bolt','timesfm_2p5':'TimesFM 2.5'}

def read(folder):return pd.read_csv(folder/'comparisons.csv',dtype={'truth_lag':str})
def choose(d,model,reference='ensemble',age=None,stratum='all'):
    mask=(d.truth_lag=='56')&(d.variant=='native')&(d.period=='all_test')&(d.stratum==stratum)&(d.metric=='wis')&(d.block_weeks==8)&(d.model==model)
    if 'reference_model' in d:mask&=d.reference_model==reference
    if age is not None:mask&=d.source_age_weeks==age
    return d[mask].sort_values('source_age_weeks')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();mapping=json.loads(pathlib.Path(args.manifest).read_text());paths={k:ROOT/v if not pathlib.Path(v).is_absolute() else pathlib.Path(v) for k,v in mapping.items()};out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','svg.hashsalt':'free-research-012'})
    primary=read(paths['primary']);extended=read(paths['extended']);fig,axes=plt.subplots(1,3,figsize=(11,3.5),sharey=True)
    for ax,(d,ref,title) in zip(axes,[(primary,'ensemble','Preplanned: fixed 3'),(extended,'ensemble_extended','Exploratory: fixed 6'),(extended,'rolling_best_classical','Exploratory: past selection')]):
        for i,model in enumerate(COLORS):
            g=choose(d,model,ref);x=g.source_age_weeks.to_numpy()+(i-.5)*.04;y=g.ratio.to_numpy()
            ax.plot(x,y,'o-',color=COLORS[model],label=NAMES[model]);ax.vlines(x,g.ratio_low,g.ratio_high,color=COLORS[model])
        
        if ref=='ensemble':
            z=choose(primary,'ensemble');ax.plot(z.source_age_weeks,z.ratio,'s--',color='#555555',label='Fixed 3 using earlier input');ax.vlines(z.source_age_weeks,z.ratio_low,z.ratio_high,color='#555555')
        ax.axhline(1,color='.4',ls='--',lw=1);ax.set_xticks([0,1,2]);ax.set_xlabel('Public-information cutoff age (weeks)');ax.set_title(title);ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('Mean WIS / latest-input classical reference');axes[0].legend(frameon=False,fontsize=7);axes[-1].legend(frameon=False,fontsize=8);fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(out/('national-model-information.'+ext),dpi=180,bbox_inches='tight',metadata={'Date':None} if ext=='svg' else None)
    plt.close(fig)
    groups=[('Germany national',primary,'all','ensemble'),('Germany national',extended,'all','ensemble_extended'),('Germany national',extended,'all','rolling_best_classical')]
    for key,title,levels in [('site','Germany sites',['site']),('nz','New Zealand',['national','regional'])]:
        if key in paths:
            d=read(paths[key])
            for level in levels:
                for ref in ['ensemble','ensemble_extended','rolling_best_classical']:groups.append((title+' / '+level,d,'level:'+level,ref))
    fig,ax=plt.subplots(figsize=(9,max(4,.46*len(groups))))
    short={'ensemble':'fixed3','ensemble_extended':'fixed6','rolling_best_classical':'past selection'}
    for row,(title,d,stratum,reference) in enumerate(groups):
        for i,model in enumerate(COLORS):
            g=choose(d,model,reference,1,stratum)
            if len(g)!=1:raise ValueError('Plot panel comparison incomplete')
            r=g.iloc[0];y=row+(i-.5)*.18;ax.plot(r.ratio,y,'o',color=COLORS[model],label=NAMES[model] if row==0 else None);ax.hlines(y,r.ratio_low,r.ratio_high,color=COLORS[model])
    ax.set_yticks(range(len(groups)),[title+' / '+short[ref] for title,_,_,ref in groups]);ax.invert_yaxis();ax.axvline(1,color='.4',ls='--');ax.set_xlabel('WIS: model using 1-week-earlier public input / latest-input reference');ax.legend(frameon=False);ax.grid(axis='x',alpha=.2);fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(out/('generalization-one-week.'+ext),dpi=180,bbox_inches='tight',metadata={'Date':None} if ext=='svg' else None)
    plt.close(fig)
    (out/'figure-provenance.json').write_text(json.dumps(dict(input_analysis_manifest=mapping,source_files={k:str(v/'comparisons.csv') for k,v in paths.items() if (v/'comparisons.csv').exists()},plots=['national-model-information','generalization-one-week'],numbers_are_not_hand_entered=True),indent=2)+'\n')
    print(json.dumps(dict(out=str(out),figures=2)))

if __name__=='__main__':main()
