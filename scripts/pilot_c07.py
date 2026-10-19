"""Acquisition pilot only. No forecast accuracy comparison."""
import datetime as dt,json,os,pathlib,subprocess,sys,time
from record import ROOT,now,event
from fetch import fetch

out=ROOT/'experiments/pilot-c07';out.mkdir(parents=True,exist_ok=True)
started=now();clock=time.monotonic()
eid=event('pilot_started','C07: acquire public AMELAG aggregate snapshots, check dated revisions and local model feasibility.',['protocol/pilots.md'],candidate_id='C07')
repo=ROOT/'.cache/amelag.git';repo.parent.mkdir(parents=True,exist_ok=True)
with (out/'git.stdout.txt').open('w') as stdout,(out/'git.stderr.txt').open('w') as stderr:
    r=subprocess.run(['git','clone','--filter=blob:none','--bare','https://github.com/robert-koch-institut/Abwassersurveillance_AMELAG.git',str(repo)],stdout=stdout,stderr=stderr,timeout=300)
if r.returncode:raise SystemExit(r.returncode)
rawbase='https://raw.githubusercontent.com/robert-koch-institut/Abwassersurveillance_AMELAG/main/'
meta={}
for name in ('Readme.en.md','LICENSE','amelag_aggregierte_kurve.tsv'):
    meta[name]=fetch(rawbase+name,'data/pilot-c07/current-'+name,license_note='CC BY 4.0; Robert Koch Institute and Federal Environment Agency',purpose='C07 feasibility pilot',max_bytes=10_000_000)
records=[]
for cutoff in ('2024-12-20T00:00:00Z','2025-12-20T00:00:00Z'):
    cmd=['git','--git-dir',str(repo),'rev-list','-1','--before='+cutoff,'HEAD','--','amelag_aggregierte_kurve.tsv']
    sha=subprocess.check_output(cmd,text=True,timeout=30).strip()
    if not sha:continue
    cmd=['git','--git-dir',str(repo),'show',sha+':amelag_aggregierte_kurve.tsv']
    data=subprocess.check_output(cmd,timeout=120)
    p=out/f'{sha}-aggregate.tsv';p.write_bytes(data)
    date=subprocess.check_output(['git','--git-dir',str(repo),'show','-s','--format=%cI',sha],text=True,timeout=30).strip()
    records.append({'requested_cutoff':cutoff,'commit':sha,'commit_date':date,'path':str(p.relative_to(ROOT)),'bytes':len(data)})
import pandas as pd
current=pd.read_csv(ROOT/'data/pilot-c07/current-amelag_aggregierte_kurve.tsv',sep='\t')
summary={'started_at_utc':started,'ended_at_utc':now(),'elapsed_seconds':time.monotonic()-clock,'git_exit_code':r.returncode,'download_records':meta,'historical_snapshots':records,'rows_current':len(current),'columns_current':list(current.columns),'head_current':current.head(2).to_dict('records'),'note':'No accuracy comparison performed. Public WWTP/national aggregates; no individual records.'}
(out/'acquisition.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str)+'\n')
event('pilot_ended','C07 acquisition pilot completed; output records snapshot dates and schema.',['experiments/pilot-c07/acquisition.json'],related=[eid],candidate_id='C07')
print(json.dumps(summary,ensure_ascii=False,default=str))
