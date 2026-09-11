# Paper 3 — NREL SRRL/MIDC External Trust-Transfer Protocol (FROZEN v1)

**Freeze date:** 2026-09-11 (Asia/Dubai)  
**Status:** Frozen before inspection of SRRL outcome metrics.  
**Purpose:** Independent transfer test of sensor-specific trust and operating-point transfer; not replication of Qatar thresholds, not sensor calibration, and not physical-fault validation.

## 1. Prespecified scientific question
Does a locally fitted version of the published redundant-irradiance trust formulation show that evidential trust and alert operating points remain sensor/context dependent in an independent, traceably calibrated radiation network, or does the SRRL archive establish a clear boundary on that transfer?

The external target is the **principle** (sensor-specific trust / operating-point transfer), not the Qatar numerical thresholds, AUROC values, or event composition.

## 2. Source and frozen radiometer pair
- Source: NREL Solar Radiation Research Laboratory (SRRL), Baseline Measurement System (BMS), Golden, Colorado; DOI `10.7799/1052221`.
- Primary redundant pair: Kipp & Zonen CMP22 **Global Horizontal (Primary)** and CMP22 **Global Horizontal (Secondary)**.
- Instrument-history lock: Primary S/N 140043 from 2015-06-22 through 2024-04-23; Secondary S/N 100174 from 2015-06-22 onward.
- Main external interval: **2021-01-01 through 2023-12-31**, which is entirely before the 2024 primary serial replacement and avoids the documented 2024 processing/instrument transition.
- Exact MIDC column names are a schema item and may be mapped after a header/schema-only inspection. Mapping may not use outcome values.

## 3. Frozen chronology
To give every stage a full seasonal cycle while keeping the same instrument serials:
- **fit:** 2021-01-01 through 2021-12-31;
- **alert calibration:** 2022-01-01 through 2022-12-31;
- **test:** 2023-01-01 through 2023-12-31.
No row from 2023 may set membership thresholds or the alert cutoff.

## 4. Sampling and aggregation
- Acquire native 1-min MIDC BMS data.
- Preserve local Mountain-time timestamp semantics provided by MIDC; do not silently reinterpret as UTC.
- Aggregate each signal to 10-min medians when >=5 native 1-min values are present; aggregate to 30-min medians when >=2 valid 10-min values are present, matching the Qatar aggregation family.
- Primary evaluation requires both CMP22 GHI channels finite at a 30-min record.
- Daylight requires solar elevation >=10 degrees, calculated from SRRL coordinates using pvlib. No outcome-dependent daylight threshold changes are allowed.

## 5. Evidence hierarchy
Primary common-evidence features are computed from the redundant GHI pair:
1. pair disagreement;
2. dynamic disagreement;
3. stuck behavior.

The published definitions are retained:
`dP = |xi-xj| / max((|xi|+|xj|)/2, 50 W m^-2)`;
`dDelta = |Δxi-Δxj| / max((|Δxi|+|Δxj|)/2, 25 W m^-2)`;
`dStuck = exp[-Ri/12.5] * min(Rj/50,1)`, with centered three-record ranges.

A fourth solar-component closure feature is admitted only if schema inspection identifies an unambiguous, continuous primary DHI and primary DNI measurement over the complete 2021–2023 interval. If admitted, GHI closure is `e = DHI + DNI*cos(z)` and uses the published normalized closure definition. Closure availability/status must be recorded before test metrics are opened.

## 6. Local IT2 membership fit
For every admitted evidence feature and each target sensor separately:
- within each fit month, compute the 75th percentile onset `a` and 97.5th percentile full-concern value `b`;
- use the 10th/90th percentiles across the 12 fit months to form `(aL,aU,bL,bU)`;
- lower high-concern membership uses ramp `R(d;aU,bU)` and upper membership uses `R(d;aL,bL)`;
- midpoint Type-1 membership uses midpoint thresholds.
The footprint is empirical seasonal threshold variation, not a confidence interval. No Qatar membership threshold is transferred.

## 7. Frozen rule structure
Retain the disclosed Takagi–Sugeno consequent table from the Qatar manuscript as structural model information, not as calibrated probabilities:
- all available concerns low: 0.95;
- pair / closure concern high: 0.25 / 0.32;
- dynamic / stuck concern high: 0.48 / 0.22;
- pair+closure / pair+dynamic: 0.05 / 0.12;
- closure+stuck / pair+stuck: 0.10 / 0.08;
- fewer than two available evidence features: 0.50;
- missing target sensor: trust 0.00 hard route.

For the external implementation, firing-strength construction and interval type reduction must be explicit in code and must not be tuned against 2023 data. If the historical implementation cannot be recovered exactly, the external result must be labelled a **disclosed-rule reconstruction sensitivity** rather than an exact engine replication.

## 8. Alert operating point
For each route separately (Type-1 center, IT2 center, IT2 lower-bound), set the alert threshold to its empirical 95th percentile score on the **2022 alert-calibration period**, targeting a nominal 5% alert burden without using 2023 outcomes or DQS labels.

## 9. Primary endpoints (do not require event labels)
On 2023 test support, report by sensor and jointly:
- no-label alert rate under the frozen 2022 threshold;
- median IT2 center trust and median interval width;
- alert rate by irradiance operating bin (50–200, 200–500, 500–800, >800 W m^-2) and by season;
- center/lower-bound route disagreement fraction;
- Primary-vs-Secondary asymmetry in the above quantities.
These are operating-transfer diagnostics, not false-positive rates because unlabeled records are not certified healthy truth.

## 10. DQS/event-labelled secondary endpoint
SRRL DQS/maintenance metadata may be used only if event intervals can be acquired reproducibly and mapped to the selected radiometers without manual outcome selection. If admitted, evaluate AUROC/AUPRC/recall and event-specific routing on common support, and call this **DQS/event-tag discrimination**, not physical-fault validation. If DQS completeness/mapping fails, omit these metrics without replacing them with inferred faults.

## 11. Type-1 / IT2 comparison boundary
Compare Type-1 midpoint, IT2 center, and IT2 lower-bound routes. Do not claim IT2 superiority from a small discrimination or alert-rate difference. The intended test is whether the interval/lower-bound route exposes a meaningful corroborate-or-hold tradeoff and whether that operating behavior transfers across sensors/periods.

## 12. Stop / downgrade rules
Do not admit a main-paper external result if any of the following holds:
- the two exact CMP22 GHI channels cannot be mapped reproducibly;
- either channel changes serial within the 2021–2023 main interval;
- fewer than 10 fit months each have >=500 daylight 30-min common-support records;
- fewer than 5,000 common-support daylight 30-min records are available in either 2022 or 2023;
- the rule engine requires post-outcome tuning or an undocumented change of mathematical family;
- an apparent event claim depends on inferred rather than documented DQS/maintenance intervals.

If primary descriptive transfer passes but DQS mapping fails, retain descriptive sensor/operating-point transfer and explicitly state that external fault validation was not performed.

## 13. Contribution gate
A compact main-paper result is warranted only if the external archive provides at least one nontrivial, reproducible finding that materially sharpens the paper, such as:
A. sensor-specific alert/trust behavior despite locally refitted thresholds;
B. operating-point/season dependence showing the calibration operating point does not transfer uniformly;
C. a clear Type-1/IT2 center/lower-bound routing tradeoff; or
D. a documented boundary showing that the Qatar trust interpretation does not transfer.
Otherwise keep SRRL in Supplement/GitHub only and do not open a new manuscript revision.

## 14. Frozen reproducibility outputs
- source/API request ledger and SHA-256 for downloaded monthly slices;
- schema and exact channel map;
- aggregation/QC report;
- exact split counts;
- monthly membership ledger;
- route thresholds from 2022;
- 2023 sensor/season/irradiance-bin diagnostics;
- optional DQS event registry if admitted;
- contribution decision;
- environment and source-code hashes.
