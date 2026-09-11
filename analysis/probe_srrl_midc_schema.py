from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from pvlib.iotools import read_midc_raw_data_from_nrel

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "srrl_midc_frozen_config.json"
OUT = ROOT / "results" / "srrl_midc_schema"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    cfg = json.loads(CONFIG.read_text())
    start = cfg["dataset"]["schema_probe_start"]
    end = cfg["dataset"]["schema_probe_end"]
    OUT.mkdir(parents=True, exist_ok=True)

    # Schema-only gate: values are downloaded only so the public MIDC parser can
    # expose the current field names/dtypes. No disagreement, trust, event, or
    # outcome statistic is computed here.
    df = read_midc_raw_data_from_nrel("BMS", start, end)
    raw = OUT / "schema_probe_raw.csv"
    df.to_csv(raw)

    cols = list(map(str, df.columns))
    def pick(*terms: str) -> list[str]:
        lo = [(c, c.lower()) for c in cols]
        return [c for c, cl in lo if all(t.lower() in cl for t in terms)]

    candidates = {
        "cmp22_global": pick("cmp22", "global"),
        "primary": pick("primary"),
        "secondary": pick("secondary"),
        "global_primary": [c for c in cols if "global" in c.lower() and "primary" in c.lower()],
        "global_secondary": [c for c in cols if "global" in c.lower() and "secondary" in c.lower()],
        "dhi": [c for c in cols if "diffuse" in c.lower() or "dhi" in c.lower()],
        "dni": [c for c in cols if "direct" in c.lower() or "dni" in c.lower()],
    }

    index = df.index
    inventory = {
        "protocol_id": cfg["protocol_id"],
        "probe_start": start,
        "probe_end": end,
        "rows": int(len(df)),
        "columns": int(len(cols)),
        "column_names": cols,
        "dtypes": {str(c): str(df[c].dtype) for c in df.columns},
        "index_type": type(index).__name__,
        "index_tz": str(getattr(index, "tz", None)),
        "first_index": str(index.min()) if len(index) else None,
        "last_index": str(index.max()) if len(index) else None,
        "duplicate_index_count": int(index.duplicated().sum()) if hasattr(index, "duplicated") else None,
        "candidate_columns": candidates,
        "raw_probe_sha256": sha256_file(raw),
        "raw_probe_bytes": raw.stat().st_size,
        "outcome_metrics_computed": False,
    }
    (OUT / "schema_inventory.json").write_text(json.dumps(inventory, indent=2))
    print(json.dumps(inventory, indent=2))


if __name__ == "__main__":
    main()
