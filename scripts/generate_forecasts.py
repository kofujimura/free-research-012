"""Offline deterministic native forecasts. Save every success/failure and quantile."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,time,traceback,warnings
import numpy as np
from scipy.stats import norm
from record import ROOT,now
from prepare_inputs import load_config

def statistical(y,h,qs):
    from statsforecast.models import AutoARIMA,AutoETS
    z=norm.ppf(qs);scale=np.std(np.diff(y[-52:]),ddof=1) if len(y)>2 else 0.0
    spread=np.sqrt(np.arange(1,h+1))*scale
    naive=y[-1]+spread[:,None]*z[None,:]
    xx=np.arange(min(8,len(y)),dtype=float);slope=float(np.polyfit(xx,y[-len(xx):],1)[0])
    trend=(y[-1]+slope*np.cumsum(0.8**np.arange(1,h+1)))[:,None]+spread[:,None]*z[None,:]
    out={'naive':naive,'damped_trend':trend};errors=[]
    estimators={'autoarima':AutoARIMA(max_p=3,max_q=3,max_d=2,max_order=5,seasonal=False,season_length=1,stepwise=True,ic='aicc',approximation=False),'autoets':AutoETS(season_length=1,model='AZN',distribution='normal')}
    for name,model in estimators.items():
        try:
            f=model.forecast(y=y,h=h,level=[20,40,60,80])
            cols=[f['lo-80'],f['lo-60'],f['lo-40'],f['lo-20'],f['mean'],f['hi-20'],f['hi-40'],f['hi-60'],f['hi-80']]
            out[name]=np.stack(cols,axis=1)
        except Exception as ex:errors.append(dict(model=name,error=type(ex).__name__+': '+str(ex),traceback=traceback.format_exc()))
    if all(n in out for n in ['autoarima','autoets','damped_trend']):out['ensemble']=np.mean([out[n] for n in ['autoarima','autoets','damped_trend']],axis=0)
    return out,errors

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--engine',choices=['statistical','chronos','timesfm'],required=True);ap.add_argument('--batch-size',type=int,default=16);ap.add_argument('--start',type=int,default=0);ap.add_argument('--stop',type=int);ap.add_argument('--timesfm-max-context',type=int,choices=[128,256],default=128);args=ap.parse_args()
    cfg=load_config();np.random.seed(cfg['seed']);out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR'])
    inputs=json.loads((ROOT/args.inputs).read_text());items=sorted(inputs.items())[args.start:args.stop];qs=np.asarray(cfg['quantiles']);h=cfg['max_horizon']
    metadata=dict(engine=args.engine,input_file=args.inputs,input_sha256=hashlib.sha256((ROOT/args.inputs).read_bytes()).hexdigest(),seed=cfg['seed'],horizon=h,quantiles=qs.tolist(),start=args.start,stop=args.stop,started_at_utc=now(),models={},failures=0,successes=0,quantile_crossings=0,timesfm_max_context=args.timesfm_max_context if args.engine=='timesfm' else None)
    if args.engine=='timesfm' and any(len(ctx['log_values'])>args.timesfm_max_context for _,ctx in items):raise ValueError('A source context exceeds the explicit TimesFM context limit')
    if args.engine in ['chronos','timesfm']:
        import torch
        torch.set_num_threads(4);torch.manual_seed(cfg['seed']);torch.use_deterministic_algorithms(True)
        if args.engine=='chronos':
            from chronos import BaseChronosPipeline
            model=BaseChronosPipeline.from_pretrained(str(ROOT/'data/models/chronos-bolt-base'),device_map='cpu',dtype=torch.float32,local_files_only=True)
            metadata['models']={'chronos_bolt_base':'data/models/chronos-bolt-base'}
        else:
            import timesfm
            model=timesfm.TimesFM_2p5_200M_torch.from_pretrained(str(ROOT/'data/models/timesfm-2.5-200m-pytorch'),torch_compile=False,local_files_only=True,token=False)
            model.compile(timesfm.ForecastConfig(max_context=args.timesfm_max_context,max_horizon=128,normalize_inputs=True,use_continuous_quantile_head=True,force_flip_invariance=True,infer_is_positive=False,fix_quantile_crossing=True))
            metadata['models']={'timesfm_2p5':'data/models/timesfm-2.5-200m-pytorch'}
    with (out/'forecasts.jsonl').open('w') as f,(out/'failures.jsonl').open('w') as err:
        for first in range(0,len(items),args.batch_size):
            batch=items[first:first+args.batch_size];tick=time.monotonic()
            if args.engine=='statistical':
                grouped=[]
                for uid,ctx in batch:
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always');preds,errors=statistical(np.array(ctx['log_values'],dtype=np.float64),h,qs)
                    for error in errors:
                        err.write(json.dumps(dict(input_id=uid,**error))+'\n');metadata['failures']+=1
                    grouped.append((uid,preds,[str(w.message) for w in caught]))
            else:
                try:
                    ys=[np.asarray(ctx['log_values'],dtype=np.float32) for uid,ctx in batch]
                    if args.engine=='chronos':
                        raw=model.predict([torch.tensor(y) for y in ys],prediction_length=h).detach().cpu().numpy().transpose(0,2,1)
                        name='chronos_bolt_base'
                    else:
                        point,raw=model.forecast(horizon=h,inputs=ys);raw=raw[:,:,1:];name='timesfm_2p5'
                    if raw.shape!=(len(batch),h,len(qs)):raise ValueError('Unexpected quantile shape '+str(raw.shape))
                    grouped=[(uid,{name:raw[j]},[]) for j,(uid,ctx) in enumerate(batch)]
                except Exception as ex:
                    err.write(json.dumps(dict(input_ids=[uid for uid,_ in batch],model=args.engine,error=type(ex).__name__+': '+str(ex),traceback=traceback.format_exc()))+'\n');err.flush();metadata['failures']+=len(batch);grouped=[]
            for uid,preds,notices in grouped:
                for name,q in preds.items():
                    if not np.isfinite(q).all():
                        err.write(json.dumps(dict(input_id=uid,model=name,error='Nonfinite native forecast'))+'\n');metadata['failures']+=1;continue
                    crossings=int((np.diff(q,axis=1)<0).sum());metadata['quantile_crossings']+=crossings
                    f.write(json.dumps(dict(input_id=uid,model=name,quantiles=np.sort(q,axis=1).tolist(),crossings=crossings,warnings=notices),allow_nan=False,separators=(',',':'))+'\n');metadata['successes']+=1
            f.flush();err.flush()
            print(json.dumps(dict(done=min(first+args.batch_size,len(items)),total=len(items),batch_seconds=time.monotonic()-tick,successes=metadata['successes'],failures=metadata['failures'])),flush=True)
            (out/'generation-summary.json').write_text(json.dumps(metadata,indent=2)+'\n')
    metadata['ended_at_utc']=now();(out/'generation-summary.json').write_text(json.dumps(metadata,indent=2)+'\n')
    if metadata['failures']:raise SystemExit('Some forecasts failed; failures saved, do not treat as complete coverage')

if __name__=='__main__':main()
