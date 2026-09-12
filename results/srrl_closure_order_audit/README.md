# SRRL closure-order sensitivity audit

This post-baseline implementation audit tests whether computing the irradiance closure relationship before versus after temporal aggregation materially changes the external SRRL/MIDC conclusion in Paper 3 AC4.

Workflow run: `34674555001`; source period: 2021-01-01 through 2023-12-31; native rows processed: 1,576,800; aggregated rows: 52,560; 2023 common-support test records: 7,408.

The locked AC4 center-alert rates were 4.8056% for the primary CMP22 and 4.8191% for the secondary CMP22. Under native-support closure followed by aggregation they are 4.9676% and 4.7786%, respectively. The absolute changes are about +0.162 and -0.040 percentage points. The sensor-gap remains small (0.189 percentage points), and the predeclared materiality rule is not triggered.

The closure feature itself can change appreciably at some timestamps, so the aggregation-order issue is scientifically real. However, it does not overturn the external-boundary conclusion: the strong Qatar sensor asymmetry is not reproduced by the closely matched SRRL CMP22 pair, while locally fitted operating-point dependence remains the appropriate interpretation.

Decision: **KEEP as Supplement/GitHub sensitivity; do not treat it as a correction of AC4 main results by itself.**

This audit does not provide physical-fault labels and does not establish sensor equivalence or universal sensor ranking.