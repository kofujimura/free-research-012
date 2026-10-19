"""Small local provenance helpers. No network and no credential output."""
from __future__ import annotations
import argparse, datetime as dt, fcntl, hashlib, json, os, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def append_json(path, obj):
    with (ROOT / path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def event(kind, summary, paths=(), related=(), **extra):
    p = ROOT / "events.jsonl"
    with p.open('a+',encoding='utf-8') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        f.seek(0);n=sum(1 for _ in f)+1
        eid=f"EV{n:04d}"
        obj=dict(event_id=eid,observed_at_utc=now(),type=kind,summary=summary,
                 artifact_paths=list(paths),related_ids=list(related),**extra)
        f.seek(0,2);f.write(json.dumps(obj,ensure_ascii=False)+'\n');f.flush()
    return eid

def scan_secrets():
    key = os.environ.get("FREE_RESEARCH_OPENAI_API_KEY")
    if not key:
        return dict(key_present=False, scanned=True, match_count=0)
    matches=[]
    needle=key.encode()
    scanned_files=0
    for p in ROOT.rglob("*"):
        if p.is_symlink() or not p.is_file():
            continue
        try:
            scanned_files+=1
            tail=b''
            with p.open('rb') as f:
                while chunk:=f.read(1024*1024):
                    block=tail+chunk
                    if needle in block:
                        matches.append(str(p.relative_to(ROOT)));break
                    tail=block[-(len(needle)-1):] if len(needle)>1 else b''
        except OSError:
            pass
    if matches:
        event("safety_stop", "Credential value detected; stop immediately. Value suppressed.", matches)
        raise SystemExit("SECRET MATCH DETECTED: STOP. Value suppressed.")
    return dict(key_present=True, scanned=True, match_count=0, scanned_files=scanned_files,
                scope='All regular files under the research root, including environment/cache and raw Git objects; symlinks are not followed')

def commit(message, related=()):
    result=scan_secrets()
    eid=event("git_commit_requested", message, related=related, secret_scan=result)
    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    subprocess.run(["git", "-c", "user.name=Free Research AI", "-c", "user.email=research@localhost", "commit", "-m", f"{eid} {message}"], cwd=ROOT, check=True)
    sha=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    event("git_commit_completed", message, related=[eid, *related], commit_id=sha)
    return sha

if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("action", choices=["event", "commit", "scan", "time"])
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--kind", default="note")
    args=ap.parse_args()
    if args.action=="event": print(event(args.kind,args.text))
    if args.action=="commit": print(commit(args.text))
    if args.action=="scan": print(json.dumps(scan_secrets()))
    if args.action=="time": print(now())
