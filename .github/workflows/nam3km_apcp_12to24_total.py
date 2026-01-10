#!/usr/bin/env python3
"""
Download 12z NAM 3km APCP GRIB2 files (f12–f24),
sum them using wgrib2, and output a new GRIB2 file.

Output:
  nam3km_12z_apcp_f12_f24_total.grib2
"""

import subprocess
import sys
from pathlib import Path

# ---------------- CONFIG ---------------- #

RUN_HOUR = "12"
START_FH = 12
END_FH = 24

BASE_URL = (
    "https://nomads.ncep.noaa.gov/pub/data/nccf/com/nam/prod"
)

WORKDIR = Path("work")
WORKDIR.mkdir(exist_ok=True)

OUTPUT_GRIB = "nam3km_12z_apcp_f12_f24_total.grib2"

# ---------------------------------------- #


def run(cmd):
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def download_files():
    files = []

    for fh in range(START_FH, END_FH + 1):
        fh_str = f"{fh:02d}"

        fname = f"nam.t{RUN_HOUR}z.conusnest.hiresf{fh_str}.tm00.grib2"
        url = f"{BASE_URL}/nam.{RUN_HOUR}/{fname}"

        out = WORKDIR / fname

        print(f"Downloading {fname}")
        run(["curl", "-f", "-o", str(out), url])
        files.append(out)

    return files


def extract_apcp(files):
    apcp_files = []

    for f in files:
        out = f.with_suffix(".apcp.grib2")

        run([
            "wgrib2",
            str(f),
            "-match", "APCP",
            "-grib", str(out)
        ])

        apcp_files.append(out)

    return apcp_files


def sum_gribs(apcp_files):
    """
    Sum all APCP files using wgrib2 -add
    """
    temp_sum = WORKDIR / "apcp_sum.grib2"

    # Initialize sum with first file
    run([
        "cp",
        str(apcp_files[0]),
        str(temp_sum)
    ])

    # Add remaining files
    for f in apcp_files[1:]:
        run([
            "wgrib2",
            str(temp_sum),
            "-add", str(f),
            "-grib", str(temp_sum)
        ])

    # Final output
    run(["mv", str(temp_sum), OUTPUT_GRIB])


def main():
    files = download_files()
    apcp_files = extract_apcp(files)
    sum_gribs(apcp_files)

    print(f"\n✅ DONE: {OUTPUT_GRIB}")


if __name__ == "__main__":
    main()
