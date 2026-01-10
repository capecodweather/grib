#!/usr/bin/env python3
"""
Download 12z NAM 3km APCP GRIB2 files (f12–f24),
sum them using xarray/cfgrib, and output NetCDF.

Output:
  nam3km_12z_apcp_f12_f24_total.nc
"""

import os
from pathlib import Path

import requests
import xarray as xr

RUN_HOUR = "12"
START_FH = 12
END_FH = 24

BASE_URL = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/nam/prod"

WORKDIR = Path("work")
WORKDIR.mkdir(exist_ok=True)

OUTFILE = "nam3km_12z_apcp_f12_f24_total.nc"


def download_file(url, outpath):
    if outpath.exists():
        return
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    outpath.write_bytes(r.content)


datasets = []

for fh in range(START_FH, END_FH + 1):
    fh_str = f"{fh:02d}"
    fname = f"nam.t{RUN_HOUR}z.conusnest.hiresf{fh_str}.tm00.grib2"
    url = f"{BASE_URL}/nam.{RUN_HOUR}/{fname}"
    local = WORKDIR / fname

    print(f"Downloading {fname}")
    download_file(url, local)

    ds = xr.open_dataset(
        local,
        engine="cfgrib",
        filter_by_keys={"shortName": "tp"},
        backend_kwargs={"indexpath": ""},
    )

    datasets.append(ds)

print("Summing precipitation")
total = sum(ds["tp"] for ds in datasets)

out = total.to_dataset(name="apcp_12_24")
out["apcp_12_24"].attrs["units"] = "mm"
out["apcp_12_24"].attrs["description"] = "NAM 3km total precipitation f12–f24"

print(f"Writing {OUTFILE}")
out.to_netcdf(OUTFILE)

print("✅ DONE")
