#!/usr/bin/env python3
"""
Download 12z NAM 3km APCP GRIB2 files (f12–f24),
sum them, and output NetCDF.

Output:
  nam3km_12z_apcp_f12_f24_total.nc
"""

from datetime import datetime
from pathlib import Path

import requests
import xarray as xr

# ---------------- CONFIG ---------------- #

RUN_HOUR = "12"
START_FH = 12
END_FH = 24

BASE_URL = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/nam/prod"

WORKDIR = Path("work")
WORKDIR.mkdir(exist_ok=True)

OUTFILE = "nam3km_12z_apcp_f12_f24_total.nc"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CapeCodWeather/1.0)"
}

# --------------------------------------- #


def download(url, outpath):
    if outpath.exists():
        return

    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    outpath.write_bytes(r.content)


def main():
    today = datetime.utcnow().strftime("%Y%m%d")

    datasets = []

    for fh in range(START_FH, END_FH + 1):
        fh_str = f"{fh:02d}"

        fname = f"nam.t{RUN_HOUR}z.conusnest.hiresf{fh_str}.tm00.grib2"
        url = f"{BASE_URL}/nam.{today}/{fname}"
        local = WORKDIR / fname

        print(f"Downloading {fname}")
        download(url, local)

        ds = xr.open_dataset(
            local,
            engine="cfgrib",
            filter_by_keys={"shortName": "tp"},
            backend_kwargs={"indexpath": ""},
        )

        datasets.append(ds["tp"])

    print("Summing APCP")
    total = sum(datasets)

    out = total.to_dataset(name="apcp_12_24")
    out["apcp_12_24"].attrs.update(
        {
            "units": "mm",
            "description": "NAM 3km total precipitation from f12 to f24",
            "model": "NAM CONUS Nest 3km",
            "run_hour": "12z",
        }
    )

    print(f"Writing {OUTFILE}")
    out.to_netcdf(OUTFILE)

    print("✅ DONE")


if __name__ == "__main__":
    main()

