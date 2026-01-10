#!/usr/bin/env python3
"""
Download 12z NAM 3km APCP (surface) for f12–f24 using
filter_nam_conusnest.pl, sum them, and write NetCDF.

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

BASE_CGI = "https://nomads.ncep.noaa.gov/cgi-bin/filter_nam_conusnest.pl"

WORKDIR = Path("work")
WORKDIR.mkdir(exist_ok=True)

OUTFILE = "nam3km_12z_apcp_f12_f24_total.nc"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CapeCodWeather/1.0)"
}

# --------------------------------------- #


def download_apcp(run_date, fh):
    fh_str = f"{fh:02d}"
    fname = f"nam.t{RUN_HOUR}z.conusnest.hiresf{fh_str}.tm00.grib2"

    params = {
        "file": fname,
        "dir": f"/nam.{run_date}",
        "var_APCP": "on",
        "lev_surface": "on",
    }

    outpath = WORKDIR / fname
    if outpath.exists():
        return outpath

    print(f"Downloading {fname}")

    r = requests.get(BASE_CGI, params=params, headers=HEADERS, timeout=120)
    r.raise_for_status()
    outpath.write_bytes(r.content)

    return outpath


def main():
    run_date = datetime.utcnow().strftime("%Y%m%d")
    datasets = []

    for fh in range(START_FH, END_FH + 1):
        grib = download_apcp(run_date, fh)

        ds = xr.open_dataset(
            grib,
            engine="cfgrib",
            backend_kwargs={"indexpath": ""},
        )

        # APCP in NAM is total precip for the interval ending at fh
        datasets.append(ds["tp"])

    print("Summing APCP f12–f24")
    total = sum(datasets)

    out = total.to_dataset(name="apcp_12_24")
    out["apcp_12_24"].attrs.update(
        {
            "units": "mm",
            "description": "NAM 3km total precipitation f12–f24",
            "model": "NAM CONUS Nest 3km",
            "run_hour": "12z",
        }
    )

    print(f"Writing {OUTFILE}")
    out.to_netcdf(OUTFILE)

    print("✅ DONE")


if __name__ == "__main__":
    main()



