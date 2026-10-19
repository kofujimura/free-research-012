"""Run a committed experiment with bounded duration and local provenance."""
from __future__ import annotations
import argparse,datetime as dt,fcntl,hashlib,json,os,pathlib,signal,subprocess,time
from record import ROOT,now,event

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def registered_active(item):
    # Conservative file-based accounting avoids probing processes through the sandbox.
    p=ROOT/'experiments'/item['id']/'run.json'
    return not p.exists() or json.loads(p.read_text()).get('status')=='running'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--id',required=True);ap.add_argument('--plan',required=True);ap.add_argument('--timeout',type=int,default=1800);ap.add_argument('--input',action='append',default=[]);ap.add_argument('command',nargs=argparse.REMAINDER);a=ap.parse_args()
    command=a.command[1:] if a.command and a.command[0]=='--' else a.command
    if not command:raise SystemExit('No experiment command')
    if not 1<=a.timeout<=1800:raise SystemExit('Timeout must be within 1..1800 seconds')
    manifest=json.loads((ROOT/'manifest.json').read_text())
    deadline=dt.datetime.fromisoformat(manifest['draft_deadline_utc'].replace('Z','+00:00'))
    if manifest.get('review',{}).get('received'):
        deadline=dt.datetime.fromisoformat(manifest['review']['deadline_utc'].replace('Z','+00:00'))
    if dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=a.timeout)>deadline:
        raise SystemExit('Full timeout would exceed the active deadline; reduce the bounded run')
    plan=ROOT/a.plan
    if not plan.is_file():raise SystemExit('Plan not found')
    head=git('rev-parse','HEAD')
    committed=subprocess.check_output(['git','show',head+':'+a.plan],cwd=ROOT)
    if committed!=plan.read_bytes():raise SystemExit('Plan differs from committed version')
    if git('diff','HEAD','--','scripts'):
        raise SystemExit('Commit experiment code before running it')
    # Validate before reserving an active slot or creating an experiment directory.
    # A nonexistent hash input previously left a stale registry entry (E067).
    input_hashes={s:digest(ROOT/s) for s in a.input}
    out=ROOT/'experiments'/a.id
    if out.exists():raise SystemExit('Experiment ID exists; preserve it and use a new ID')
    used_kib=int(subprocess.check_output(['du','-sk',str(ROOT)],text=True).split()[0])
    if used_kib*1024>=manifest['resource_limits']['storage_bytes']-100_000_000:
        raise SystemExit('Storage limit approaching; do not start a new experiment')
    lock=ROOT/'experiments/.runner-lock'
    with lock.open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        active_path=ROOT/'experiments/.active.json'
        active=json.loads(active_path.read_text()) if active_path.exists() else []
        active=[x for x in active if registered_active(x)]
        if len(active)>=2:raise SystemExit('Two experiment jobs are already active')
        active.append({'id':a.id,'controller_pid':os.getpid(),'started_at_utc':now()})
        active_path.write_text(json.dumps(active,indent=2)+'\n')
    out.mkdir(parents=True)
    metadata={'experiment_id':a.id,'plan_path':a.plan,'plan_commit':head,'plan_sha256':digest(plan),'code_commit':head,'command':command,'started_at_utc':now(),'timeout_seconds':a.timeout,'input_files':input_hashes,'seed':'Defined by the committed experiment configuration','status':'running','controller_pid':os.getpid(),'storage_before_bytes_du':used_kib*1024}
    (out/'run.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    eid=event('experiment_started',f'{a.id}: bounded run started',[str((out/'run.json').relative_to(ROOT)),a.plan],experiment_id=a.id,plan_commit=head,code_commit=head)
    env=os.environ.copy();env.update(XDG_CACHE_HOME=str(ROOT/'.cache'),HF_HOME=str(ROOT/'.cache/huggingface'),PIP_CACHE_DIR=str(ROOT/'.cache/pip'),MPLCONFIGDIR=str(ROOT/'.cache/matplotlib'),PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',HF_HUB_DISABLE_TELEMETRY='1')
    env.pop('FREE_RESEARCH_OPENAI_API_KEY',None)
    env['HF_HUB_DISABLE_IMPLICIT_TOKEN']='1'
    env['RESEARCH_EXPERIMENT_DIR']=str(out)
    tick=time.monotonic();child=None
    try:
        with (out/'stdout.txt').open('w') as stdout,(out/'stderr.txt').open('w') as stderr:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
            metadata['child_pid']=child.pid
            try:
                returncode=child.wait(timeout=a.timeout)
                status='completed' if returncode==0 else 'failed'
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                returncode=child.returncode;status='timeout'
    except BaseException as exc:
        if child and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=5)
        returncode=-1;status='runner_error';metadata['runner_error']=type(exc).__name__+': '+str(exc)
    finally:
        metadata.update(ended_at_utc=now(),elapsed_seconds=time.monotonic()-tick,returncode=returncode,status=status)
        (out/'run.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
        event('experiment_ended' if status=='completed' else 'experiment_failed',f'{a.id}: {status}, exit {returncode}',[str((out/'run.json').relative_to(ROOT))],related=[eid],experiment_id=a.id)
        with lock.open('a+') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            active=json.loads(active_path.read_text())
            active_path.write_text(json.dumps([x for x in active if x['controller_pid']!=os.getpid()],indent=2)+'\n')
    print(json.dumps(metadata,ensure_ascii=False))
    raise SystemExit(0 if status=='completed' else 1)

if __name__=='__main__':main()
