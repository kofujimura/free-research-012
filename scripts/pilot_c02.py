"""Bounded acquisition pilot for dense satellite features and public air observations."""
import hashlib,json,pathlib,signal,time,urllib.parse,zipfile,io
import requests,numpy as np,pandas as pd
from record import ROOT,now,event,append_json
from fetch import fetch

signal.alarm(900)
out=ROOT/'experiments/pilot-c02';out.mkdir(parents=True,exist_ok=True)
started=now();clock=time.monotonic();eid=event('pilot_started','C02: check open annual air-quality data and small satellite-feature window.',['protocol/pilots.md'],candidate_id='C02')
results={}
try:
    url='https://storage.googleapis.com/storage/v1/b/alphaearth_foundations/o?'+urllib.parse.urlencode({'prefix':'satellite_embedding/v1/annual/2024/10N/','maxResults':1})
    r=requests.get(url,timeout=45);r.raise_for_status()
    meta=r.json();(out/'gcs-list.json').write_text(json.dumps(meta,indent=2)+'\n')
    item=meta.get('items',[{}])[0]
    if item.get('name'):
        import rasterio
        from rasterio.windows import Window
        u='https://storage.googleapis.com/alphaearth_foundations/'+urllib.parse.quote(item['name'],safe='/')
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tiff,.tif',GDAL_HTTP_TIMEOUT='45',GDAL_HTTP_MAX_RETRY='0',GDAL_CACHEMAX=32):
            with rasterio.open(u) as ds:
                win=Window(max(ds.width//2-8,0),max(ds.height//2-8,0),16,16)
                values=ds.read(window=win)
                results['raster']={'url':u,'file_size':item.get('size'),'full_shape':[ds.count,ds.height,ds.width],'window_shape':list(values.shape),'crs':str(ds.crs),'bounds':list(ds.bounds),'nodata_fraction':float(np.mean(values==-128))}
                np.save(out/'raw-window.npy',values)
        append_json('data/downloads.jsonl',dict(url=u,retrieved_at_utc=now(),path='experiments/pilot-c02/raw-window.npy',license='CC BY 4.0; Google and Google DeepMind',partial_range_read=True,sha256=hashlib.sha256((out/'raw-window.npy').read_bytes()).hexdigest()))
except Exception as e:
    results['raster_error']=f'{type(e).__name__}: {e}'
try:
    info=fetch('https://aqs.epa.gov/aqsweb/airdata/annual_all_2024.zip','data/pilot-c02/annual_all_2024.zip',license_note='US EPA public data',purpose='C02 acquisition pilot',max_bytes=80_000_000)
    with zipfile.ZipFile(ROOT/info['path']) as z:
        with z.open(z.namelist()[0]) as f:
            df=pd.read_csv(f,encoding='utf-8',low_memory=False)
    g=df[df['Parameter Code']==88101]
    cols=[c for c in ['State Code','County Code','Site Num','Latitude','Longitude'] if c in g]
    s=g[cols].drop_duplicates()
    results['air_quality']={'rows_all':len(df),'rows_pm25':len(g),'unique_sites_pm25':len(s),'columns':list(df.columns),'input':info}
except Exception as e:
    results['air_quality_error']=f'{type(e).__name__}: {e}'
results.update(started_at_utc=started,ended_at_utc=now(),elapsed_seconds=time.monotonic()-clock,note='Acquisition/scale only. No prediction accuracy evaluated.')
(out/'acquisition.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
event('pilot_ended','C02 acquisition pilot ended; successes and failures retained.',['experiments/pilot-c02/acquisition.json'],related=[eid],candidate_id='C02')
print(json.dumps(results,ensure_ascii=False))
