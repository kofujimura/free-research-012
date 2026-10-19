"""Prespecified exploratory seasonal/classical competitors for frozen inputs."""
import argparse,json,os,pathlib,time,traceback,warnings
import numpy as np
import pandas as pd
from scipy.stats import norm
from statsforecast.models import AutoARIMA,AutoTheta
from prepare_inputs import ROOT,load_config

def quantiles(f):
    return np.stack([f['lo-80'],f['lo-60'],f['lo-40'],f['lo-20'],f['mean'],f['hi-20'],f['hi-40'],f['hi-60'],f['hi-80']],axis=1)

def arima(d=None):return AutoARIMA(d=d,max_p=3,max_q=3,max_d=2,max_order=5,seasonal=False,season_length=1,stepwise=True,ic='aicc',approximation=False)

def fourier(days,k):
    if not k:return None
    return np.stack([fun(2*np.pi*j*days/365.2425) for j in range(1,k+1) for fun in [np.sin,np.cos]],axis=1)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);args=ap.parse_args()
    out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);cfg=load_config();np.random.seed(cfg['seed']);h=cfg['max_horizon'];qs=cfg['quantiles'];inputs=json.loads((ROOT/args.inputs).read_text())
    success=0;failed=0
    with (out/'forecasts.jsonl').open('w') as output,(out/'failures.jsonl').open('w') as errors,(out/'selection.jsonl').open('w') as selections:
        for i,(uid,ctx) in enumerate(sorted(inputs.items())):
            y=np.asarray(ctx['log_values'],dtype=float);preds={}
            try:
                m=52 if len(y)>=104 else 1
                f=AutoTheta(season_length=m,decomposition_type='additive',distribution='normal').forecast(y=y,h=h,level=[20,40,60,80])
                preds['autotheta']=quantiles(f)
            except Exception as ex:errors.write(json.dumps(dict(input_id=uid,model='autotheta',error=str(ex),traceback=traceback.format_exc()))+'\n');failed+=1
            if len(y)>=52:
                point=y[len(y)-52+np.arange(h)%52]
                annual=np.diff(np.stack([y[52:],y[:-52]]),axis=0).ravel() if len(y)>52 else np.array([])
                sigma=float(np.std(annual,ddof=1)) if len(annual)>=3 else float(np.std(np.diff(y[-52:]),ddof=1))
                spread=np.sqrt(np.ceil(np.arange(1,h+1)/52))*sigma if len(annual)>=3 else np.sqrt(np.arange(1,h+1))*sigma
            else:
                point=np.repeat(y[-1],h);spread=np.sqrt(np.arange(1,h+1))*np.std(np.diff(y[-52:]),ddof=1)
            preds['seasonal_naive']=point[:,None]+spread[:,None]*norm.ppf(qs)[None,:]
            try:
                days=np.asarray(ctx['dates'],dtype='datetime64[D]').astype(np.int64).astype(float);future=days[-1]+7*np.arange(1,h+1)
                k0=arima().fit(y=y);d=int(k0.model_['arma'][5]);options=[(float(k0.model_['aicc']),0,k0)]
                details=[dict(k=0,aicc=float(k0.model_['aicc']),common_d=d)]
                # Keep differencing fixed: AICc values with different d are not comparable.
                if len(y)>=78:
                    for k in [1,2,3]:
                        try:
                            model=arima(d=d).fit(y=y,X=fourier(days,k));score=float(model.model_['aicc'])
                            options.append((score,k,model));details.append(dict(k=k,aicc=score,common_d=d))
                        except Exception as ex:details.append(dict(k=k,error=str(ex)))
                score,k,chosen=min(options,key=lambda x:(x[0],x[1]))
                preds['harmonic_arima']=quantiles(chosen.predict(h=h,X=fourier(future,k),level=[20,40,60,80]))
                selections.write(json.dumps(dict(input_id=uid,chosen_k=k,common_d=d,candidates=details),allow_nan=False)+'\n')
            except Exception as ex:errors.write(json.dumps(dict(input_id=uid,model='harmonic_arima',error=str(ex),traceback=traceback.format_exc()))+'\n');failed+=1
            for name,q in preds.items():
                if not np.isfinite(q).all():errors.write(json.dumps(dict(input_id=uid,model=name,error='Nonfinite quantiles'))+'\n');failed+=1;continue
                output.write(json.dumps(dict(input_id=uid,model=name,quantiles=np.sort(q,axis=1).tolist(),crossings=int((np.diff(q,axis=1)<0).sum())),separators=(',',':'),allow_nan=False)+'\n');success+=1
            output.flush();errors.flush();selections.flush()
            if (i+1)%16==0:print(json.dumps(dict(done=i+1,total=len(inputs),successes=success,failures=failed)),flush=True)
    summary=dict(inputs=len(inputs),successes=success,failures=failed,seed=cfg['seed'],common_d_for_fourier_aicc=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
    if failed:raise SystemExit('Some extra forecasts failed; preserve partial outputs')

if __name__=='__main__':main()
