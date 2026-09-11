# SRRL/MIDC external-transfer result

Scientific run: `34641948767`  
Source commit: `f6225bf485fae5f9ad891204fb9967b416b4cd91`  
Actions artifact digest: `sha256:c9530fcbd8705530e23f962a5e616f4a642596af171a997f736090dec64f01d0`  
Frozen protocol: `SRRL_MIDC_EXTERNAL_TRANSFER_FROZEN_v1`

## Admission
All prespecified primary stop rules passed. Solar-component closure was available across the full interval. All 12 fit months met the coverage rule. Common-support counts were 7,410 in the 2022 alert-calibration period and 7,408 in the 2023 test period. The implementation is labelled a **disclosed-rule reconstruction sensitivity**, not an exact historical Qatar-engine replay.

## Primary 2023 diagnostics

| Sensor | IT2 center alert | IT2 lower alert | Median center trust | Median interval width |
|---|---:|---:|---:|---:|
| Primary CMP22 GHI | 4.806% | 5.292% | 0.822 | 0.092 |
| Secondary CMP22 GHI | 4.819% | 5.292% | 0.825 | 0.093 |

Primary-minus-secondary IT2-center alert-rate difference: `-0.000135`; bootstrap interval `[-0.00436, 0.00314]`.

Conditional IT2-center alert burden remains non-uniform after local fitting. Across seasons the observed range is approximately 2.6-9.0%; across the prespecified 50-200, 200-500, 500-800, and >800 W/m^2 irradiance bins it is approximately 1.6-9.3%.

## Scientific interpretation
The Qatar-style sensor asymmetry does **not** transfer to this matched SRRL pair. Operating-point/season dependence **does** remain evident after local fitting. The external result therefore supports local trust fitting and conditional operating-point monitoring while providing a clear boundary against universal sensor-specific ranking.

No SRRL physical-fault validation was performed because reproducible event labels were not admitted. No reference-grade calibration or universal IT2-superiority claim is made.

The original automated `contribution_decision.json` is retained unchanged in the Actions artifact. Its narrow direction-retention heuristic sets `candidate_for_contribution_review=false` and explicitly requires interpretive review. The separate interpretive review is recorded in `CONTRIBUTION_REVIEW.md`.