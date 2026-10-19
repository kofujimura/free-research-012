"""Build the prespecified facility panel from frozen weekly release states."""
import bisect,functools,hashlib,json,os,pathlib
import pandas as pd
from prepare_inputs import ROOT,load_config
from panel_inputs import build_panel

WEEKLY='experiments/E023-site-weekly-cohort'

class SiteArchive:
    def __init__(self,records):
        self.records=sorted(records,key=lambda x:pd.Timestamp(x['commit_time']));self.times=[pd.Timestamp(r['commit_time']).tz_convert('UTC') for r in self.records];self.freeze=self.times[-1]
    def asof(self,stamp):
        i=bisect.bisect_right(self.times,pd.Timestamp(stamp))-1
        return self.records[i] if i>=0 else None
    @functools.lru_cache(maxsize=8)
    def release(self,commit):
        r=next(x for x in self.records if x['commit']==commit);frame=pd.read_parquet(ROOT/r['path']);result={}
        for (site,pathogen),d in frame.groupby(['site_id','pathogen'],sort=False):
            key=site+'|'+pathogen;result[key]=d.drop(columns=['site_id','pathogen']).set_index('date').sort_index()
        return result
    def get_series(self,record,unit):
        return self.release(record['commit']).get(unit,pd.DataFrame(columns=['value','population','floor_fraction','n_days','lab_change'],index=pd.DatetimeIndex([],name='date'),dtype=float))

def main():
    out=pathlib.Path(os.environ['RESEARCH_EXPERIMENT_DIR']);cfg=load_config();sitecfg=json.loads((ROOT/'config/multisite.json').read_text());cfg.update(sitecfg)
    root=ROOT/WEEKLY;index=json.loads((root/'weekly-index.json').read_text());cohort=pd.read_csv(root/'cohort.csv',dtype={'site_id':str})
    units=[]
    for r in cohort.to_dict('records'):
        units.append(dict(unit_id=r['site_id']+'|'+r['pathogen'],site_id=r['site_id'],pathogen=r['pathogen'],unit_level='site',active2026=bool(r['active2026']),cohort_population=float(r['population'])))
    manifest=dict(weekly_index=WEEKLY+'/weekly-index.json',weekly_index_sha256=hashlib.sha256((root/'weekly-index.json').read_bytes()).hexdigest(),cohort_path=WEEKLY+'/cohort.csv',cohort_sha256=hashlib.sha256((root/'cohort.csv').read_bytes()).hexdigest(),source_files={r['path']:r['sha256'] for r in index['records']},raw_sources={r['raw_source_path']:r['raw_source_sha256'] for r in index['records']})
    build_panel(SiteArchive(index['records']),units,cfg,out,'W-FRI',manifest)

if __name__=='__main__':main()
