"""Create or verify a file hash inventory, without self-referential claims."""
import argparse,datetime as dt,hashlib,json,pathlib,subprocess

ROOT=pathlib.Path(__file__).resolve().parents[1]
EXCLUDED_PARTS={'.git','.venv','.cache','.verify-work','__pycache__'}

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['create','verify']);ap.add_argument('--manifest',default='SHA256SUMS.json');ap.add_argument('--tracked-only',action='store_true');ap.add_argument('--out');args=ap.parse_args();path=ROOT/args.manifest
    if args.action=='create':
        tracked=set(subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0'));entries=[]
        for p in sorted(ROOT.rglob('*')):
            rel=p.relative_to(ROOT)
            if any(x in EXCLUDED_PARTS for x in rel.parts) or p.is_symlink() or not p.is_file():continue
            if p.suffix=='.pyc' or p.name.startswith('SHA256SUMS') or p.name in ['.active.json','.runner-lock']:continue
            entries.append(dict(path=str(rel),bytes=p.stat().st_size,sha256=digest(p),git_tracked=str(rel) in tracked))
        result=dict(created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),algorithm='SHA-256',files=entries,excluded_directory_names=sorted(EXCLUDED_PARTS),excluded_files=['all SHA256SUMS* inventories/self-check reports (including submission copy)','*.pyc','.active.json','.runner-lock','symbolic links'],meaning='Integrity inventory only; does not prove independent origin, immutability, or chronology.')
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(files=len(entries),bytes=sum(x['bytes'] for x in entries))))
    else:
        data=json.loads(path.read_text());checked=0;skipped=[];errors=[]
        for r in data['files']:
            if args.tracked_only and not r['git_tracked']:skipped.append(r['path']);continue
            p=ROOT/r['path']
            if not p.is_file():errors.append(dict(path=r['path'],error='missing'));continue
            if p.stat().st_size!=r['bytes'] or digest(p)!=r['sha256']:errors.append(dict(path=r['path'],error='hash_or_size_mismatch'))
            checked+=1
        result=dict(checked=checked,skipped=skipped,errors=errors,passed=not errors,tracked_only=args.tracked_only)
        if args.out:pathlib.Path(args.out).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(checked=checked,skipped=len(skipped),errors=len(errors),passed=not errors)));raise SystemExit(0 if not errors else 1)

if __name__=='__main__':main()
