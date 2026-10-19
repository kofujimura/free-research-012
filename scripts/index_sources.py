"""Index saved search results as search-only, never as full-text evidence."""
import hashlib,json,pathlib,re
from record import ROOT,now,append_json

existing=set()
for line in (ROOT/'sources.jsonl').read_text().splitlines():
    existing.add(json.loads(line)['url'])
added=0
for p in sorted((ROOT/'literature').glob('*.txt')):
    for line in p.read_text().splitlines():
        m=re.fullmatch(r'(.+?) \((https?://[^ ]+)\)',line)
        if not m:continue
        title,url=m.groups()
        if url in existing:continue
        sid='S'+hashlib.sha256(url.encode()).hexdigest()[:10]
        append_json('sources.jsonl',dict(source_id=sid,title=title,url=url,doi=None,authors=None,
             year=None,version=None,retrieved_at_utc=now(),verification_scope='search_result_only',
             supports=['topic exploration only; not paper evidence until full text checked'],
             record_path=str(p.relative_to(ROOT))))
        existing.add(url);added+=1
print(json.dumps({'new_search_only_sources':added,'total_urls':len(existing)}))
