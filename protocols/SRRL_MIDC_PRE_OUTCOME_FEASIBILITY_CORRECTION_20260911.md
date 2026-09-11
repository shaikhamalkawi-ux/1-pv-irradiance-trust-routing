# SRRL/MIDC — Pre-Outcome Feasibility Correction to Fit-Month Gate

**Date:** 2026-09-11 (Asia/Dubai)  
**Outcome status:** no SRRL trust/alert-transfer outcome inspected.

The frozen v1 protocol initially required >=500 daylight 30-min common-support records in at least ten fit months. A deterministic solar-geometry check showed that this count is not physically attainable in multiple winter months at SRRL under the already frozen solar-elevation >=10 degree rule, even with perfect data availability. The count threshold would therefore confound seasonal day length with data completeness.

Replace that single gate with a coverage-based gate:
- for each 2021 fit month, calculate the number of theoretical 30-min timestamps whose solar elevation is >=10 degrees at SRRL;
- calculate common-support availability as admitted pair records divided by those theoretical daylight timestamps;
- require **>=70% coverage in at least 10 of 12 fit months**.

No feature, split, membership quantile, sensor mapping, rule, route threshold, endpoint, or contribution criterion changes. The annual 2022/2023 common-support minimum of 5,000 records remains unchanged.
