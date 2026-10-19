"""Archive the official national AMELAG release history; no forecasts."""
from __future__ import annotations
import hashlib,io,json,os,pathlib,subprocess
import pandas as pd
from record import ROOT,now,append_json

REMOTE='https://github.com/robert-koch-institut/Abwassersurveillance_AMELAG'
FILE='amelag_aggregierte_kurve.tsv'
GIT=ROOT/'.cache/amelag.git'
OUT=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR'])
DEST=ROOT/'data/amelag/vintages'
DEST.mkdir(parents=True,exist_ok=True)

def git(*args):
    p=subprocess.run(['git','-c','core.commitGraph=false','-c','fetch.writeCommitGraph=false','--git-dir',str(GIT),*args],capture_output=True,timeout=90,check=False)
    if p.stderr:
        with (OUT/'git-stderr.txt').open('ab') as f:f.write(p.stderr)
    p.check_returncode()
    return p.stdout

def main():
    freeze=git('rev-parse','6586326').decode().strip()
    lines=git('log','--reverse','--format=%H|%cI',freeze,'--',FILE).decode().splitlines()
    archive=[];audit=[];seen_headers=set()
    for n,line in enumerate(lines):
        sha,stamp=line.split('|')
        path=DEST/(sha+'.tsv')
        if path.exists():
            raw=path.read_bytes()
            # A successfully archived blob is reused after the interrupted acquisition.
            expected=git('rev-parse',sha+':'+FILE).decode().strip()
            actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            if actual!=expected:raise ValueError('Archived blob does not match official Git object')
        else:
            raw=git('show',sha+':'+FILE);path.write_bytes(raw)
        item=dict(commit=sha,commit_time=stamp,retrieved_at_utc=now(),path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),url=REMOTE+'/blob/'+sha+'/'+FILE,license='CC BY 4.0; Robert Koch Institute and Umweltbundesamt',availability_proxy='Git committer timestamp, not independently observed public availability')
        archive.append(item)
        append_json('data/downloads.jsonl',dict(item,status='success',purpose='main actual-vintage archive',transport='official public Git'))
        frame=pd.read_csv(io.BytesIO(raw),sep='\t')
        head=tuple(frame.columns)
        seen_headers.add(head)
        if True:  # Method changes can occur without a column-header change.
            names=git('ls-tree','--name-only',sha).decode().splitlines()
            for name in ['Readme.en.md','Readme.md','LICENSE']:
                if name in names:
                    dp=ROOT/'data/amelag/docs'/sha/name
                    if dp.exists():doc=dp.read_bytes()
                    else:
                        doc=git('show',sha+':'+name);dp.parent.mkdir(parents=True,exist_ok=True);dp.write_bytes(doc)
                    append_json('data/downloads.jsonl',dict(url=REMOTE+'/blob/'+sha+'/'+name,path=str(dp.relative_to(ROOT)),retrieved_at_utc=now(),sha256=hashlib.sha256(doc).hexdigest(),bytes=len(doc),license='CC BY 4.0' if name!='LICENSE' else 'license text',status='success',purpose='schema transition documentation'))
        groupcols=[x for x in ['typ','normalisierung'] if x in frame]
        grouped=frame.groupby(groupcols,dropna=False) if groupcols else [(('ALL',),frame)]
        for key,g in grouped:
            keys=key if isinstance(key,tuple) else (key,)
            item2=dict(commit=sha,commit_time=stamp,columns='|'.join(frame.columns),rows=len(g),**dict(zip(groupcols,map(str,keys))))
            dates=pd.to_datetime(g['datum'],errors='coerce')
            item2.update(first_date=str(dates.min().date()),last_date=str(dates.max().date()),date_na=int(dates.isna().sum()),duplicate_dates=int(dates.duplicated().sum()),weekdays=','.join(map(str,sorted(dates.dt.dayofweek.dropna().unique()))))
            for col in ['viruslast','viruslast_normalisiert','n','anteil_bev']:
                if col in g:
                    vals=pd.to_numeric(g[col],errors='coerce')
                    item2.update({col+'_na':int(vals.isna().sum()),col+'_nonpositive':int((vals<=0).sum()),col+'_min':float(vals.min()) if vals.notna().any() else None,col+'_max':float(vals.max()) if vals.notna().any() else None})
            audit.append(item2)
        (OUT/'archive-index.json').write_text(json.dumps(dict(frozen_commit=freeze,records=archive),ensure_ascii=False,indent=2)+'\n')
        print(f'{n+1}/{len(lines)} {sha[:8]} rows={len(frame)}',flush=True)
    pd.DataFrame(audit).to_csv(OUT/'schema-audit.csv',index=False)
    summary=dict(frozen_commit=freeze,vintages=len(archive),distinct_headers=len(seen_headers),first_release=archive[0]['commit_time'],last_release=archive[-1]['commit_time'],archived_bytes=sum(x['bytes'] for x in archive),types=sorted(set(x.get('typ','ALL') for x in audit)))
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
