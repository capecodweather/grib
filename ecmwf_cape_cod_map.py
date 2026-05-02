#!/usr/bin/env python3
"""
Download ECMWF open-data surface fields and plot a Cape Cod forecast map.

Outputs:
  ecmwf_cape_cod_latest.png
"""

from __future__ import annotations

import argparse
from datetime import timezone
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cfgrib
import matplotlib.pyplot as plt
import numpy as np
from ecmwf.opendata import Client


CAPE_COD_BBOX = {
    "west": -71.4,
    "east": -69.4,
    "south": 40.8,
    "north": 42.3,
}

PARAMS = ["2t", "10u", "10v", "msl", "tp"]
DEFAULT_STEP = 24
DEFAULT_SOURCE = "google"
DEFAULT_GRIB = "work/ecmwf_cape_cod_latest.grib2"
DEFAULT_PNG = "ecmwf_cape_cod_latest.png"
SOURCE_FALLBACKS = ["google", "ecmwf", "azure"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download ECMWF open data and plot Cape Cod weather fields."
    )
    parser.add_argument("--step", type=int, default=DEFAULT_STEP, help="Forecast hour.")
    parser.add_argument(
        "--time",
        type=int,
        default=None,
        choices=[0, 6, 12, 18],
        help="Forecast cycle UTC. Defaults to latest available matching run.",
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        choices=["auto", "ecmwf", "azure", "google"],
        help="ECMWF open-data source. Use auto to try mirrors until one works.",
    )
    parser.add_argument("--grib", default=DEFAULT_GRIB, help="Downloaded GRIB2 path.")
    parser.add_argument("--output", default=DEFAULT_PNG, help="Output PNG path.")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Use an existing GRIB2 file instead of downloading.",
    )
    return parser.parse_args()


def download_gribs(args: argparse.Namespace) -> list[Path]:
    target = Path(args.grib)
    target.parent.mkdir(parents=True, exist_ok=True)

    if args.skip_download and target.exists():
        print(f"Using existing {target}")
        return [target]

    downloaded = []
    sources = SOURCE_FALLBACKS if args.source == "auto" else [args.source]

    for param in PARAMS:
        param_target = target.with_name(f"{target.stem}_{param}{target.suffix}")
        request = {
            "type": "fc",
            "step": args.step,
            "param": param,
            "target": str(param_target),
        }
        if args.time is not None:
            request["time"] = args.time

        last_error = None
        for source in sources:
            if param_target.exists():
                param_target.unlink()

            print(f"Downloading ECMWF {param} from {source} to {param_target}")
            client = Client(source=source, model="ifs")
            try:
                result = client.retrieve(**request)
            except Exception as exc:
                last_error = exc
                print(f"Download of {param} from {source} failed: {exc}")
                continue

            print(f"Retrieved {param}: {getattr(result, 'datetime', 'latest available')}")
            downloaded.append(param_target)
            break
        else:
            raise RuntimeError(f"All ECMWF open-data sources failed for {param}: {last_error}")

    return downloaded


def open_fields(grib_paths: list[Path]) -> dict[str, object]:
    datasets = []
    for grib_path in grib_paths:
        datasets.extend(
            cfgrib.open_datasets(
                grib_path,
                backend_kwargs={
                    "indexpath": "",
                    "errors": "ignore",
                },
            )
        )

    fields = {}
    for ds in datasets:
        for name, data_array in ds.data_vars.items():
            fields[name] = data_array
    return fields


def find_field(fields: dict[str, object], *names: str):
    for name in names:
        if name in fields:
            return fields[name]
    available = ", ".join(sorted(fields))
    raise KeyError(f"Missing one of {names}. Available fields: {available}")


def subset_cape_cod(data_array):
    normalized = data_array.assign_coords(
        longitude=(((data_array.longitude + 180) % 360) - 180)
    ).sortby("longitude")

    lat_values = np.asarray(normalized.latitude.values)
    if lat_values[0] > lat_values[-1]:
        lat_slice = slice(CAPE_COD_BBOX["north"], CAPE_COD_BBOX["south"])
    else:
        lat_slice = slice(CAPE_COD_BBOX["south"], CAPE_COD_BBOX["north"])

    subset = normalized.sel(
        latitude=lat_slice,
        longitude=slice(CAPE_COD_BBOX["west"], CAPE_COD_BBOX["east"]),
    )
    if subset.size == 0:
        raise ValueError("Cape Cod subset is empty; check source grid coordinates.")
    return subset


def to_numpy(data_array):
    return np.asarray(data_array.squeeze())


def forecast_label(data_array, step: int) -> str:
    valid_time = data_array.coords.get("valid_time")
    if valid_time is None:
        return f"ECMWF IFS f{step:03d}"

    value = np.asarray(valid_time.values).item()
    if hasattr(value, "replace"):
        value = value.replace(tzinfo=timezone.utc)
        return value.strftime("ECMWF IFS valid %Y-%m-%d %HZ")
    return f"ECMWF IFS f{step:03d}"


def draw_panel(ax, title: str, data, levels, cmap, colorbar_label: str):
    projection = ccrs.PlateCarree()
    lon = to_numpy(data.longitude)
    lat = to_numpy(data.latitude)
    values = to_numpy(data)

    mesh = ax.contourf(
        lon,
        lat,
        values,
        levels=levels,
        cmap=cmap,
        extend="both",
        transform=projection,
    )
    ax.coastlines(resolution="10m", linewidth=0.8)
    ax.add_feature(cfeature.STATES.with_scale("10m"), linewidth=0.4, edgecolor="0.35")
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.3, edgecolor="0.45")
    ax.set_extent(
        [
            CAPE_COD_BBOX["west"],
            CAPE_COD_BBOX["east"],
            CAPE_COD_BBOX["south"],
            CAPE_COD_BBOX["north"],
        ],
        crs=projection,
    )
    ax.set_title(title, fontsize=11)
    ax.gridlines(draw_labels=False, linewidth=0.3, alpha=0.4)
    cbar = plt.colorbar(mesh, ax=ax, orientation="horizontal", pad=0.04, shrink=0.82)
    cbar.set_label(colorbar_label, fontsize=9)


def plot_map(fields: dict[str, object], output: str, step: int) -> None:
    t2m = subset_cape_cod(find_field(fields, "t2m", "2t")) - 273.15
    u10 = subset_cape_cod(find_field(fields, "u10", "10u"))
    v10 = subset_cape_cod(find_field(fields, "v10", "10v"))
    msl = subset_cape_cod(find_field(fields, "msl")) / 100.0
    tp = subset_cape_cod(find_field(fields, "tp")) * 39.3701

    temp_f = (t2m * 9.0 / 5.0) + 32.0
    wind_kt = np.hypot(u10, v10) * 1.94384

    projection = ccrs.PlateCarree()
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(12, 9),
        subplot_kw={"projection": projection},
        constrained_layout=True,
    )

    fig.suptitle(forecast_label(t2m, step), fontsize=16, fontweight="bold")

    draw_panel(
        axes[0, 0],
        "2 m Temperature",
        temp_f,
        np.arange(10, 91, 5),
        "coolwarm",
        "deg F",
    )
    draw_panel(
        axes[0, 1],
        "10 m Wind Speed",
        wind_kt,
        np.arange(0, 61, 5),
        "viridis",
        "kt",
    )

    lon = to_numpy(u10.longitude)
    lat = to_numpy(u10.latitude)
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    skip = (slice(None, None, 2), slice(None, None, 2))
    axes[0, 1].barbs(
        lon_grid[skip],
        lat_grid[skip],
        to_numpy(u10)[skip] * 1.94384,
        to_numpy(v10)[skip] * 1.94384,
        length=4.5,
        linewidth=0.45,
        transform=projection,
    )

    draw_panel(
        axes[1, 0],
        "Mean Sea Level Pressure",
        msl,
        np.arange(960, 1046, 4),
        "Spectral_r",
        "hPa",
    )
    contour = axes[1, 0].contour(
        to_numpy(msl.longitude),
        to_numpy(msl.latitude),
        to_numpy(msl),
        levels=np.arange(960, 1046, 4),
        colors="black",
        linewidths=0.45,
        transform=projection,
    )
    axes[1, 0].clabel(contour, inline=True, fontsize=7, fmt="%d")

    draw_panel(
        axes[1, 1],
        "Total Precipitation",
        tp,
        [0, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 1.0, 1.5, 2.0],
        "YlGnBu",
        "in",
    )

    fig.text(
        0.5,
        0.01,
        "Data: ECMWF Open Data, IFS 0.25 degree GRIB2. Plot generated by capecodweather/grib.",
        ha="center",
        fontsize=8,
        color="0.35",
    )
    fig.savefig(output, dpi=160, bbox_inches="tight")
    print(f"Wrote {output}")


def main() -> None:
    args = parse_args()
    grib_paths = download_gribs(args)
    fields = open_fields(grib_paths)
    plot_map(fields, args.output, args.step)


if __name__ == "__main__":
    main()
