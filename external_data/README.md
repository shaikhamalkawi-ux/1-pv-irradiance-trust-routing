# External data record — NREL SRRL BMS

Authoritative source:
- Solar Radiation Research Laboratory (SRRL), Baseline Measurement System (BMS), Golden, Colorado
- DOI: `10.7799/1052221`
- NLR/NREL data catalog: https://data.nlr.gov/submissions/7
- MIDC instrument history: https://midcdmz.nrel.gov/srrl_bms/instruments.html

SRRL BMS provides 1-minute solar-radiation measurements and extensive instrument metadata. The instrument history documents redundant global-horizontal radiometers, calibration histories, maintenance records, and Data Quality Statements.

## Candidate external comparison
Primary and secondary Kipp & Zonen CMP22 global-horizontal pyranometers are the first candidate pair because they are redundant, co-located global-horizontal measurements with traceable calibration histories. The exact analysis interval will be frozen only after checking sensor serial-number changes, calibration intervals, and DQS records.

## Prespecified transfer question
Does a locally calibrated trust-routing formulation retain the same evidential meaning across redundant radiometers and later periods in an independent, traceably calibrated solar-radiation network?

## Guardrails
1. Do not reuse Qatar membership thresholds or route cutoffs as SRRL constants.
2. Freeze fit/calibration/test chronology before inspecting headline test outcomes.
3. Use SRRL instrument-history/DQS evidence to define documented event intervals; do not infer physical faults solely from score excursions.
4. Report Type-1 and IT2 center together; do not claim IT2 superiority from tiny discrimination differences.
5. Compare lower-bound routing only as a sensitivity/operating route, with its recall cost shown explicitly.
6. If event composition differs materially by sensor, interpret discrimination as channel-and-event-composition dependent rather than intrinsic sensor quality.
