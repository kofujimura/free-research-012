"""Recompute the one authorized critique's accounting from saved public JSON."""
import argparse,json,pathlib
from decimal import Decimal
from api_wrapper import costs,latest_calls
from record import ROOT

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args();out=pathlib.Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);rows=[];total=Decimal(0)
    for call in latest_calls().values():
        request=json.loads((ROOT/call['request_path']).read_text());response=json.loads((ROOT/call['response_path']).read_text());fee,detail=costs(response)
        assert request['model']=='gpt-6-astra' and request['reasoning']=={'effort':'xhigh'} and request['background'] is True
        assert request['tools']==[{'type':'web_search'}] and request['include']==['web_search_call.action.sources'] and 'max_output_tokens' not in request
        assert response['status']=='completed' and response['model']==call['model_returned'] and response['usage']==call['usage'] and fee==Decimal(str(call['cost_usd']))
        total+=fee;rows.append(dict(call_id=call['call_id'],model_returned=call['model_returned'],response_status=response['status'],usage=response['usage'],calculated_actual_cost_usd=str(fee),cost_detail=detail,recorded_cost_matches=True))
    manifest=json.loads((ROOT/'manifest.json').read_text());assert total==Decimal(str(manifest['api']['cumulative_actual_cost_usd'])) and total<=Decimal(str(manifest['api']['budget_usd']))
    result=dict(unique_requests=len(rows),calls=rows,total_calculated_actual_cost_usd=str(total),network_required=False,ai_api_called=False,invoice_reconciliation_performed=False,fee_correction_preserved_in_append_only_ledger=True);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(unique_requests=len(rows),total_calculated_actual_cost_usd=str(total),passed=True)))

if __name__=='__main__':main()
