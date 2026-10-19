# Retrospective copy of the executed inline command. Do not run in-place: would overwrite the pilot.
import os,pathlib,time,json,sys
p=pathlib.Path.cwd();os.environ['HF_HOME']=str(p/'.cache/huggingface');os.environ['XDG_CACHE_HOME']=str(p/'.cache');os.environ['HF_HUB_DISABLE_TELEMETRY']='1';os.environ['HF_HUB_DISABLE_XET']='1'
sys.path.insert(0,str(p/'scripts'))
from record import now,event
started=now();tick=time.monotonic()
from huggingface_hub import snapshot_download
local=snapshot_download('amazon/chronos-bolt-tiny',local_dir=p/'data/models/chronos-bolt-tiny',allow_patterns=['*.json','*.safetensors','README.md','LICENSE'],max_workers=2,token=False)
import torch,pandas as pd,numpy as np
from chronos import BaseChronosPipeline
torch.set_num_threads(4)
df=pd.read_csv(p/'data/pilot-c07/current-amelag_aggregierte_kurve.tsv',sep='\t')
series=df[df.typ=='SARS-CoV-2'].sort_values('datum')['viruslast_normalisiert'].dropna().tail(64).to_numpy(dtype='float32')
if not len(series):
 series=df.sort_values('datum')['viruslast_normalisiert'].dropna().tail(64).to_numpy(dtype='float32')
pipeline=BaseChronosPipeline.from_pretrained(local,device_map='cpu')
t0=time.monotonic();pred=pipeline.predict(torch.tensor(series),prediction_length=4)
np.save(p/'experiments/pilot-c07/model-output.npy',pred.detach().cpu().numpy())
r={'started_at_utc':started,'ended_at_utc':now(),'elapsed_seconds':time.monotonic()-tick,'inference_seconds':time.monotonic()-t0,'series_length':len(series),'prediction_shape':list(pred.shape),'model':'amazon/chronos-bolt-tiny','local_path':'data/models/chronos-bolt-tiny','device':'cpu','license':'Apache-2.0','note':'Feasibility only. No held-out accuracy compared.'}
(p/'experiments/pilot-c07/model-check.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
event('pilot_model_checked','Local Chronos-Bolt tiny produced quantile forecasts on a short public aggregate series.',['experiments/pilot-c07/model-check.json'],candidate_id='C07')
