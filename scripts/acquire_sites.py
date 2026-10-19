"""Official public site measurements: lossless compressed archive and schema counts."""
import argparse,gzip,hashlib,io,json,os,pathlib,subprocess
import pandas as pd
from record import ROOT,now,append_json

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--all-releases',action='store_true');args=ap.parse_args()
    out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);ix=json.loads((ROOT/'experiments/E004-vintage-audit-complete/archive-index.json').read_text())
    recs=ix['records']
    if args.all_releases:recs=[r for r in recs if r['commit_time']>='2024-12-18']
    else:recs=[r for r in recs if r['commit'].startswith(('6f630bf','6586326'))]
    dest=ROOT/'data/amelag/sites';dest.mkdir(parents=True,exist_ok=True);records=[];audit=[]
    for i,r in enumerate(recs):
        storage=int(subprocess.check_output(['du','-sk',str(ROOT)],text=True).split()[0])*1024
        if storage>9*1024**3:raise SystemExit('Storage approaching limit; stop further acquisition')
        sha=r['commit'];p=dest/(sha+'.tsv.gz');filename='amelag_einzelstandorte.tsv'
        command=['git','-c','core.commitGraph=false','-c','fetch.writeCommitGraph=false','--git-dir',str(ROOT/'.cache/amelag.git'),'show',sha+':'+filename]
        if p.exists():raw=gzip.decompress(p.read_bytes());transport='reuse saved compressed raw data'
        else:
            proc=subprocess.run(command,capture_output=True,timeout=90)
            if proc.stderr:
                with (out/'git-stderr.txt').open('ab') as f:f.write(proc.stderr)
            proc.check_returncode();raw=proc.stdout;transport='official public Git'
            if len(raw)>200_000_000:raise ValueError('Unexpectedly large raw file; do not store')
            p.write_bytes(gzip.compress(raw,mtime=0))
        gitblob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        wanted=subprocess.check_output(['git','-c','core.commitGraph=false','--git-dir',str(ROOT/'.cache/amelag.git'),'rev-parse',sha+':'+filename],text=True).strip()
        if gitblob!=wanted:raise ValueError('Archived measurements differ from official Git blob')
        compressed=p.read_bytes()
        item=dict(commit=sha,commit_time=r['commit_time'],path=str(p.relative_to(ROOT)),url='https://github.com/robert-koch-institut/Abwassersurveillance_AMELAG/blob/'+sha+'/'+filename,retrieved_at_utc=now(),raw_sha256=hashlib.sha256(raw).hexdigest(),sha256=hashlib.sha256(compressed).hexdigest(),raw_bytes=len(raw),compressed_bytes=len(compressed),git_blob=gitblob,license='CC BY4.0; Robert Koch Institute and Umweltbundesamt',status='success',transport=transport)
        records.append(item);append_json('data/downloads.jsonl',item)
        d=pd.read_csv(io.BytesIO(raw),sep='\t',low_memory=False)
        info=dict(commit=sha,commit_time=r['commit_time'],rows=len(d),columns=list(d.columns),types=sorted(map(str,d.typ.dropna().unique())) if 'typ' in d else ['SARS-CoV-2'],sites=int(d.standort.nunique()),min_date=str(pd.to_datetime(d.datum).min()),max_date=str(pd.to_datetime(d.datum).max()))
        if 'einwohner' in d:
            v=pd.to_numeric(d.einwohner,errors='coerce');info.update(population_missing=int(v.isna().sum()),population_min=float(v.min()),population_max=float(v.max()))
        audit.append(info)
        (out/'archive-index.json').write_text(json.dumps(dict(records=records),indent=2)+'\n')
        (out/'schema-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(info,ensure_ascii=False),flush=True)
    summary=dict(releases=len(records),raw_bytes=sum(x['raw_bytes'] for x in records),compressed_bytes=sum(x['compressed_bytes'] for x in records),data_rows=sum(x['rows'] for x in audit))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
