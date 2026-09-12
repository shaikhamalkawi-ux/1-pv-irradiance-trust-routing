from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / 'analysis' / 'run_srrl_midc_transfer.py'
CONFIG = ROOT / 'config' / 'srrl_midc_frozen_config.json'
OUT = ROOT / 'results' / 'srrl_closure_order_audit'
OUT.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location('base_transfer', BASE_PATH)
base = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(base)


def aggregate_series_with_completeness(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors='coerce')
    med10 = x.resample('10min').median()
    cnt10 = x.resample('10min').count()
    med10 = med10.where(cnt10 >= 5)
    med30 = med10.resample('30min').median()
    cnt30 = med10.resample('30min').count()
    return med30.where(cnt30 >= 2)


def normalized_residual(x: pd.Series, e: pd.Series, scale: float = 50.0) -> pd.Series:
    den = np.maximum((x.abs() + e.abs()) / 2.0, scale)
    return (x - e).abs() / den


def prepare_frame(native: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inst = cfg['instrument_lock']; ds = cfg['dataset']
    wanted = [inst['primary_column'], inst['secondary_column'], inst['dhi_column'], inst['dni_column']]
    agg = base.aggregate_with_completeness(native, wanted)
    rename = {inst['primary_column']:'primary', inst['secondary_column']:'secondary',
              inst['dhi_column']:'dhi', inst['dni_column']:'dni'}
    agg = agg.rename(columns=rename)

    # Existing implementation: solar geometry at 30-minute bin label.
    sol_left = pvlib.solarposition.get_solarposition(agg.index, ds['latitude'], ds['longitude'], ds['altitude_m'])
    agg['zenith_deg'] = sol_left['apparent_zenith'].to_numpy()
    agg['elevation_deg'] = sol_left['apparent_elevation'].to_numpy()
    agg['daylight'] = agg['elevation_deg'] >= cfg['aggregation']['solar_elevation_min_deg']
    agg['common_pair'] = agg['primary'].notna() & agg['secondary'].notna()
    agg['pair_mean'] = (agg['primary'] + agg['secondary']) / 2
    agg['split'] = np.select([
        (agg.index.date >= pd.Timestamp(ds['fit_start']).date()) & (agg.index.date <= pd.Timestamp(ds['fit_end']).date()),
        (agg.index.date >= pd.Timestamp(ds['calibration_start']).date()) & (agg.index.date <= pd.Timestamp(ds['calibration_end']).date()),
        (agg.index.date >= pd.Timestamp(ds['test_start']).date()) & (agg.index.date <= pd.Timestamp(ds['test_end']).date())],
        ['fit','calibration','test'], default='outside')
    agg['season'] = [base.season_for_month(m) for m in agg.index.month]
    agg['irr_bin'] = pd.cut(agg['pair_mean'], bins=cfg['irradiance_bins_wm2'],
                            labels=['50-200','200-500','500-800','>800'], right=False)

    # Alternative 1: aggregate components first, but use temporal midpoint solar geometry.
    mid_idx = agg.index + pd.Timedelta(minutes=15)
    sol_mid = pvlib.solarposition.get_solarposition(mid_idx, ds['latitude'], ds['longitude'], ds['altitude_m'])
    e_mid = agg['dhi'] + agg['dni'] * np.cos(np.deg2rad(sol_mid['apparent_zenith'].to_numpy()))
    midP = normalized_residual(agg['primary'], e_mid)
    midS = normalized_residual(agg['secondary'], e_mid)

    # Alternative 2: compute physical closure on native synchronized rows, then aggregate the residual.
    raw = native.rename(columns=rename).copy()
    sol_raw = pvlib.solarposition.get_solarposition(raw.index, ds['latitude'], ds['longitude'], ds['altitude_m'])
    e_raw = raw['dhi'] + raw['dni'] * np.cos(np.deg2rad(sol_raw['apparent_zenith'].to_numpy()))
    common_components = raw[['primary','secondary','dhi','dni']].notna().all(axis=1)
    rawP = normalized_residual(raw['primary'], e_raw).where(common_components)
    rawS = normalized_residual(raw['secondary'], e_raw).where(common_components)
    preP = aggregate_series_with_completeness(rawP).reindex(agg.index)
    preS = aggregate_series_with_completeness(rawS).reindex(agg.index)

    mid = pd.DataFrame({'primary':midP,'secondary':midS}, index=agg.index)
    pre = pd.DataFrame({'primary':preP,'secondary':preS}, index=agg.index)
    return agg, mid, pre


def closure_features(frame: pd.DataFrame, target: str, peer: str, closure_override: pd.Series | None):
    f = base.features_for_target(frame, target, peer, True)
    if closure_override is not None:
        f['closure'] = closure_override
    return f


def run_variant(frame: pd.DataFrame, cfg: dict, label: str, closure_override: pd.DataFrame | None):
    features = ['pair','dynamic','stuck','closure']
    fit_mask = frame['split'].eq('fit') & frame['common_pair'] & frame['daylight']
    cal_mask = frame['split'].eq('calibration') & frame['common_pair'] & frame['daylight']
    test_mask = frame['split'].eq('test') & frame['common_pair'] & frame['daylight']

    featP = closure_features(frame, 'primary', 'secondary', None if closure_override is None else closure_override['primary'])[features]
    featS = closure_features(frame, 'secondary', 'primary', None if closure_override is None else closure_override['secondary'])[features]
    fitP,_ = base.fit_memberships(featP, fit_mask, cfg, 'primary', label)
    fitS,_ = base.fit_memberships(featS, fit_mask, cfg, 'secondary', label)
    scoreP = base.infer_scores(featP, fitP, cfg['rule_consequents'])
    scoreS = base.infer_scores(featS, fitS, cfg['rule_consequents'])

    thresholds = {}
    for sensor,score in [('primary',scoreP),('secondary',scoreS)]:
        for route,col in [('type1','type1_trust'),('center','it2_center'),('lower','it2_low')]:
            thresholds[f'{sensor}_{route}'] = base.q95_threshold(1-score.loc[cal_mask,col], cfg['alert_quantile'])

    rows=[]
    test_idx = frame.index[test_mask]
    for sensor,score in [('primary',scoreP),('secondary',scoreS)]:
        row={'variant':label,'sensor':sensor,'n_test':len(test_idx)}
        for route,col in [('type1','type1_trust'),('center','it2_center'),('lower','it2_low')]:
            alert = (1-score.loc[test_idx,col]) > thresholds[f'{sensor}_{route}']
            row[f'{route}_alert_rate'] = float(alert.mean())
        row['median_center_trust'] = float(score.loc[test_idx,'it2_center'].median())
        row['median_width'] = float((score.loc[test_idx,'it2_high']-score.loc[test_idx,'it2_low']).median())
        rows.append(row)
    return pd.DataFrame(rows), thresholds, {'primary':fitP,'secondary':fitS}


def summarize_feature_change(frame: pd.DataFrame, alt: pd.DataFrame, label: str):
    out=[]
    for sensor,peer in [('primary','secondary'),('secondary','primary')]:
        baseline = base.features_for_target(frame,sensor,peer,True)['closure']
        x = pd.concat([baseline.rename('baseline'), alt[sensor].rename('alternative')],axis=1).dropna()
        d=(x['alternative']-x['baseline']).abs()
        out.append({'variant':label,'sensor':sensor,'n_common':len(x),
                    'baseline_median':float(x.baseline.median()),
                    'alternative_median':float(x.alternative.median()),
                    'median_abs_change':float(d.median()),'p95_abs_change':float(d.quantile(.95)),
                    'max_abs_change':float(d.max()),'pearson':float(x.corr().iloc[0,1])})
    return out


def main():
    cfg=json.loads(CONFIG.read_text())
    inst=cfg['instrument_lock']; ds=cfg['dataset']
    wanted=[inst['primary_column'],inst['secondary_column'],inst['dhi_column'],inst['dni_column']]
    monthly=[]; ledger=[]
    for ms,me in base.month_windows(ds['main_start'],ds['main_end']):
        print(f'ACQUIRE {ms.date()}..{me.date()}', flush=True)
        raw=base.safe_fetch(ds['site'],ms,me)
        missing=[c for c in wanted if c not in raw.columns]
        if missing: raise RuntimeError(f'Missing required channels {ms.date()}: {missing}')
        selected=raw[wanted].copy()
        h,nbytes=base.canonical_csv_hash(selected)
        ledger.append({'start':str(ms.date()),'end':str(me.date()),'rows':len(selected),
                       'sha256':h,'bytes':nbytes,'first':str(selected.index.min()),'last':str(selected.index.max())})
        monthly.append(selected)
    native=pd.concat(monthly).sort_index()
    native=native.loc[~native.index.duplicated(keep='first')]
    pd.DataFrame(ledger).to_json(OUT/'source_ledger.json',orient='records',indent=2)

    frame, mid, pre = prepare_frame(native,cfg)
    feat_rows=[]
    feat_rows += summarize_feature_change(frame,mid,'aggregate_components_midpoint_geometry')
    feat_rows += summarize_feature_change(frame,pre,'native_support_closure_then_aggregate')
    pd.DataFrame(feat_rows).to_csv(OUT/'closure_feature_comparison.csv',index=False)

    all_metrics=[]; summaries={}
    for label,override in [('baseline_locked',None),
                           ('aggregate_components_midpoint_geometry',mid),
                           ('native_support_closure_then_aggregate',pre)]:
        print('RUN',label,flush=True)
        metrics,thr,membership=run_variant(frame,cfg,label,override)
        all_metrics.append(metrics)
        summaries[label]={'thresholds':thr,'membership':membership}
    metrics=pd.concat(all_metrics,ignore_index=True)
    metrics.to_csv(OUT/'route_metrics_by_closure_definition.csv',index=False)
    (OUT/'variant_summaries.json').write_text(json.dumps(summaries,indent=2))

    base_rows=metrics[metrics.variant.eq('baseline_locked')].set_index('sensor')
    pre_rows=metrics[metrics.variant.eq('native_support_closure_then_aggregate')].set_index('sensor')
    decision={
      'audit_scope':'Post-baseline implementation audit; does not alter AC4 unless a material result change is verified.',
      'source_period':[ds['main_start'],ds['main_end']],
      'native_rows':int(len(native)),
      'aggregated_rows':int(len(frame)),
      'baseline_center_rates':base_rows['center_alert_rate'].to_dict(),
      'native_first_center_rates':pre_rows['center_alert_rate'].to_dict(),
      'absolute_center_rate_changes':(pre_rows['center_alert_rate']-base_rows['center_alert_rate']).abs().to_dict(),
      'materiality_rule':'Flag for manuscript correction if closure-order choice changes the qualitative external-boundary conclusion or changes either sensor center-alert rate by >=1 percentage point absolute.',
    }
    maxchg=max(decision['absolute_center_rate_changes'].values())
    bdiff=abs(base_rows.loc['primary','center_alert_rate']-base_rows.loc['secondary','center_alert_rate'])
    pdiff=abs(pre_rows.loc['primary','center_alert_rate']-pre_rows.loc['secondary','center_alert_rate'])
    decision['baseline_sensor_gap']=float(bdiff); decision['native_first_sensor_gap']=float(pdiff)
    decision['materiality_flag']=bool(maxchg>=0.01 or ((bdiff<0.01)!=(pdiff<0.01)))
    (OUT/'CONTRIBUTION_DECISION.json').write_text(json.dumps(decision,indent=2))
    print(json.dumps(decision,indent=2))

if __name__=='__main__':
    main()
