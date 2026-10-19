"""Download two public Apache-licensed checkpoints; no hosted inference."""
import hashlib,json,os,pathlib
from huggingface_hub import HfApi,snapshot_download
from record import ROOT,now,append_json

out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR'])
api=HfApi(token=False)
records=[]
for repo,folder in [('amazon/chronos-bolt-base','chronos-bolt-base'),('google/timesfm-2.5-200m-pytorch','timesfm-2.5-200m-pytorch')]:
    info=api.model_info(repo,token=False)
    revision=info.sha
    path=ROOT/'data/models'/folder
    snapshot_download(repo_id=repo,revision=revision,local_dir=path,token=False,max_workers=2,allow_patterns=['README.md','LICENSE','config.json','model.safetensors','*.safetensors.index.json'])
    files=[]
    for p in sorted(path.iterdir()):
        if not p.is_file():continue
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        item=dict(url=f'https://huggingface.co/{repo}/resolve/{revision}/{p.name}',path=str(p.relative_to(ROOT)),retrieved_at_utc=now(),sha256=digest,bytes=p.stat().st_size,license='Apache-2.0 (official model card)',purpose='local public model weights and metadata',status='success',repository=repo,revision=revision)
        append_json('data/downloads.jsonl',item);files.append(item)
    records.append(dict(repository=repo,revision=revision,files=files,git_exclusion='Large pretrained weights excluded from Git; included in final SHA list and available via exact revision. Stored forecasts suffice for API/model-free analysis.'))
    (out/'models.json').write_text(json.dumps(records,indent=2)+'\n')
    print(repo,revision,[(p.name,p.stat().st_size) for p in path.iterdir() if p.is_file()],flush=True)
