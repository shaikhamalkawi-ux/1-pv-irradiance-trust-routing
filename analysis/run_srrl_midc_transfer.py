from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
from pvlib.iotools import read_midc_raw_data_from_nrel

ROOT = Path(__file__).resolve().parents[1] if 'analysis' in Path(__file__).parts else Path.cwd()
CONFIG = ROOT / 'config' / 'srrl_midc_frozen_config.json'
OUT = ROOT / 'results' / 'srrl_midc_transfer'
OUT.mkdir(parents=True, exist_ok=True)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_fetch(site: str, start: pd.Timestamp, end: pd.Timestamp, depth: int = 0) -> pd.DataFrame:
    """Fetch inclusive date window; split recursively when MIDC rejects a window."""
    last_err = None
    for attempt in range(3):
        try:
            return read_midc_raw_data_from_nrel(site, start, end, timeout=120)
        except Exception as exc:
            last_err = exc
            time.sleep(2 ** attempt)
    if start.normalize() >= end.normalize():
        raise RuntimeError(f'MIDC acquisition failed for {start.date()}: {last_err}')
    mid = start.normalize() + pd.Timedelta(days=(end.normalize() - start.normalize()).days // 2)
    left = safe_fetch(site, start.normalize(), mid, depth + 1)
    right_start = mid + pd.Timedelta(days=1)
    right = safe_fetch(site, right_start, end.normalize(), depth + 1)
    return pd.concat([left, right]).sort_index().loc[lambda x: ~x.index.duplicated(keep='first')]


def month_windows(start: str, end: str):
    s = pd.Timestamp(start).normalize()
    e = pd.Timestamp(end).normalize()
    for ms in pd.date_range(s.replace(day=1), e.replace(day=1), freq='MS'):
        me = (ms + pd.offsets.MonthEnd(1)).normalize()
        yield max(ms, s), min(me, e)


def canonical_csv_hash(df: pd.DataFrame) -> tuple[str, int]:
    b = df.to_csv(index=True, float_format='%.10g').encode('utf-8')
    return sha256_bytes(b), len(b)


def aggregate_with_completeness(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    numeric = df[cols].apply(pd.to_numeric, errors='coerce')
    med10 = numeric.resample('10min').median()
    cnt10 = numeric.resample('10min').count()
    med10 = med10.where(cnt10 >= 5)
    med30 = med10.resample('30min').median()
    cnt30 = med10.resample('30min').count()
    med30 = med30.where(cnt30 >= 2)
    return med30


def season_for_month(m: int) -> str:
    if m in (12, 1, 2): return 'DJF'
    if m in (3, 4, 5): return 'MAM'
    if m in (6, 7, 8): return 'JJA'
    return 'SON'


def features_for_target(frame: pd.DataFrame, target: str, peer: str, closure_ok: bool) -> pd.DataFrame:
    s = 50.0
    x = frame[target].astype(float)
    y = frame[peer].astype(float)
    out = pd.DataFrame(index=frame.index)
    out['pair'] = (x - y).abs() / np.maximum((x.abs() + y.abs()) / 2.0, s)

    dx = x.diff(); dy = y.diff()
    contiguous_prev = frame.index.to_series().diff().eq(pd.Timedelta(minutes=30)).to_numpy()
    dyn = (dx - dy).abs() / np.maximum((dx.abs() + dy.abs()) / 2.0, s / 2.0)
    out['dynamic'] = dyn.where(contiguous_prev)

    prev_ok = frame.index.to_series().diff().eq(pd.Timedelta(minutes=30))
    next_ok = frame.index.to_series().shift(-1).sub(frame.index.to_series()).eq(pd.Timedelta(minutes=30))
    ri = pd.concat([x.shift(1), x, x.shift(-1)], axis=1).max(axis=1) - pd.concat([x.shift(1), x, x.shift(-1)], axis=1).min(axis=1)
    rj = pd.concat([y.shift(1), y, y.shift(-1)], axis=1).max(axis=1) - pd.concat([y.shift(1), y, y.shift(-1)], axis=1).min(axis=1)
    stuck = np.exp(-ri / (s / 4.0)) * np.minimum(rj / s, 1.0)
    out['stuck'] = stuck.where(prev_ok & next_ok)

    if closure_ok:
        z = frame['zenith_deg'].astype(float)
        e = frame['dhi'].astype(float) + frame['dni'].astype(float) * np.cos(np.deg2rad(z))
        out['closure'] = (x - e).abs() / np.maximum((x.abs() + e.abs()) / 2.0, s)
    return out


def fit_memberships(feat: pd.DataFrame, fit_mask: pd.Series, cfg: dict, sensor: str, model_label: str):
    mq = cfg['membership']
    monthly_rows = []
    fitted = {}
    for f in feat.columns:
        vals = feat.loc[fit_mask, f].replace([np.inf, -np.inf], np.nan)
        month_stats = []
        for month in range(1, 13):
            v = vals[vals.index.month == month].dropna()
            if len(v) == 0:
                continue
            a = float(v.quantile(mq['monthly_onset_quantile']))
            b = float(v.quantile(mq['monthly_full_quantile']))
            month_stats.append((month, a, b, len(v)))
            monthly_rows.append({'model':model_label,'sensor':sensor,'feature':f,'month':month,'n':len(v),'a75':a,'b975':b})
        if len(month_stats) < mq['min_fit_months']:
            raise RuntimeError(f'Only {len(month_stats)} fit months for {sensor}/{model_label}/{f}')
        aa = np.array([r[1] for r in month_stats]); bb = np.array([r[2] for r in month_stats])
        aL = float(np.quantile(aa, mq['across_month_lower_quantile']))
        aU = float(np.quantile(aa, mq['across_month_upper_quantile']))
        bL = float(np.quantile(bb, mq['across_month_lower_quantile']))
        bU = float(np.quantile(bb, mq['across_month_upper_quantile']))
        if min(bL-aL, bU-aU) <= 0:
            raise RuntimeError(f'Invalid ramp ordering for {sensor}/{model_label}/{f}')
        fitted[f] = {'aL':aL,'aU':aU,'bL':bL,'bU':bU,'aM':(aL+aU)/2,'bM':(bL+bU)/2}
    return fitted, monthly_rows


def ramp(x: np.ndarray, a: float, b: float) -> np.ndarray:
    out = (x-a)/(b-a)
    return np.clip(out, 0.0, 1.0)


def km_endpoint(consequents: np.ndarray, wl: np.ndarray, wu: np.ndarray, left: bool) -> float:
    order = np.argsort(consequents)
    y = consequents[order]; l = wl[order]; u = wu[order]
    if np.nansum(u) <= 0: return 0.5
    w = (l+u)/2.0
    cur = float(np.sum(y*w)/np.sum(w))
    for _ in range(100):
        k = int(np.searchsorted(y, cur, side='right') - 1)
        k = max(-1, min(k, len(y)-1))
        idx = np.arange(len(y))
        if left:
            ww = np.where(idx <= k, u, l)
        else:
            ww = np.where(idx <= k, l, u)
        if ww.sum() <= 0: return cur
        nxt = float(np.sum(y*ww)/np.sum(ww))
        if abs(nxt-cur) < 1e-12: return nxt
        cur = nxt
    return cur


def build_rules(feature_names: list[str], c: dict):
    rules = []
    rules.append(('all_low', [('low', f) for f in feature_names], c['all_low']))
    singles = {'pair':'pair_high','closure':'closure_high','dynamic':'dynamic_high','stuck':'stuck_high'}
    for f in feature_names:
        if f in singles: rules.append((f'{f}_high',[('high',f)],c[singles[f]]))
    pairs = [
        ('pair_closure','pair','closure'),('pair_dynamic','pair','dynamic'),
        ('closure_stuck','closure','stuck'),('pair_stuck','pair','stuck')]
    for name,a,b in pairs:
        if a in feature_names and b in feature_names:
            rules.append((name,[('high',a),('high',b)],c[name]))
    return rules


def infer_scores(feat: pd.DataFrame, fitted: dict, c: dict) -> pd.DataFrame:
    names = list(fitted)
    if len(names) < 2:
        return pd.DataFrame({'type1_trust':0.5,'it2_low':0.5,'it2_high':0.5,'it2_center':0.5}, index=feat.index)
    rules = build_rules(names,c)
    result=[]
    for idx,row in feat[names].iterrows():
        if row.notna().sum() < 2:
            result.append((0.5,0.5,0.5,0.5)); continue
        hiL={}; hiU={}; hiM={}
        for f in names:
            v=row[f]
            if pd.isna(v):
                hiL[f]=hiU[f]=hiM[f]=np.nan; continue
            p=fitted[f]
            lo=float(ramp(np.array([v]),p['aU'],p['bU'])[0])
            up=float(ramp(np.array([v]),p['aL'],p['bL'])[0])
            if lo > up + 1e-10:
                lo,up=min(lo,up),max(lo,up)
            hiL[f],hiU[f]=lo,up
            hiM[f]=float(ramp(np.array([v]),p['aM'],p['bM'])[0])
        ys=[]; wls=[]; wus=[]; wms=[]
        for name,ants,cons in rules:
            if any(pd.isna(hiM[f]) for _,f in ants):
                continue
            ls=[]; us=[]; ms=[]
            for state,f in ants:
                if state=='high':
                    ls.append(hiL[f]); us.append(hiU[f]); ms.append(hiM[f])
                else:
                    ls.append(1-hiU[f]); us.append(1-hiL[f]); ms.append(1-hiM[f])
            ys.append(float(cons)); wls.append(min(ls)); wus.append(min(us)); wms.append(min(ms))
        if not ys or sum(wms)<=0:
            result.append((0.5,0.5,0.5,0.5)); continue
        ya=np.array(ys); la=np.array(wls); ua=np.array(wus); ma=np.array(wms)
        t1=float(np.sum(ya*ma)/np.sum(ma))
        tl=km_endpoint(ya,la,ua,True); tu=km_endpoint(ya,la,ua,False)
        if tl>tu: tl,tu=tu,tl
        result.append((t1,tl,tu,(tl+tu)/2.0))
    return pd.DataFrame(result,index=feat.index,columns=['type1_trust','it2_low','it2_high','it2_center'])


def q95_threshold(scores: pd.Series, q: float) -> float:
    return float(scores.dropna().quantile(q))


def interval(vals: np.ndarray) -> list[float]:
    return [float(np.quantile(vals,.025)), float(np.quantile(vals,.975))]


def date_cluster_bootstrap(test: pd.DataFrame, reps: int, seed: int) -> dict:
    rng=np.random.default_rng(seed)
    dates=np.array(sorted(test['date'].unique()))
    bydate={d:test.index[test['date'].eq(d)].to_numpy() for d in dates}
    cols_alert=['primary_center_alert','secondary_center_alert','primary_lower_alert','secondary_lower_alert']
    out={k:[] for k in ['primary_center','secondary_center','primary_minus_secondary','primary_center_minus_lower','secondary_center_minus_lower','primary_width_median','secondary_width_median']}
    for _ in range(reps):
        pick=rng.choice(dates,size=len(dates),replace=True)
        idx=np.concatenate([bydate[d] for d in pick])
        x=test.loc[idx]
        p=float(x['primary_center_alert'].mean()); s=float(x['secondary_center_alert'].mean())
        pl=float(x['primary_lower_alert'].mean()); sl=float(x['secondary_lower_alert'].mean())
        out['primary_center'].append(p); out['secondary_center'].append(s); out['primary_minus_secondary'].append(p-s)
        out['primary_center_minus_lower'].append(p-pl); out['secondary_center_minus_lower'].append(s-sl)
        out['primary_width_median'].append(float(x['primary_width'].median())); out['secondary_width_median'].append(float(x['secondary_width'].median()))
    return {k:{'point':None,'ci95':interval(np.array(v))} for k,v in out.items()}


def run_model(frame: pd.DataFrame, cfg: dict, model_label: str, features: list[str]) -> tuple[dict,pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    fit_mask=frame['split'].eq('fit') & frame['common_pair'] & frame['daylight']
    cal_mask=frame['split'].eq('calibration') & frame['common_pair'] & frame['daylight']
    test_mask=frame['split'].eq('test') & frame['common_pair'] & frame['daylight']
    featP=features_for_target(frame,'primary','secondary','closure' in features)[features]
    featS=features_for_target(frame,'secondary','primary','closure' in features)[features]
    fitP, rowsP=fit_memberships(featP,fit_mask,cfg,'primary',model_label)
    fitS, rowsS=fit_memberships(featS,fit_mask,cfg,'secondary',model_label)
    scoreP=infer_scores(featP,fitP,cfg['rule_consequents'])
    scoreS=infer_scores(featS,fitS,cfg['rule_consequents'])

    thresholds={}
    for sensor,score in [('primary',scoreP),('secondary',scoreS)]:
        for route,col in [('type1','type1_trust'),('center','it2_center'),('lower','it2_low')]:
            thresholds[f'{sensor}_{route}']=q95_threshold(1-score.loc[cal_mask,col],cfg['alert_quantile'])

    test=frame.loc[test_mask,['primary','secondary','pair_mean','season','irr_bin']].copy()
    test['date']=test.index.date
    for sensor,score in [('primary',scoreP),('secondary',scoreS)]:
        test[f'{sensor}_type1_trust']=score.loc[test.index,'type1_trust']
        test[f'{sensor}_center']=score.loc[test.index,'it2_center']
        test[f'{sensor}_low']=score.loc[test.index,'it2_low']
        test[f'{sensor}_high']=score.loc[test.index,'it2_high']
        test[f'{sensor}_width']=test[f'{sensor}_high']-test[f'{sensor}_low']
        for route,tcol in [('type1','type1_trust'),('center','it2_center'),('lower','it2_low')]:
            test[f'{sensor}_{route}_alert']=(1-score.loc[test.index,tcol]) > thresholds[f'{sensor}_{route}']

    aggregate=[]
    for sensor in ['primary','secondary']:
        aggregate.append({
            'model':model_label,'sensor':sensor,'n_test':len(test),
            'type1_alert_rate':float(test[f'{sensor}_type1_alert'].mean()),
            'it2_center_alert_rate':float(test[f'{sensor}_center_alert'].mean()),
            'it2_lower_alert_rate':float(test[f'{sensor}_lower_alert'].mean()),
            'median_center_trust':float(test[f'{sensor}_center'].median()),
            'median_interval_width':float(test[f'{sensor}_width'].median()),
            'center_lower_alert_disagreement':float((test[f'{sensor}_center_alert']!=test[f'{sensor}_lower_alert']).mean()),
        })
    aggregate_df=pd.DataFrame(aggregate)

    detail=[]
    for sensor in ['primary','secondary']:
        for dim in ['season','irr_bin']:
            for key,g in test.groupby(dim,dropna=False):
                detail.append({'model':model_label,'sensor':sensor,'dimension':dim,'level':str(key),'n':len(g),
                               'center_alert_rate':float(g[f'{sensor}_center_alert'].mean()),
                               'lower_alert_rate':float(g[f'{sensor}_lower_alert'].mean()),
                               'median_center_trust':float(g[f'{sensor}_center'].median()),
                               'median_width':float(g[f'{sensor}_width'].median())})
    detail_df=pd.DataFrame(detail)

    boot=date_cluster_bootstrap(test,cfg['bootstrap']['replicates'],cfg['bootstrap']['seed'])
    points={
        'primary_center':float(test['primary_center_alert'].mean()),
        'secondary_center':float(test['secondary_center_alert'].mean()),
        'primary_minus_secondary':float(test['primary_center_alert'].mean()-test['secondary_center_alert'].mean()),
        'primary_center_minus_lower':float(test['primary_center_alert'].mean()-test['primary_lower_alert'].mean()),
        'secondary_center_minus_lower':float(test['secondary_center_alert'].mean()-test['secondary_lower_alert'].mean()),
        'primary_width_median':float(test['primary_width'].median()),
        'secondary_width_median':float(test['secondary_width'].median()),
    }
    for k,v in points.items(): boot[k]['point']=v
    summary={'model':model_label,'features':features,'thresholds':thresholds,'membership':{'primary':fitP,'secondary':fitS},'bootstrap':boot}
    monthly=pd.DataFrame(rowsP+rowsS)
    return summary,test,aggregate_df,pd.concat([detail_df,monthly.assign(dimension='membership_month',level=monthly['month'].astype(str))],ignore_index=True,sort=False)


def main():
    cfg=json.loads(CONFIG.read_text())
    inst=cfg['instrument_lock']; ds=cfg['dataset']
    wanted=[inst['primary_column'],inst['secondary_column'],inst['dhi_column'],inst['dni_column']]
    monthly=[]; ledger=[]; closure_all=True
    for ms,me in month_windows(ds['main_start'],ds['main_end']):
        print(f'ACQUIRE {ms.date()}..{me.date()}',flush=True)
        raw=safe_fetch(ds['site'],ms,me)
        missing=[c for c in [inst['primary_column'],inst['secondary_column']] if c not in raw.columns]
        if missing: raise RuntimeError(f'Required channel(s) missing {ms.date()}: {missing}')
        closure_present=all(c in raw.columns for c in [inst['dhi_column'],inst['dni_column']])
        closure_all &= closure_present
        keep=[c for c in wanted if c in raw.columns]
        selected=raw[keep].copy()
        h,nbytes=canonical_csv_hash(selected)
        ledger.append({'start':str(ms.date()),'end':str(me.date()),'rows':len(selected),'columns':keep,'canonical_selected_csv_sha256':h,'canonical_selected_csv_bytes':nbytes,'closure_present':closure_present,'first_index':str(selected.index.min()),'last_index':str(selected.index.max())})
        monthly.append(selected)
    native=pd.concat(monthly).sort_index()
    native=native.loc[~native.index.duplicated(keep='first')]
    agg=aggregate_with_completeness(native,wanted if closure_all else wanted[:2])
    rename={inst['primary_column']:'primary',inst['secondary_column']:'secondary',inst['dhi_column']:'dhi',inst['dni_column']:'dni'}
    agg=agg.rename(columns=rename)

    sol=pvlib.solarposition.get_solarposition(agg.index,ds['latitude'],ds['longitude'],ds['altitude_m'])
    agg['zenith_deg']=sol['apparent_zenith'].to_numpy(); agg['elevation_deg']=sol['apparent_elevation'].to_numpy()
    agg['daylight']=agg['elevation_deg']>=cfg['aggregation']['solar_elevation_min_deg']
    agg['common_pair']=agg['primary'].notna() & agg['secondary'].notna()
    agg['pair_mean']=(agg['primary']+agg['secondary'])/2
    agg['split']=np.select([
        (agg.index.date>=pd.Timestamp(ds['fit_start']).date()) & (agg.index.date<=pd.Timestamp(ds['fit_end']).date()),
        (agg.index.date>=pd.Timestamp(ds['calibration_start']).date()) & (agg.index.date<=pd.Timestamp(ds['calibration_end']).date()),
        (agg.index.date>=pd.Timestamp(ds['test_start']).date()) & (agg.index.date<=pd.Timestamp(ds['test_end']).date())],['fit','calibration','test'],default='outside')
    agg['season']=[season_for_month(m) for m in agg.index.month]
    bins=cfg['irradiance_bins_wm2']
    labels=['50-200','200-500','500-800','>800']
    agg['irr_bin']=pd.cut(agg['pair_mean'],bins=bins,labels=labels,right=False)

    theoretical=agg.loc[agg['split'].eq('fit') & agg['daylight']].groupby(agg.index.month).size()
    admitted=agg.loc[agg['split'].eq('fit') & agg['daylight'] & agg['common_pair']].groupby(agg.index.month).size()
    coverage=pd.DataFrame({'theoretical_daylight_slots':theoretical,'common_pair_records':admitted}).fillna(0)
    coverage['coverage_fraction']=coverage['common_pair_records']/coverage['theoretical_daylight_slots']
    coverage.index.name='month'
    good_months=int((coverage['coverage_fraction']>=cfg['membership']['min_fit_month_daylight_coverage_fraction']).sum())
    ncal=int((agg['split'].eq('calibration') & agg['daylight'] & agg['common_pair']).sum())
    ntest=int((agg['split'].eq('test') & agg['daylight'] & agg['common_pair']).sum())
    stop=[]
    if good_months<cfg['membership']['min_fit_months']: stop.append(f'fit_month_coverage:{good_months}')
    if ncal<cfg['min_common_support_calibration']: stop.append(f'calibration_common_support:{ncal}')
    if ntest<cfg['min_common_support_test']: stop.append(f'test_common_support:{ntest}')

    pd.DataFrame(ledger).to_json(OUT/'source_acquisition_ledger.json',orient='records',indent=2)
    coverage.to_csv(OUT/'fit_month_coverage.csv')
    qa={'protocol_id':cfg['protocol_id'],'closure_available_full_interval':bool(closure_all),'aggregated_rows':len(agg),'fit_good_months':good_months,'calibration_common_support':ncal,'test_common_support':ntest,'stop_reasons':stop}
    (OUT/'admission_qa.json').write_text(json.dumps(qa,indent=2))
    if stop:
        (OUT/'contribution_decision.json').write_text(json.dumps({'stop_rules_pass':False,'stop_reasons':stop,'candidate_main_paper_external_result':False},indent=2))
        print(json.dumps(qa,indent=2)); return

    models=[]
    primary_features=['pair','dynamic','stuck']+(['closure'] if closure_all else [])
    models.append(('full_common_evidence',primary_features))
    models.append(('pair_only_sensitivity',['pair','dynamic','stuck']))
    all_test=[]; all_agg=[]; all_detail=[]; summaries={}
    for label,features in models:
        print('MODEL',label,features,flush=True)
        summary,test,aggregate,detail=run_model(agg,cfg,label,features)
        summaries[label]=summary
        t=test.copy(); t.insert(0,'model',label); all_test.append(t.reset_index(names='timestamp'))
        all_agg.append(aggregate); all_detail.append(detail)
    test_df=pd.concat(all_test,ignore_index=True); aggregate_df=pd.concat(all_agg,ignore_index=True); detail_df=pd.concat(all_detail,ignore_index=True)
    test_df.to_csv(OUT/'test_scores_and_routes.csv.gz',index=False,compression='gzip')
    aggregate_df.to_csv(OUT/'aggregate_transfer_metrics.csv',index=False)
    detail_df.to_csv(OUT/'operating_and_membership_detail.csv',index=False)
    (OUT/'model_summaries.json').write_text(json.dumps(summaries,indent=2))

    full=aggregate_df[aggregate_df.model.eq('full_common_evidence')].set_index('sensor')
    sens=aggregate_df[aggregate_df.model.eq('pair_only_sensitivity')].set_index('sensor')
    direction_primary=np.sign(full.loc['primary','it2_center_alert_rate']-0.05)==np.sign(sens.loc['primary','it2_center_alert_rate']-0.05)
    direction_secondary=np.sign(full.loc['secondary','it2_center_alert_rate']-0.05)==np.sign(sens.loc['secondary','it2_center_alert_rate']-0.05)
    decision={
        'stop_rules_pass':True,'stop_reasons':[],
        'closure_available_full_interval':bool(closure_all),
        'primary_model_label':'full_common_evidence' if closure_all else 'pair_only_sensitivity',
        'rule_engine_exact_qatar_replay':False,
        'rule_engine_label':cfg['rule_engine']['label'],
        'sensitivity_direction_retained_vs_5pct':{'primary':bool(direction_primary),'secondary':bool(direction_secondary)},
        'candidate_for_contribution_review':bool(direction_primary and direction_secondary),
        'main_paper_admission_requires_interpretive_review':True,
        'external_fault_validation_performed':False,
        'claim_boundary':'Sensor/operating-point transfer only; no physical-fault validation and no reference-grade calibration claim.'
    }
    (OUT/'contribution_decision.json').write_text(json.dumps(decision,indent=2))
    env={'python':sys.version,'platform':platform.platform(),'pandas':pd.__version__,'numpy':np.__version__,'pvlib':pvlib.__version__}
    (OUT/'environment.json').write_text(json.dumps(env,indent=2))
    agg.loc[:,['primary','secondary'] + (['dhi','dni'] if closure_all else []) + ['zenith_deg','elevation_deg','daylight','common_pair','pair_mean','split','season','irr_bin']].to_csv(OUT/'aggregated_input_30min.csv.gz',compression='gzip')

    manifest=[]
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name!='SHA256_MANIFEST.json':
            manifest.append({'file':p.name,'bytes':p.stat().st_size,'sha256':sha256_file(p)})
    (OUT/'SHA256_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'qa':qa,'decision':decision,'aggregate':aggregate_df.to_dict(orient='records')},indent=2))

if __name__=='__main__':
    main()
