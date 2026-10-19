"""Archive only PHF Science's public national/regional wastewater CSV vintages."""
import gzip,hashlib,io,json,os,pathlib,subprocess
import pandas as pd
from record import ROOT,now,append_json

REMOTE='https://github.com/ESR-NZ/covid_in_wastewater.git'
FILES=['data/ww_national.csv','data/ww_regional.csv']

def main():
    out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);gitdir=ROOT/'.cache/nz-wastewater.git'
    def run(*args):
        p=subprocess.run(['git','-c','core.commitGraph=false','-c','fetch.writeCommitGraph=false','--git-dir',str(gitdir),*args],capture_output=True,timeout=90)
        if p.stderr:
            with (out/'git-stderr.txt').open('ab') as f:f.write(p.stderr)
        p.check_returncode();return p.stdout
    if not gitdir.exists():
        p=subprocess.run(['git','clone','--bare','--filter=blob:none','--no-tags',REMOTE,str(gitdir)],capture_output=True,timeout=90)
        (out/'clone-stdout.txt').write_bytes(p.stdout);(out/'clone-stderr.txt').write_bytes(p.stderr);p.check_returncode()
    start=json.loads((ROOT/'manifest.json').read_text())['start_at_utc']
    frozen=run('rev-list','-1','--before='+start,'HEAD').decode().strip()
    if not frozen:raise ValueError('No public commit before research start')
    lines=run('log','--reverse','--format=%H|%cI',frozen,'--',*FILES).decode().splitlines()
    if not lines:
        (out/'path-audit.txt').write_bytes(run('ls-tree','-r','--name-only',frozen,'data'))
        raise ValueError('Documented national/regional CSV paths absent from history; inspect saved path audit')
    dest=ROOT/'data/nz/vintages';dest.mkdir(parents=True,exist_ok=True);records=[];audits=[]
    for i,line in enumerate(lines):
        if int(subprocess.check_output(['du','-sk',str(ROOT)],text=True).split()[0])*1024>9*1024**3:raise SystemExit('Storage limit approaching')
        commit,stamp=line.split('|');files=[]
        for target in FILES:
            exists=run('ls-tree',commit,'--',target).decode().strip()
            if not exists:continue
            raw=run('show',commit+':'+target);compressed=gzip.compress(raw,mtime=0)
            short=pathlib.Path(target).name;p=dest/(commit+'-'+short+'.gz');p.write_bytes(compressed)
            f=dict(path=str(p.relative_to(ROOT)),url=REMOTE.removesuffix('.git')+'/blob/'+commit+'/'+target,source_path=target,retrieved_at_utc=now(),raw_sha256=hashlib.sha256(raw).hexdigest(),sha256=hashlib.sha256(compressed).hexdigest(),raw_bytes=len(raw),bytes=len(compressed),license='CC BY4.0; attribute as COVID-19 Data Repository by the New Zealand Institute for Public Health and Forensic Science Ltd',status='success',commit=commit,commit_time=stamp)
            append_json('data/downloads.jsonl',f);files.append(f)
            frame=pd.read_csv(io.BytesIO(raw));datecol='week_end_date'
            info=dict(commit=commit,commit_time=stamp,source_path=target,rows=len(frame),columns=list(frame.columns))
            if datecol in frame:
                dates=pd.to_datetime(frame[datecol],errors='coerce');info.update(first_date=str(dates.min()),last_date=str(dates.max()),weekdays=sorted(map(int,dates.dt.dayofweek.dropna().unique())))
            if 'Region' in frame:info['regions']=int(frame.Region.nunique())
            audits.append(info)
        records.append(dict(commit=commit,commit_time=stamp,files=files))
        (out/'archive-index.json').write_text(json.dumps(dict(frozen_commit=frozen,freeze_cutoff=start,records=records),indent=2)+'\n')
        (out/'schema-audit.json').write_text(json.dumps(audits,indent=2)+'\n')
        print(json.dumps(dict(done=i+1,total=len(lines),commit_time=stamp,files=len(files))),flush=True)
    for label,commit in [('first',records[0]['commit']),('frozen',frozen)]:
        raw=run('show',commit+':README.md');p=ROOT/'data/nz'/f'{label}-README.md';p.write_bytes(raw)
        append_json('data/downloads.jsonl',dict(path=str(p.relative_to(ROOT)),url=REMOTE.removesuffix('.git')+'/blob/'+commit+'/README.md',retrieved_at_utc=now(),sha256=hashlib.sha256(raw).hexdigest(),license='repository terms of use text',status='success'))
    summary=dict(frozen_commit=frozen,releases=len(records),csv_files=sum(len(r['files']) for r in records),first_release=records[0]['commit_time'],last_release=records[-1]['commit_time'],raw_bytes=sum(f['raw_bytes'] for r in records for f in r['files']),compressed_bytes=sum(f['bytes'] for r in records for f in r['files']))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
