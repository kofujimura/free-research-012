"""The sole AI API entry point for free-research-012.

Only the authorized topic-critique exception is implemented. No research task is
delegated. SDK retries are disabled; at most two submit attempts are permitted.
Polling and cancellation are not counted as new model requests.
"""
from __future__ import annotations
import argparse,decimal,hashlib,json,os,pathlib,sys
from record import ROOT,now,event,append_json

RATES={'input_per_million':'10','cached_input_per_million':'1','cache_write_per_million':'12.50','output_per_million':'50','web_search_per_call':'0.01'}
BUDGET=decimal.Decimal('20')
PRICE_SOURCE='literature/openai-pricing.md'

def read_json(p):return json.loads(p.read_text())

def latest_calls():
    rows={}
    for line in (ROOT/'api_calls.jsonl').read_text().splitlines():
        row=json.loads(line);rows[row['call_id']]=row
    return rows

def known_cost():
    return sum((decimal.Decimal(str(x['cost_usd'])) for x in latest_calls().values() if x.get('cost_usd') is not None),decimal.Decimal('0'))

def client():
    from openai import OpenAI
    key=os.environ.get('FREE_RESEARCH_OPENAI_API_KEY')
    if not key:raise RuntimeError('Designated API key is absent')
    return OpenAI(api_key=key,base_url='https://api.openai.com/v1',max_retries=0,timeout=45)

def write_json(path,obj):
    text=json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n'
    key=os.environ.get('FREE_RESEARCH_OPENAI_API_KEY')
    if key and key in text:
        raise RuntimeError('Credential content would be written; suppressed and stopped')
    path.write_text(text)

def costs(response):
    usage=response.get('usage')
    if not usage:return None,{'reason':'Usage not yet available'}
    if response.get('service_tier') not in (None,'default','standard'):
        return None,{'reason':'Unexpected service tier; rate not assumed','returned_service_tier':response.get('service_tier')}
    details=usage.get('input_tokens_details',{})
    if 'cached_tokens' not in details or 'cache_write_tokens' not in details:
        return None,{'reason':'Cache-read/write usage is missing; do not assume zero'}
    cached=details['cached_tokens'];written=details['cache_write_tokens']
    total_in=usage['input_tokens'];total_out=usage['output_tokens']
    if any(type(x) is not int or x<0 for x in [cached,written,total_in,total_out]) or cached+written>total_in:
        return None,{'reason':'Invalid or overlapping token accounting; charges not assumed'}
    if total_in>272000:
        return None,{'reason':'Usage exceeds verified short-context accounting scope; long-context charge not assumed'}
    ordinary=total_in-cached-written
    web=sum(x.get('type')=='web_search_call' for x in response.get('output',[]))
    D=decimal.Decimal
    token_cost=(D(ordinary)*D(RATES['input_per_million'])+D(cached)*D(RATES['cached_input_per_million'])+D(written)*D(RATES['cache_write_per_million'])+D(total_out)*D(RATES['output_per_million']))/D(1_000_000)
    search_cost=D(web)*D(RATES['web_search_per_call'])
    return token_cost+search_cost,{'input_tokens':total_in,'ordinary_input_tokens':ordinary,'cached_input_tokens':cached,'cache_write_tokens':written,'output_tokens':total_out,'reasoning_tokens':usage.get('output_tokens_details',{}).get('reasoning_tokens'),'web_search_calls':web,'token_cost_usd':str(token_cost),'web_search_cost_usd':str(search_cost),'rates':RATES,'pricing_source':PRICE_SOURCE,'cache_accounting_source':'literature/reading-cache-accounting-official.json','note':'Ordinary input = total input minus cached reads minus cache writes. Reasoning is already in output. Search content is in input usage; search calls charged separately. This is a usage/rate calculation, not invoice reconciliation.'}

def save_status(call_id,response,request_path,requested_at):
    folder=ROOT/'api'/call_id;folder.mkdir(parents=True,exist_ok=True)
    seq=len(list(folder.glob('response-*.json')))+1
    rp=folder/f'response-{seq:03d}.json';write_json(rp,response)
    cost,detail=costs(response)
    prior=latest_calls().get(call_id)
    previous_cost=decimal.Decimal(str(prior['cost_usd'])) if prior and prior.get('cost_usd') is not None else decimal.Decimal('0')
    cumulative=known_cost()-previous_cost+(cost or decimal.Decimal('0'))
    row=dict(call_id=call_id,experiment_id='topic-selection-critique',purpose='Authorized one-time critique of five topic candidates; user section 2.1 step 6',requested_at_utc=requested_at,observed_at_utc=now(),provider='OpenAI',model_requested='gpt-6-astra',model_returned=response.get('model'),parameters=read_json(ROOT/request_path),request_path=request_path,response_path=str(rp.relative_to(ROOT)),usage=response.get('usage'),cost_usd=float(cost) if cost is not None else None,cumulative_cost_usd=float(cumulative),cost_detail=detail,status=response.get('status'),error=response.get('error'),response_id=response.get('id'),budget_check={'actual_known_before_usd':str(known_cost()),'budget_usd':str(BUDGET),'next_maximum_cost_check':'Exempt only for topic critique by user instruction; no max_output_tokens is set'},ledger_note='Append-only status snapshots. Aggregate by last row per call_id; do not sum status rows.')
    append_json('api_calls.jsonl',row)
    write_json(folder/'state.json',row)
    event('api_status',f"{call_id}: {response.get('status')}",[str(rp.relative_to(ROOT)),'api_calls.jsonl'],call_id=call_id)
    print(json.dumps({'call_id':call_id,'status':response.get('status'),'response_id':response.get('id'),'cost_usd':row['cost_usd'],'known_cumulative_usd':float(cumulative)}))

def submit(prompt_path,without_search=False):
    calls=latest_calls()
    if len(calls)>=2:raise RuntimeError('Topic critique request limit of two attempts reached')
    if any(x['status'] in ('queued','in_progress','completed') for x in calls.values()):
        raise RuntimeError('Existing pending/completed response must be reused')
    if known_cost()>=BUDGET:raise RuntimeError('Known actual budget exhausted')
    if without_search:
        if len(calls)!=1:raise RuntimeError('Search-free fallback is permitted only on the second request')
        err=json.dumps(next(iter(calls.values())).get('error','')).lower()
        if 'search' not in err:raise RuntimeError('Fallback requires a documented web-search incompatibility')
    call_id=f'CALL{len(calls)+1:03d}';folder=ROOT/'api'/call_id;folder.mkdir(parents=True,exist_ok=True)
    prompt=(ROOT/prompt_path).read_text()
    req={'model':'gpt-6-astra','reasoning':{'effort':'xhigh'},'input':prompt,'background':True,'service_tier':'default'}
    if not without_search:req.update(tools=[{'type':'web_search'}],include=['web_search_call.action.sources'])
    assert 'max_output_tokens' not in req
    request_path=str((folder/'request.json').relative_to(ROOT));write_json(ROOT/request_path,req)
    stamp=now();event('api_requested',f'{call_id}: submit specified topic critique model and settings',[request_path,prompt_path],call_id=call_id)
    try:
        response=client().responses.create(**req).model_dump(mode='json')
        save_status(call_id,response,request_path,stamp)
    except Exception as exc:
        key=os.environ.get('FREE_RESEARCH_OPENAI_API_KEY','')
        msg=str(exc).replace(key,'[REDACTED]') if key else str(exc)
        obj={'status':'failed','model':None,'usage':None,'error':{'type':type(exc).__name__,'message':msg}}
        save_status(call_id,obj,request_path,stamp)

def poll(call_id,cancel=False):
    row=read_json(ROOT/'api'/call_id/'state.json')
    if row['status'] not in ('queued','in_progress'):
        print(json.dumps({'call_id':call_id,'status':row['status'],'reused':True}));return
    cli=client()
    response=(cli.responses.cancel(row['response_id']) if cancel else cli.responses.retrieve(row['response_id'],include=['web_search_call.action.sources'])).model_dump(mode='json')
    save_status(call_id,response,row['request_path'],row['requested_at_utc'])

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['submit-critic','poll','cancel']);ap.add_argument('path_or_id');ap.add_argument('--without-search',action='store_true');a=ap.parse_args()
    if a.action=='submit-critic':submit(a.path_or_id,a.without_search)
    else:poll(a.path_or_id,cancel=a.action=='cancel')
