"""Polite public-data downloader with local provenance; no credentials."""
from __future__ import annotations
import argparse, hashlib, json, pathlib, ssl, time, urllib.request, urllib.error, urllib.parse, urllib.robotparser
import certifi
from record import ROOT, now, append_json

UA = "FreeResearch012/1.0 (public-data academic analysis; low request rate)"
TLS = ssl.create_default_context(cafile=certifi.where())

def fetch(url, relative, *, license_note="Not established; reading only", purpose="literature", max_bytes=50_000_000, robots=True):
    path=ROOT / relative
    if path.exists():
        return {"status":"cached", "path":relative, "bytes":path.stat().st_size,
                "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    path.parent.mkdir(parents=True, exist_ok=True)
    record=dict(url=url, retrieved_at_utc=now(), path=relative, license=license_note, purpose=purpose)
    if robots:
        parsed=urllib.parse.urlsplit(url)
        robot_url=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,"/robots.txt","",""))
        rp=urllib.robotparser.RobotFileParser()
        try:
            req=urllib.request.Request(robot_url,headers={"User-Agent":UA})
            with urllib.request.urlopen(req,timeout=30,context=TLS) as response:
                raw=response.read(2_000_000).decode("utf-8",errors="replace")
            rp.parse(raw.splitlines())
            allowed=rp.can_fetch(UA,url)
            record["robots"]={"url":robot_url,"allowed":allowed,"sha256":hashlib.sha256(raw.encode()).hexdigest()}
            if not allowed:
                raise RuntimeError("robots.txt disallows retrieval")
            delay=rp.crawl_delay(UA) or rp.crawl_delay("*") or 1
            time.sleep(min(max(delay,1),60))
        except urllib.error.HTTPError as e:
            if e.code in (404,410):
                record["robots"]={"url":robot_url,"status":e.code,"allowed":True}
            else:
                record["robots"]={"url":robot_url,"status":e.code,"allowed":None}
                raise
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=90,context=TLS) as response:
            data=response.read(max_bytes+1)
            if len(data)>max_bytes:
                raise RuntimeError("Download exceeds permitted per-file size")
            record.update(http_status=response.status,final_url=response.url,content_type=response.headers.get("Content-Type"))
        path.write_bytes(data)
        record.update(status="success",bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    except Exception as e:
        record.update(status="failed",error=f"{type(e).__name__}: {e}")
        append_json("data/downloads.jsonl",record)
        raise
    append_json("data/downloads.jsonl",record)
    return record

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("url");ap.add_argument("path")
    ap.add_argument("--license",default="Not established; reading only")
    ap.add_argument("--purpose",default="literature")
    args=ap.parse_args()
    print(json.dumps(fetch(args.url,args.path,license_note=args.license,purpose=args.purpose),ensure_ascii=False))
