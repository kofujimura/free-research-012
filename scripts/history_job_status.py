"""Read the finite job plan and return up to two safe next foreground commands."""
import argparse,json,pathlib,shlex,subprocess

ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--preparation',required=True);args=ap.parse_args();prep=ROOT/args.preparation;assert json.loads((prep/'run.json').read_text())['status']=='completed';jobs=json.loads((prep/'inference-jobs.json').read_text());counts={};pending=[];failures=[]
    active=json.loads((ROOT/'experiments/.active.json').read_text());active=[x for x in active if not (ROOT/'experiments'/x['id']/'run.json').exists() or json.loads((ROOT/'experiments'/x['id']/'run.json').read_text()).get('status')=='running']
    for j in jobs:
        p=ROOT/j['forecast_dir']/'run.json';status=json.loads(p.read_text())['status'] if p.exists() else 'pending';counts[status]=counts.get(status,0)+1
        if status=='pending':pending.append(j)
        elif status not in ['completed','running']:failures.append(j['experiment_id'])
    dirty=subprocess.check_output(['git','status','--porcelain','--','scripts'],cwd=ROOT,text=True).strip();selected=[]
    if not failures and not dirty:
        for j in pending[:max(0,2-len(active))]:selected.append(dict(experiment_id=j['experiment_id'],command=shlex.join(j['command'])))
    print(json.dumps(dict(counts=counts,active_experiments=[x['id'] for x in active],failures=failures,script_changes_prevent_dispatch=bool(dirty),next_jobs=selected,all_completed=counts.get('completed',0)==len(jobs))))

if __name__=='__main__':main()
