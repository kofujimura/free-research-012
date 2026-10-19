"""Build the explicit offline verification workflow (does not execute it)."""
import json,pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    steps=[];compare=[];aliases={};quality=[]
    def add(name,script,args=(),expected=None,files=(),optional=False,env_output=False,outfile=None):
        arguments=list(args)
        if not env_output:arguments+=['--out','{OUT}'+('/'+name if outfile is None else '/'+outfile if outfile else '')]
        steps.append(dict(name=name,script=script,args=arguments,large_optional=optional))
        for file in files:compare.append(dict(expected=expected+'/'+file,actual=name+'/'+file,large_optional=optional))
    mainpanel='experiments/E007-prepare-inputs-fixed';sitepanel='experiments/E024-site-panel-inputs';nzpanel='experiments/E027-nz-panel-inputs-eligible';rawpanel='experiments/E045-raw-sars-inputs'
    sitefits=['experiments/'+x for x in ['E060-pooled-fit-0','E062-pooled-fit-1','E064-pooled-fit-2','E066-pooled-fit-3','E068-pooled-fit-4']];nzfits=['experiments/'+x for x in ['E073-nz-pooled-fit-0','E074-nz-pooled-fit-1','E075-nz-pooled-fit-2','E077-nz-pooled-fit-3','E078-nz-pooled-fit-4']]
    def fitargs(paths):return [x for p in paths for x in ['--fit-dir',p]]
    add('temporal','verify_temporal.py',outfile='temporal/results.json')
    add('weekly_sample','verify_site_weekly.py',env_output=True)
    add('api_accounting','verify_api_accounting.py',outfile='api_accounting/results.json')
    add('primary','analyze.py',expected='experiments/E011-primary-analysis/results',files=['comparisons.csv','model-scores.csv','alerts-paired.csv','alerts.csv']);aliases['primary']='primary'
    add('extended','analyze_extra_baselines.py',expected='experiments/E022-extra-analysis-fixed/results',files=['comparisons.csv','model-scores.csv']);aliases['extended']='extended'
    add('updates','analyze_updates.py',['--primary-dir','{OUT}/primary'],expected='experiments/E018-update-decomposition/results',files=['anchored-comparisons.csv','update-contributions.csv','anchor-revision-summary.csv']);aliases['updates']='updates'
    panels=[('nz',nzpanel,['experiments/'+x for x in ['E039-nz-statistical','E040-nz-chronos','E041-nz-timesfm','E043-nz-extra']],'experiments/E044-nz-panel-analysis/results'),('site',sitepanel,json.loads((ROOT/'config/site-forecast-dirs.json').read_text()),'experiments/E072-site-panel-analysis/results'),('raw',rawpanel,['experiments/'+x for x in ['E047-raw-sars-statistical','E048-raw-sars-chronos','E049-raw-sars-timesfm','E050-raw-sars-extra']],'experiments/E052-raw-sars-analysis/results')]
    # Resolve actual saved directory spellings by the recorded experiment ID.
    for name,panel,folders,expected in panels:
        resolved=[]
        for folder in folders:
            candidates=list((ROOT/'experiments').glob(pathlib.Path(folder).name.split('-')[0]+'-*'));assert len(candidates)==1;resolved.append(str(candidates[0].relative_to(ROOT)))
        add(name,'panel_analysis.py',['--panel',panel,*[x for p in resolved for x in ['--forecast-dir',p]]],expected=expected,files=['comparisons.csv','model-scores.csv','case-availability.csv']);aliases[name]=name
    add('indicator','analyze_indicator_choice.py',['--raw-forecasts','{OUT}/raw/case-forecasts.csv.gz','--raw-panel',rawpanel,'--normalized-forecasts','{OUT}/extended/case-forecasts.csv.gz'],expected='experiments/E053-matched-raw-normalized/results',files=['matched-indicator-ratios.csv']);aliases['indicator']='indicator'
    add('sensitivity','analyze_sensitivity.py',['--primary-dir','{OUT}/primary'],expected='experiments/E038-reference-and-timing-sensitivity/results',files=['matched-maturity.csv','matched-input-reference-matrix.csv','information-advance-counts.csv','timestamp-proxy-sensitivity.csv','intended-case-availability.csv','context-audit.csv']);aliases['sensitivity']='sensitivity'
    add('shifted','analyze_shifted.py',['--scenarios','experiments/E057-shifted-inputs-label-availability/scenarios.json','--forecast-map','config/shift-forecast-map.json'],expected='experiments/E076-shifted-timing-analysis/results',files=['comparisons.csv']);aliases['shifted']='shifted'
    for name,panel,features,fits,expected in [('site',sitepanel,'experiments/E056-pooled-feature-preparation',sitefits,'experiments/E079-site-pooled-analysis/results'),('nz',nzpanel,'experiments/E071-nz-pooled-features',nzfits,'experiments/E081-nz-pooled-analysis/results')]:
        add(name+'_features','prepare_pooled_features.py',['--panel',panel],env_output=True)
        add(name+'_model_replay','verify_pooled.py',['--features','{OUT}/'+name+'_features','--expected-features',features,*fitargs(fits)])
        add(name+'_first_refit','train_pooled.py',['--features','{OUT}/'+name+'_features','--start','0','--stop','1'],env_output=True)
        add(name+'_refit_check','compare_pooled_refit.py',['--original',fits[0],'--refit','{OUT}/'+name+'_first_refit'],outfile=name+'_refit_check/results.json')
        alias='pooled_'+name;add(alias,'analyze_pooled.py',['--panel',panel,'--site-forecasts','{OUT}/'+name+'/case-forecasts.csv.gz',*fitargs(fits)],expected=expected,files=['comparisons.csv','model-scores.csv']);aliases[alias]=alias
    for name,panel,forecast,expected in [('national',mainpanel,'extended','experiments/E082-national-growth-complete/results'),('nz',nzpanel,'nz','experiments/E083-nz-growth/results'),('site',sitepanel,'site','experiments/E084-site-growth/results')]:
        add('growth_'+name,'analyze_growth.py',['--panel',panel,'--forecast-csv','{OUT}/'+forecast+'/case-forecasts.csv.gz'],expected=expected,files=['growth-summary.csv','growth-paired.csv','roc-summary.csv'])
        args=['--panel',panel,'--growth','{OUT}/growth_'+name]
        if name=='national':args+=['--original-alerts','{OUT}/primary/alerts-paired.csv']
        add('growth_check_'+name,'verify_growth.py',args)
    for name,panel,forecast,expected,optional in [('national',mainpanel,'extended','experiments/E080-national-interval-correction/results',False),('nz',nzpanel,'nz','experiments/E085-nz-interval-correction/results',False),('site',sitepanel,'site','experiments/E086-site-interval-correction/results',True)]:
        alias='cqr_'+name;add(alias,'analyze_interval_calibration.py',['--panel',panel,'--forecast-csv','{OUT}/'+forecast+'/case-forecasts.csv.gz'],expected=expected,files=['comparisons.csv','model-scores.csv'],optional=optional);aliases[alias]=alias
    for name,panel,score_args,expected in [('national',mainpanel,['{OUT}/primary/case-scores.csv','{OUT}/extended/case-extra-scores.csv.gz'],'experiments/E093-national-freshness-interaction/results'),('nz',nzpanel,['{OUT}/nz/case-scores.csv.gz','{OUT}/pooled_nz/pooled-case-scores.csv.gz'],'experiments/E094-nz-freshness-interaction/results'),('site',sitepanel,['{OUT}/site/case-scores.csv.gz','{OUT}/pooled_site/pooled-case-scores.csv.gz'],'experiments/E095-site-freshness-interaction/results')]:
        alias='interaction_'+name;add(alias,'analyze_freshness_interaction.py',['--panel',panel,*[x for p in score_args for x in ['--scores',p]]],expected=expected,files=['comparisons.csv','four-prediction-availability.csv']);aliases[alias]=alias
        quality.append(dict(name={'national':'germany_national','site':'germany_sites','nz':'nz'}[name],panel=panel,scores=score_args))
    add('quality','analyze_input_quality.py',['--datasets','{OUT}/quality-datasets.json'],expected='experiments/E097-input-quality-case-provenance/results',files=['comparisons.csv','similarity-summary.csv']);aliases['quality']='quality'
    history_prep='experiments/E099-history-length-inputs-fixed'
    definitions=json.loads((ROOT/history_prep/'panels.json').read_text())
    add('temporal_history','verify_temporal.py',[x for d in definitions for x in ['--panel',d['panel']]],outfile='temporal_history/results.json')
    add('history_native','assemble_history_control.py',['--preparation',history_prep],expected='experiments/E138-history-native-assembly/results',files=[d['dataset']+'-'+str(d['maximum_context'])+'/model-scores.csv' for d in definitions])
    add('history','analyze_history_control.py',['--assembled','{OUT}/history_native','--original-map','{OUT}/history-original-scores.json'],expected='experiments/E139-history-matched-analysis/results',files=['comparisons.csv','availability.csv','original-short-compatibility.csv']);aliases['history']='history'
    add('joint','analyze_joint_comparisons.py',['--datasets','{OUT}/joint-comparison-datasets.json'],expected='experiments/E140-joint-comparison-sensitivity/results',files=['comparisons.csv','family-summary.csv']);aliases['joint']='joint'
    add('review_strata','analyze_review_strata.py',['--primary-dir','{OUT}/primary'],expected='experiments/E144-post-review-horizon-strata/results',files=['horizon-comparisons.csv','identity-weeks.csv','horizon-distribution.csv','pathogen-comparisons.csv','publication-gaps.csv','nz-publication-intervals.csv']);aliases['review_strata']='review_strata'
    add('figures','plot_results.py',['--manifest','{OUT}/report-manifest.json'])
    add('manuscript','render_paper.py',['--manifest','{OUT}/report-manifest.json'],outfile='')
    add('claims','verify_claims.py',['--results-manifest','{OUT}/report-manifest.json'],outfile='claims/results.json')
    add('comparison','compare_recalculation.py',outfile='')
    history_original_scores=dict(national=['{OUT}/primary/case-scores.csv','{OUT}/extended/case-extra-scores.csv.gz'],site=['{OUT}/site/case-scores.csv.gz','{OUT}/pooled_site/pooled-case-scores.csv.gz'],nz=['{OUT}/nz/case-scores.csv.gz','{OUT}/pooled_nz/pooled-case-scores.csv.gz'])
    joint_datasets=[dict(name=k,country='NZ' if k=='nz' else 'Germany',scores=[p for p in v if 'pooled_' not in p]) for k,v in history_original_scores.items()]
    quality.sort(key=lambda d:d['name'])
    cfg=dict(version=3,network_required=False,ai_api_required=False,report_aliases=aliases,quality_datasets=quality,history_original_scores=history_original_scores,joint_comparison_datasets=joint_datasets,steps=steps,compare_tables=compare,quick_omits=['cqr_site'],meaning='Offline saved-output recalculation plus local model/feature and limited first-week refit checks; not independent replication.')
    (ROOT/'config/reproduction.json').write_text(json.dumps(cfg,indent=2)+'\n');print(json.dumps(dict(steps=len(steps),tables=len(compare),aliases=len(aliases),quick_omits=cfg['quick_omits'])))

if __name__=='__main__':main()
