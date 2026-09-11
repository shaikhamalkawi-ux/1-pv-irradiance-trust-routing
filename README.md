# PV Irradiance Trust Routing

Companion repository for the conference manuscript **Sensor-Specific Trust and Operating-Point Transfer in Redundant PV Irradiance Measurements**.

## Research question
Can the same irradiance-sensor trust formulation and operating threshold be applied across redundant radiometers and later periods, or should trust be routed by sensor/channel and evidence state?

## Current Qatar result
The Qatar study found large channel-specific differences in evidential discrimination and an explicit alert/recall trade-off for interval type-2 (IT2) lower-bound routing. The manuscript does **not** claim broad IT2 superiority, physical sensor-fault diagnosis, or metrological calibration.

## Independent public-data extension
A prespecified transfer test is being prepared with the **NREL Solar Radiation Research Laboratory (SRRL) Baseline Measurement System (BMS)**. SRRL provides one-minute irradiance data from redundant, traceably calibrated radiometers together with instrument histories, calibration information, maintenance records, and Data Quality Statements.

Primary public-data citation:

> Stoffel, T., & Andreas, A. *NREL Solar Radiation Research Laboratory (SRRL): Baseline Measurement System (BMS), Golden, Colorado*. NREL / NLR Data Catalog. DOI: 10.7799/1052221.

Candidate external pair: primary and secondary global-horizontal CMP22 pyranometers, subject to a frozen channel/history audit before analysis.

## Repository policy
- Qatar source telemetry and owner-event records are not redistributed.
- Public SRRL data are referenced from the authoritative MIDC/NLR source.
- Qatar fuzzy memberships and thresholds will **not** be copied as universal constants to SRRL; local fit/calibration/test periods are required.
- The external estimand is transfer of the **trust-routing principle**, not equality of Qatar and SRRL scores.

## Planned structure
- `src/` trust-feature and IT2/type-1 code
- `configs/` frozen rule/membership/threshold specifications
- `tests/` chronology, equation, and leakage checks
- `results/` public result tables
- `supplement/` conference supplementary material
- `external_data/` SRRL provenance and download records
- `restricted_data/` Qatar-data/event-registry boundary

## Status
Public research companion. Manuscript authorship/affiliations will be synchronized after collaborator confirmation.
