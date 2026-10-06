"""Download current NAV histories for the requested Indian mutual-fund schemes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT / "data" / "raw" / "live_nav"
API_URL = "https://api.mfapi.in/mf/{scheme_code}"
SCHEMES = (
    (119018, "HDFC Large Cap Fund - Direct Plan - Growth Option"),
    (119598, "SBI Large Cap Fund - Direct Plan - Growth"),
    (
        120586,
        "ICICI Prudential Large Cap Fund (erstwhile Bluechip Fund) - Direct Plan - Growth",
    ),
    (118632, "Nippon India Large Cap Fund - Direct Plan - Growth Option"),
    (120465, "Axis Large Cap Fund - Direct Plan - Growth Option"),
    (120152, "Kotak Large Cap Fund - Direct Plan - Growth"),
)


def safe_filename(name: str) -> str:
    """Convert a scheme name to a portable filename component."""
    return re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")


def fetch_scheme(
    scheme_code: int, scheme_name: str, output_dir: Path
) -> Path:
    """Fetch one MFAPI NAV history, validate identity, and save the raw records."""
    response = requests.get(
        API_URL.format(scheme_code=scheme_code),
        timeout=(10, 60),
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Unexpected API response for scheme {scheme_code}: expected an object")

    meta = payload.get("meta")
    records = payload.get("data")
    if not isinstance(meta, dict) or not isinstance(records, list):
        raise ValueError(
            f"Unexpected API response for scheme {scheme_code}: expected meta object and data list"
        )
    if not records:
        raise ValueError(f"API returned no NAV records for scheme {scheme_code}")

    frame = pd.DataFrame.from_records(records)
    if not {"date", "nav"}.issubset(frame.columns):
        raise ValueError(
            f"API records for scheme {scheme_code} are missing date/nav fields: "
            f"{frame.columns.tolist()}"
        )

    actual_scheme_code = int(meta["scheme_code"])
    if actual_scheme_code != scheme_code:
        raise ValueError(
            f"MFAPI returned scheme code {actual_scheme_code} for requested code {scheme_code}"
        )
    actual_scheme_name = str(meta.get("scheme_name", ""))
    frame.insert(0, "scheme_code", actual_scheme_code)
    frame.insert(1, "requested_scheme_name", scheme_name)
    frame.insert(2, "scheme_name", actual_scheme_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{scheme_code}_{safe_filename(actual_scheme_name)}_nav.csv"
    frame.to_csv(output_path, index=False)
    requested_tokens = set(re.findall(r"[a-z0-9]+", scheme_name.casefold()))
    actual_tokens = set(re.findall(r"[a-z0-9]+", actual_scheme_name.casefold()))
    if not requested_tokens.issubset(actual_tokens):
        print(
            f"WARNING: code {scheme_code} was labeled '{scheme_name}', but MFAPI identifies it "
            f"as '{actual_scheme_name}'. The CSV preserves both names."
        )
    print(f"Saved {len(frame):,} NAV record(s) to {output_path}")
    return output_path


def fetch_schemes(
    schemes: tuple[tuple[int, str], ...] = SCHEMES,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    """Fetch the configured schemes and return paths to their saved CSV files."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    print(f"Fetch started (UTC): {fetched_at}")
    paths = [fetch_scheme(code, name, output_dir) for code, name in schemes]
    print(f"Completed: {len(paths)} scheme(s) fetched.")
    return paths


def main() -> None:
    """Parse the output directory and fetch the configured scheme histories."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for raw NAV CSV files (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()
    fetch_schemes(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
