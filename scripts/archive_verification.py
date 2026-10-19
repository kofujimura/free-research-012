"""Archive an actually completed offline replay; never turn a failure into success."""
import argparse,hashlib,json,pathlib,shutil,subprocess
from record import ROOT,now,event

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--inventory',required=True);ap.add_argument('--experiment',required=True);ap.add_argument('--archive',required=True);args=ap.parse_args();out=ROOT/args.output;archive=ROOT/args.archive;v=json.loads((out/'verification-run.json').read_text());comparison=json.loads((out/'expected-comparison.json').read_text());claims=json.loads((out/'claims/results.json').read_text());run=json.loads((ROOT/'experiments'/args.experiment/'run.json').read_text());assert run['status']=='completed' and v['status']=='completed';assert all(s['status']=='completed' for s in v['steps']);assert len(v['steps'])==43 and comparison['passed'] and len(comparison['checks'])==64;assert claims['all_registered_values_match'];inventory=json.loads((ROOT/args.inventory).read_text());source=pathlib.Path(inventory['source_checkout']);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==inventory['source_commit']==v['source_commit'];assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=source,text=True).strip();errors=[]
    for item in inventory['files']:
        if digest(source/item['path'])!=item['sha256']:errors.append(item['path'])
    assert not errors,errors;archive.mkdir(parents=True,exist_ok=False)
    for stage in v['steps']:
        child=archive/stage['name'];child.mkdir()
        for filename in ['replay-stdout.txt','replay-stderr.txt']:shutil.copy2(out/stage['name']/filename,child/filename)
    for path in [*out.rglob('*.json'),*out.rglob('*.jsonl')]:
        rel=path.relative_to(out)
        if '.cache' in rel.parts:continue
        target=archive/'json'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    shutil.copy2(out/'paper.md',archive/'paper.md');shutil.copy2(out/'verification-run.json',archive/'verification-run.json');shutil.copy2(out/'expected-comparison.json',archive/'expected-comparison.json')
    result=dict(observed_at_utc=now(),status='completed',successful_experiment=args.experiment,successful_source_commit=v['source_commit'],stages=len(v['steps']),tables=len(comparison['checks']),table_rows=sum(c['rows'] for c in comparison['checks']),max_absolute_numeric_difference=max(c['max_absolute_numeric_difference'] for c in comparison['checks']),relative_tolerance=comparison['comparison_relative_tolerance'],absolute_tolerance=comparison['comparison_absolute_tolerance'],claims=claims['claims'],claim_evidence_rows=len(claims['checks']),elapsed_seconds=v['elapsed_seconds'],source_input_files_checked=len(inventory['files']),source_inputs_unchanged=True,source_tracked_edits_after=False,full_not_quick=not v['quick'],first_attempt_status='failed',first_attempt_reason='Only dataset traversal order in two quality tables; failure and all outputs preserved',first_attempt_records='review/verification-attempt-1',successful_records=args.archive,independent_reproduction=False,existing_dependency_environment_reused=True,git_objects_shared=True,first_duplicate_outputs_shared_only_after_computation=True,api_required=False,network_required=False,manuscript_bytes_match_saved_analysis_render=digest(ROOT/'paper.md')==digest(out/'paper.md'))
    (ROOT/'review/verification-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');event('offline_verification_completed','Fresh full retry completed all43 stages; strict64-table and claim checks passed; selected source inputs unchanged. Failed first attempt retained.',['review/verification-result.json',args.archive],source_commit=v['source_commit'],tables=result['tables'],table_rows=result['table_rows']);print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
