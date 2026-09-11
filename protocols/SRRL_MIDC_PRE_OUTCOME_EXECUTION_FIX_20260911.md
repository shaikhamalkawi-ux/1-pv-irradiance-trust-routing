# SRRL/MIDC — Pre-Outcome Execution Fix

**Date:** 2026-09-11 (Asia/Dubai)  
**Applies to:** first full external-transfer run `34640927307`  
**Outcome status:** no trust score, alert rate, sensor asymmetry, contribution result, or manuscript-admission outcome was computed before this fix.

The first full run successfully acquired all monthly MIDC slices from January 2021 through December 2023, then stopped in the deterministic fit-month coverage calculation with pandas `ValueError: Grouper and axis must be same length`.

Cause: the implementation filtered the DataFrame rows but passed `agg.index.month` from the unfiltered full DataFrame as the group key. This is a dataframe-indexing bug only.

Fix: construct the fit-day and fit-admitted boolean masks first, then group each filtered DataFrame by **its own filtered index month**. No source data, study period, sensor mapping, aggregation, feature definition, membership quantile, fuzzy rule, alert threshold, endpoint, stop rule, sensitivity, or contribution criterion changes.

The failed run therefore contains acquisition/execution evidence only and no scientific outcome to inspect or optimize against.
