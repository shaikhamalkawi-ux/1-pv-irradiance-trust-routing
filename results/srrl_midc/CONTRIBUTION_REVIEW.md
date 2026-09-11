# SRRL/MIDC contribution review

This review is intentionally separate from the preserved automated `contribution_decision.json`.

## Automated outcome
The automated result sets `candidate_for_contribution_review=false` under a narrow direction-retention heuristic and also sets `main_paper_admission_requires_interpretive_review=true`. That machine outcome is retained unchanged.

## Frozen contribution gate
The prespecified protocol permits a compact main-paper result when the external archive supplies at least one material finding such as:
- sensor-specific trust/alert behavior after local refitting;
- operating-point or seasonal dependence showing non-uniform transfer;
- a meaningful Type-1/IT2 center/lower-bound routing tradeoff; or
- a documented boundary showing that the Qatar trust interpretation does not transfer.

## Evidence
All primary stop rules passed. On 7,408 common-support daylight 30-min 2023 records, the locally calibrated IT2-center alert rates were 4.806% and 4.819% for the primary and secondary CMP22 GHI channels. The primary-minus-secondary difference was -0.000135 with a bootstrap interval of [-0.00436, 0.00314], so the strong Qatar-style sensor asymmetry did not transfer to this matched SRRL pair.

At the same time, alert burden remained strongly conditional after local fitting: approximately 2.6-9.0% across seasons and 1.6-9.3% across the four prespecified irradiance bins. This is non-uniform operating-point transfer under gate B and a clear boundary on universal sensor-specific ranking under gate D.

## Decision
**ADMIT COMPACT MAIN-PAPER BOUNDARY RESULT.** The external evidence materially sharpens the paper because it distinguishes the transferable element (local fitting plus conditional operating-point monitoring) from the non-transferable element (strong sensor-specific asymmetry). This is not a generic validation claim and does not require the Qatar winner or sensor ranking to repeat.

## Claim limits
- No SRRL physical-fault validation: reproducible event labels were not admitted.
- No reference-grade calibration claim.
- No universal IT2-superiority claim.
- No automatic sensor-substitution claim.
- The SRRL implementation is a disclosed-rule reconstruction sensitivity, not an exact replay of historical Qatar firing-strength code.