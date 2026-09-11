# SRRL/MIDC — Pre-Outcome Schema / Engine-Conformance Amendment

**Date:** 2026-09-11 (Asia/Dubai)  
**Applies to:** `SRRL_MIDC_EXTERNAL_TRANSFER_FROZEN_v1`  
**Outcome status:** no SRRL trust score, alert-rate transfer result, sensor asymmetry result, event-discrimination metric, or manuscript-admission decision had been computed or inspected when this amendment was frozen.

## 1. Schema probe
GitHub Actions schema run `34640125298` queried MIDC BMS for 2021-06-21 through 2021-06-22 and returned 2,880 native 1-min rows and 229 fields. The probe computed no scientific outcome metric.

The public raw schema does not label the two horizontal unventilated CMP22 channels with the words Primary/Secondary. It exposes:
- `Global CMP22-1 (cor) [W/m^2]` with raw `Global CMP22-1 [mV]`;
- `Global CMP22-2 (cor) [W/m^2]` with raw `Global CMP22-2 [mV]`.

## 2. Frozen channel mapping
The instrument-history page documents the selected redundant pair as Primary CMP22 S/N 140043 and Secondary CMP22 S/N 100174 during the full 2021–2023 study interval. The schema-probe corrected/raw ratios are approximately 110.66 W m^-2/mV for channel #1 and 102.21 W m^-2/mV for channel #2. These are consistent with the independent BORCAL responsivities/calibration factors for S/N 140043 and S/N 100174 and identify the channel mapping without using trust outcomes.

Therefore freeze:
- **SRRL GHI Sensor 1 / Primary:** `Global CMP22-1 (cor) [W/m^2]`, S/N 140043;
- **SRRL GHI Sensor 2 / Secondary:** `Global CMP22-2 (cor) [W/m^2]`, S/N 100174.

The manuscript-facing external labels will be `SRRL GHI Primary` and `SRRL GHI Secondary`; Qatar coded labels GHI1/GHI2 are not reused as if they were the same instruments.

## 3. Closure channels admitted before outcome inspection
The current pvlib MIDC mapping and SRRL field semantics identify:
- DHI: `Diffuse CM22-1 (vent/cor) [W/m^2]`;
- DNI: `Direct CHP1-1 [W/m^2]`.

These fields are admitted for the GHI solar-component closure feature if monthly acquisition confirms they are present over the full 2021–2023 interval. If either field is structurally unavailable in any required period, closure is downgraded according to the frozen evidence hierarchy; it is not replaced post hoc by whichever alternative gives a better result.

## 4. Explicit disclosed-rule reconstruction
The AC3 manuscript discloses membership equations and consequent values but does not preserve the exact historical software implementation of firing-strength construction/type reduction. The SRRL external run is therefore frozen as a **disclosed-rule reconstruction sensitivity**, not an exact byte-for-byte replay of the Qatar engine.

Before SRRL outcomes are computed, freeze the following implementation:
- high memberships use the disclosed IT2 lower/upper ramps;
- low membership intervals are complements `[1-upper_high, 1-lower_high]`;
- fuzzy AND uses the minimum t-norm;
- single-feature high rules fire on that feature's high membership;
- pairwise interaction rules fire on the minimum of their two high memberships;
- the all-low rule fires on the minimum of all available low memberships;
- rules involving an unavailable optional feature are omitted;
- if fewer than two evidence features are available, trust is 0.50;
- missing target irradiance hard-routes to trust 0.00;
- singleton-consequent interval type reduction uses the standard Karnik–Mendel endpoint iteration;
- Type-1 uses midpoint membership thresholds and the same rule structure.

No t-norm, consequent, feature, membership quantile, or route threshold may be changed after 2023 outcomes are opened.

## 5. Operating bins / seasons
Before outcome inspection:
- irradiance operating bins use the contemporaneous mean of the two admitted CMP22 GHI measurements, not the target sensor individually;
- bins are 50–200, 200–500, 500–800, and >800 W m^-2;
- meteorological seasons are DJF, MAM, JJA, SON.

## 6. DQS boundary
No DQS interval is inferred from score excursions. Event-labelled analysis remains optional and requires a reproducible SRRL DQS/maintenance registry tied to the selected instruments. Failure to obtain such a registry does not invalidate the primary descriptive transfer, but it blocks external fault-validation language.
