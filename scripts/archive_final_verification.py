"""Preserve actual post-review replay proof; keep the initial proof unchanged."""
import argparse,hashlib,json,pathlib,shutil,subprocess
from record import ROOT,now,event

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while x:=f.read(1048576):h.update(x)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--inventory',required=True);ap.add_argument('--experiment',required=True);ap.add_argument('--archive',default='review/final-verification');args=ap.parse_args();out=ROOT/args.output;archive=ROOT/args.archive
    v=json.loads((out/'verification-run.json').read_text());comp=json.loads((out/'expected-comparison.json').read_text());checks=json.loads((out/'claims/results.json').read_text());inv=json.loads((ROOT/args.inventory).read_text());source=pathlib.Path(inv['source_checkout']);cfg=json.loads((source/'config/reproduction.json').read_text());run=json.loads((ROOT/'experiments'/args.experiment/'run.json').read_text())
    assert run['status']==v['status']=='completed';assert len(v['steps'])==len(cfg['steps']) and all(s['status']=='completed' for s in v['steps']);assert comp['passed'] and len(comp['checks'])==len(cfg['compare_tables']);assert checks['all_registered_values_match'];assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==inv['source_commit']==v['source_commit'];assert not subprocess.check_output(['git','--no-optional-locks','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
    errors=[r['path'] for r in inv['files'] if digest(source/r['path'])!=r['sha256']];assert not errors,errors
    paper_match=digest(ROOT/'paper.md')==digest(out/'paper.md');assert paper_match
    figures=[]
    for name in ['national-model-information','generalization-one-week']:
        for ext in ['png','svg']:
            rel='figures/'+name+'.'+ext;equal=digest(ROOT/rel)==digest(out/rel);assert equal,rel;figures.append(dict(path=rel,sha256=digest(ROOT/rel),regenerated_bytes_match=equal))
    archive.mkdir(parents=True,exist_ok=False)
    for stage in v['steps']:
        child=archive/stage['name'];child.mkdir()
        for filename in ['replay-stdout.txt','replay-stderr.txt']:shutil.copy2(out/stage['name']/filename,child/filename)
    for p in [*out.rglob('*.json'),*out.rglob('*.jsonl')]:
        rel=p.relative_to(out)
        if '.cache' in rel.parts:continue
        target=archive/'json'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    for name in ['paper.md','verification-run.json','expected-comparison.json']:shutil.copy2(out/name,archive/name)
    result=dict(observed_at_utc=now(),status='completed',phase='post_review',successful_experiment=args.experiment,successful_source_commit=v['source_commit'],stages=len(v['steps']),tables=len(comp['checks']),table_rows=sum(c['rows'] for c in comp['checks']),max_absolute_numeric_difference=max(c['max_absolute_numeric_difference'] for c in comp['checks']),relative_tolerance=comp['comparison_relative_tolerance'],absolute_tolerance=comp['comparison_absolute_tolerance'],claims=checks['claims'],claim_evidence_rows=len(checks['checks']),elapsed_seconds=v['elapsed_seconds'],source_input_files_checked=len(inv['files']),source_inputs_unchanged=True,source_tracked_edits_after=False,full_not_quick=not v['quick'],manuscript_bytes_match_saved_analysis_render=paper_match,figures=figures,independent_reproduction=False,existing_dependency_environment_reused=True,git_objects_shared=True,immutable_source_input_files_shared=True,replay_outputs_started_empty=True,api_required=False,network_required=False,initial_verification_record_preserved='review/verification-result.json',archive=args.archive)
    (ROOT/'review/final-verification-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');eid=event('final_offline_verification_completed','Post-review full offline replay completed; all tables/claims, manuscript/figures match; selected source inputs unchanged. Initial proof retained.',['review/final-verification-result.json',args.archive],source_commit=v['source_commit'],tables=result['tables'],table_rows=result['table_rows'])
    path=ROOT/'review/response-1.json';response=json.loads(path.read_text());response.update(full_verification_status='completed',full_verification_experiment=args.experiment,full_verification_event_id=eid,scientific_change_commit=v['source_commit'])
    for r in response['comments']:r['change_commit']=v['source_commit'];r['final_artifact_commit_ref']='final'
    path.write_text(json.dumps(response,ensure_ascii=False,indent=2)+'\n')
    with (ROOT/'review/response-1.md').open('a') as f:f.write('\n'+result['observed_at_utc']+'：改訂コミット`'+v['source_commit']+'`の清浄な複製から、全'+str(result['stages'])+'段階・'+str(result['tables'])+'表・'+str(result['table_rows'])+'行を再計算し、最大数値差'+str(result['max_absolute_numeric_difference'])+'で一致した。'+str(result['claims'])+'主張・'+str(result['claim_evidence_rows'])+'根拠行、論文と4画像ファイルのバイト一致、入力'+str(len(inv['files']))+'ファイルの不変を確認した。縮小実行ではない。実行は同じ研究者・同じ既存依存環境で、独立再現とはしない。指摘別のchange_commitはこのコミットを指し、最終の記録・実測の追記はタグfinalから参照する。\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
