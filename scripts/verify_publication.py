"""Verify final presentation against freshly recalculated tables after editorial edits."""
import argparse,hashlib,json,pathlib,subprocess,sys
from record import ROOT,now

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();out=pathlib.Path(args.out).resolve();assert out!=ROOT;out.mkdir(parents=True,exist_ok=False)
    commands=[['scripts/render_paper.py','--manifest',args.manifest,'--out',str(out)],['scripts/plot_results.py','--manifest',args.manifest,'--out',str(out/'figures')],['scripts/verify_claims.py','--results-manifest',args.manifest,'--out',str(out/'claims.json')]]
    for command in commands:subprocess.run([sys.executable,*command],cwd=ROOT,check=True,timeout=120)
    files=[]
    for rel in ['paper.md',*[f'figures/{name}.{ext}' for name in ['national-model-information','generalization-one-week'] for ext in ['png','svg']]]:
        match=digest(ROOT/rel)==digest(out/rel);assert match,rel;files.append(dict(path=rel,sha256=digest(out/rel),bytes_match=True))
    checks=json.loads((out/'claims.json').read_text());assert checks['all_registered_values_match'];result=dict(observed_at_utc=now(),status='completed',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),analysis_manifest=args.manifest,scope='Presentation-only regenerated from E145 recalculated analysis tables; numerical algorithms and expected tables unchanged',files=files,claims=checks['claims'],evidence_rows=len(checks['checks']),new_prediction_inference=False,new_model_fitting=False,independent_reproduction=False);(out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
