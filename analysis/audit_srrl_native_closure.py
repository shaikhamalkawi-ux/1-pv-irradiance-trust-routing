from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

import analysis.run_srrl_midc_transfer as base

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / 'config' / 'srrl_midc_frozen_config.json').read_text())
OUT = ROOT / 'results' / 'srrl_native_closure_audit'
OUT.mkdir(parents=True, exist_ok=True)


def aggregate_common_native_residual(native: pd.DataFrame, target: str, cfg: dict) -> pd.Series:
    """Compute closure residual on synchronized native rows first, then aggregate.

    Uses the same normalized absolute residual definition as the locked transfer,
    but evaluates GHI = DHI + DNI*cos(zenith) before temporal aggregation.
    Completeness is enforced on common native support across GHI target, DHI and DNI.
    """
    ds = cfg['dataset']
    s = float(cfg['feature_scales_wm2']['ghi'])
    cols = [target, 'dhi', 'dni']
    common = native[cols].apply(pd.to_numeric, errors='coerce').dropna()
    if common.empty:
        raise RuntimeError('No synchronized native support for closure audit')

    sol = pvlib.solarposition.get_solarposition(
        common.index, ds['latitude'], ds['longitude'], ds['altitude_m']
    )
    z = sol['apparent_zenith'].astype(float)
    e = common['dhi'] + common['dni'] * np.cos(np.deg2rad(z.to_numpy()))
    x = common[target]
    residual = (x - e).abs() / np.maximum((x.abs() + e.abs()) / 2.0, s)
    residual.name = 'closure_native_first'

    # Mirror the locked two-stage completeness thresholds, but on common support.
    r10 = residual.resample('10min').median()
    c10 = residual.resample('10min').count()
    r10 = r10.where(c10 >= int(cfg['aggregation']['stage1_min_native']))
    r30 = r10.resample('30min').median()
    c30 = r10.resample('30min').count()
    r30 = r30.where(c30 >= int(cfg['aggregation']['stage2_min_stage1']))
    return r30


def fit_and_route(feat: pd.DataFrame, agg: pd.DataFrame, sensor: str, label: str, cfg: dict):
    fit_mask = agg['split'].eq('fit') & agg['daylight'] & agg['common_pair']
    cal_mask = agg['split'].eq('calibration') & agg['daylight'] & agg['common_pair']
    test_mask = agg['split'].eq('test') & agg['daylight'] & agg['common_pair']

    fitted, _ = base.fit_memberships(feat, fit_mask, cfg, sensor, label)
    score = base.infer_scores(feat, fitted, cfg['rule_consequents'])
    threshold = base.q95_threshold(1.0 - score.loc[cal_mask, 'it2_center'], cfg['alert_quantile'])
    test_score = score.loc[test_mask, 'it2_center']
    alert = (1.0 - test_score) > threshold
    return {
        'threshold': float(threshold),
        'n_test': int(test_mask.sum()),
        'alert_rate': float(alert.mean()),
        'median_center_trust': float(test_score.median()),
        'score': score,
        'test_mask': test_mask,
        'alert': alert,
    }


def main():
    cfg = CFG
    ds = cfg['dataset']
    inst = cfg['instrument_lock']
    source_cols = [
        inst['primary_column'], inst['secondary_column'],
        inst['dhi_column'], inst['dni_column']
    ]

    monthly = []
    acquisition = []
    for ms, me in base.month_windows(ds['main_start'], ds['main_end']):
        print(f'ACQUIRE {ms.date()}..{me.date()}', flush=True)
        raw = base.safe_fetch(ds['site'], ms, me)
        missing = [c for c in source_cols if c not in raw.columns]
        if missing:
            raise RuntimeError(f'Missing required channel(s) {missing} for {ms.date()}')
        selected = raw[source_cols].copy()
        h, nbytes = base.canonical_csv_hash(selected)
        acquisition.append({
            'start': str(ms.date()), 'end': str(me.date()), 'rows': int(len(selected)),
            'canonical_selected_csv_sha256': h, 'canonical_selected_csv_bytes': int(nbytes),
            'first_index': str(selected.index.min()), 'last_index': str(selected.index.max()),
        })
        monthly.append(selected)

    native = pd.concat(monthly).sort_index()
    native = native.loc[~native.index.duplicated(keep='first')]
    rename = {
        inst['primary_column']: 'primary', inst['secondary_column']: 'secondary',
        inst['dhi_column']: 'dhi', inst['dni_column']: 'dni'
    }
    native = native.rename(columns=rename)

    # Locked aggregate-first representation.
    agg = base.aggregate_with_completeness(native, ['primary', 'secondary', 'dhi', 'dni'])
    sol = pvlib.solarposition.get_solarposition(
        agg.index, ds['latitude'], ds['longitude'], ds['altitude_m']
    )
    agg['zenith_deg'] = sol['apparent_zenith'].to_numpy()
    agg['elevation_deg'] = sol['apparent_elevation'].to_numpy()
    agg['daylight'] = agg['elevation_deg'] >= cfg['aggregation']['solar_elevation_min_deg']
    agg['common_pair'] = agg['primary'].notna() & agg['secondary'].notna()
    agg['split'] = np.select([
        (agg.index.date >= pd.Timestamp(ds['fit_start']).date()) & (agg.index.date <= pd.Timestamp(ds['fit_end']).date()),
        (agg.index.date >= pd.Timestamp(ds['calibration_start']).date()) & (agg.index.date <= pd.Timestamp(ds['calibration_end']).date()),
        (agg.index.date >= pd.Timestamp(ds['test_start']).date()) & (agg.index.date <= pd.Timestamp(ds['test_end']).date()),
    ], ['fit', 'calibration', 'test'], default='outside')

    native_first = {
        sensor: aggregate_common_native_residual(native, sensor, cfg).reindex(agg.index)
        for sensor in ['primary', 'secondary']
    }

    rows = []
    route_rows = []
    for sensor, peer in [('primary', 'secondary'), ('secondary', 'primary')]:
        feat_locked = base.features_for_target(agg, sensor, peer, True)
        feat_native = feat_locked.copy()
        feat_native['closure'] = native_first[sensor]

        common = feat_locked['closure'].notna() & feat_native['closure'].notna() & agg['daylight'] & agg['common_pair']
        diff = feat_native.loc[common, 'closure'] - feat_locked.loc[common, 'closure']
        absdiff = diff.abs()
        corr = feat_native.loc[common, 'closure'].corr(feat_locked.loc[common, 'closure'], method='spearman')
        rows.append({
            'sensor': sensor,
            'n_common_closure': int(common.sum()),
            'locked_closure_median': float(feat_locked.loc[common, 'closure'].median()),
            'native_first_closure_median': float(feat_native.loc[common, 'closure'].median()),
            'median_abs_difference': float(absdiff.median()),
            'p95_abs_difference': float(absdiff.quantile(0.95)),
            'max_abs_difference': float(absdiff.max()),
            'spearman': float(corr),
        })

        locked_route = fit_and_route(feat_locked, agg, sensor, 'locked_aggregate_first', cfg)
        native_route = fit_and_route(feat_native, agg, sensor, 'native_first', cfg)
        test_idx = locked_route['test_mask'] & native_route['test_mask']
        a0 = locked_route['alert'].reindex(agg.index).loc[test_idx]
        a1 = native_route['alert'].reindex(agg.index).loc[test_idx]
        s0 = locked_route['score'].loc[test_idx, 'it2_center']
        s1 = native_route['score'].loc[test_idx, 'it2_center']
        route_rows.append({
            'sensor': sensor,
            'locked_threshold': locked_route['threshold'],
            'native_first_threshold': native_route['threshold'],
            'n_test_common': int(test_idx.sum()),
            'locked_alert_rate': float(a0.mean()),
            'native_first_alert_rate': float(a1.mean()),
            'alert_rate_difference_native_minus_locked': float(a1.mean() - a0.mean()),
            'alert_disagreement_fraction': float((a0 != a1).mean()),
            'median_abs_center_trust_difference': float((s1 - s0).abs().median()),
            'p95_abs_center_trust_difference': float((s1 - s0).abs().quantile(0.95)),
        })

    pd.DataFrame(acquisition).to_json(OUT / 'source_acquisition_ledger.json', orient='records', indent=2)
    pd.DataFrame(rows).to_csv(OUT / 'closure_definition_comparison.csv', index=False)
    pd.DataFrame(route_rows).to_csv(OUT / 'route_impact_comparison.csv', index=False)

    summary = {
        'status': 'POST_BASELINE_IMPLEMENTATION_AUDIT',
        'protocol_baseline': cfg['protocol_id'],
        'question': 'Does computing physical closure on synchronized native support before aggregation materially alter the locked aggregate-first closure feature or downstream IT2-center routing?',
        'locked_baseline_unchanged': True,
        'comparisons': rows,
        'route_impact': route_rows,
        'interpretation_rule': 'Do not declare the locked result invalid solely because definitions differ. If downstream routing changes materially, open a correction review; otherwise document the aggregation sensitivity as robustness evidence.',
        'claim_limits': [
            'This audit does not create physical-fault labels.',
            'This audit does not establish causal sensor bias.',
            'This audit uses the same public SRRL/MIDC source period and is not a new independent site.',
            'No threshold is tuned on 2023 test outcomes; each definition is fit on 2021 and calibrated on 2022.'
        ]
    }
    (OUT / 'AUDIT_SUMMARY.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
