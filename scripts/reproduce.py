"""One offline entry point. All writes go to an explicit output directory."""
import argparse,datetime as dt,json,os,pathlib,subprocess,sys,time

ROOT=pathlib.Path(__file__).resolve().parents[1]
ALLOWED={'analyze_review_strata.py','analyze_joint_comparisons.py','verify_claims.py','assemble_history_control.py','analyze_history_control.py','verify_temporal.py','verify_site_weekly.py','verify_artifacts.py','verify_growth.py','verify_api_accounting.py','prepare_pooled_features.py','train_pooled.py','compare_pooled_refit.py','analyze.py','analyze_extra_baselines.py','analyze_updates.py','panel_analysis.py','analyze_sensitivity.py','analyze_growth.py','analyze_interval_calibration.py','analyze_freshness_interaction.py','analyze_input_quality.py','analyze_shifted.py','analyze_indicator_choice.py','analyze_pooled.py','verify_pooled.py','plot_results.py','render_paper.py','compare_recalculation.py'}

def now():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--config',default='config/reproduction.json');ap.add_argument('--quick',action='store_true');ap.add_argument('--max-seconds',type=int,default=1740);args=ap.parse_args();out=pathlib.Path(args.out).resolve()
    if out==ROOT or out.is_relative_to(ROOT):raise SystemExit('Choose an output directory outside the source checkout')
    out.mkdir(parents=True,exist_ok=True);cfg=json.loads((ROOT/args.config).read_text());env=os.environ.copy();env.pop('FREE_RESEARCH_OPENAI_API_KEY',None);env.pop('OPENAI_API_KEY',None);env.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',XDG_CACHE_HOME=str(out/'.cache'),MPLCONFIGDIR=str(out/'.cache/matplotlib'),HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1');tick=time.monotonic();records=[];source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip();assert not dirty,'Verification source checkout must have no tracked edits';result=dict(started_at_utc=now(),source_checkout=str(ROOT),source_commit=source_commit,source_tracked_edits_before=False,output_directory=str(out),quick=args.quick,network_required=False,ai_api_required=False,steps=records,status='running')
    skipped={s['name'] for s in cfg['steps'] if args.quick and s.get('large_optional',False)}
    aliases={k:str(out/v) for k,v in cfg.get('report_aliases',{}).items() if v not in skipped}
    (out/'report-manifest.json').write_text(json.dumps(aliases,indent=2)+'\n')
    if cfg.get('quality_datasets'):
        quality=json.loads(json.dumps(cfg['quality_datasets']).replace('{OUT}',str(out)))
        (out/'quality-datasets.json').write_text(json.dumps(quality,indent=2)+'\n')
    if cfg.get('history_original_scores'):
        history=json.loads(json.dumps(cfg['history_original_scores']).replace('{OUT}',str(out)))
        (out/'history-original-scores.json').write_text(json.dumps(history,indent=2)+'\n')
    if cfg.get('joint_comparison_datasets'):
        joint=json.loads(json.dumps(cfg['joint_comparison_datasets']).replace('{OUT}',str(out)))
        (out/'joint-comparison-datasets.json').write_text(json.dumps(joint,indent=2)+'\n')
    for step in cfg['steps']:
        if args.quick and step.get('large_optional',False):continue
        script=step['script']
        if script not in ALLOWED:raise SystemExit('Not an offline analysis/replay entry: '+script)
        directory=out/step['name'];directory.mkdir(parents=True,exist_ok=True);arguments=[x.replace('{OUT}',str(out)).replace('{ROOT}',str(ROOT)) for x in step.get('args',[])]
        if args.quick and script=='compare_recalculation.py':arguments.append('--quick')
        command=[sys.executable,str(ROOT/'scripts'/script),*arguments];current_env=dict(env,RESEARCH_EXPERIMENT_DIR=str(directory));remaining=args.max_seconds-(time.monotonic()-tick)
        if remaining<=0:result['status']='timeout';break
        record=dict(name=step['name'],script=script,command=command,started_at_utc=now());records.append(record);part=time.monotonic()
        try:
            with (directory/'replay-stdout.txt').open('w') as stdout,(directory/'replay-stderr.txt').open('w') as stderr:
                code=subprocess.run(command,cwd=ROOT,env=current_env,stdout=stdout,stderr=stderr,timeout=remaining).returncode
            record.update(status='completed' if code==0 else 'failed',returncode=code)
        except subprocess.TimeoutExpired:record.update(status='timeout',returncode=None)
        record.update(ended_at_utc=now(),elapsed_seconds=time.monotonic()-part);(out/'verification-run.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(record,ensure_ascii=False),flush=True)
        if record['status']!='completed':result['status']=record['status'];break
    else:result['status']='completed'
    result.update(ended_at_utc=now(),elapsed_seconds=time.monotonic()-tick);(out/'verification-run.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=result['status'],elapsed_seconds=result['elapsed_seconds'],steps=len(records))))
    raise SystemExit(0 if result['status']=='completed' else 1)

if __name__=='__main__':main()
