"""Check public ensemble output metadata without running global weather models."""
import json,signal,time,hashlib,requests
from record import ROOT,now,event

signal.alarm(900)
out=ROOT/'experiments/pilot-c13';out.mkdir(parents=True,exist_ok=True)
started=now();clock=time.monotonic();eid=event('pilot_started','C13: inspect public ensemble metadata and licenses. Same capability also available from NeuralGCM (2024); GenCast outputs not yet located.',['protocol/pilots.md'],candidate_id='C13')
base='https://storage.googleapis.com/weatherbench2/datasets/neuralgcm_ens/'
results=[]
for name in ('LICENSE','2020-240x121_equiangular_with_poles_conservative.zarr/.zmetadata','2020-64x32_equiangular_conservative.zarr/.zmetadata'):
    url=base+name
    try:
        r=requests.get(url,timeout=45)
        item={'url':url,'observed_at_utc':now(),'http_status':r.status_code,'bytes':len(r.content)}
        if r.status_code==200:
            fn='license.txt' if name=='LICENSE' else name.split('/')[0]+'-metadata.json'
            (out/fn).write_bytes(r.content);item.update(path=str((out/fn).relative_to(ROOT)),sha256=hashlib.sha256(r.content).hexdigest())
            if name.endswith('.zmetadata'):
                meta=r.json().get('metadata',{})
                arrays={k:v for k,v in meta.items() if k.endswith('/.zarray')}
                item['arrays']={k:{'shape':v.get('shape'),'chunks':v.get('chunks'),'dtype':v.get('dtype')} for k,v in arrays.items() if any(x in k for x in ['2m_temperature','time','member','prediction_timedelta','ensemble'])}
        results.append(item)
    except Exception as e:results.append({'url':url,'error':f'{type(e).__name__}: {e}'})
    time.sleep(1)
summary={'started_at_utc':started,'ended_at_utc':now(),'elapsed_seconds':time.monotonic()-clock,'results':results,'note':'No forecasting or impact analysis. GenCast precomputed output not confirmed; related 2024 NeuralGCM output considered within same capability.'}
(out/'acquisition.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
event('pilot_ended','C13 public ensemble metadata pilot ended; no climate-impact outcome evaluated.',['experiments/pilot-c13/acquisition.json'],related=[eid],candidate_id='C13')
print(json.dumps(summary,ensure_ascii=False))
