#!/usr/bin/env python3
"""Cut the scenario's Sentinel-2 scenes - before and after the incident - over its map area into images.

The scenes are the scenario's SENTINEL2_SCENES (Level-2A surface reflectance), named
by product up to the relative orbit, for example `S2A_MSIL2A_20260820T101701_R065`:
every tile of that datatake over the map area is used, so an area across two tiles
or UTM zones is whole. Per scene it writes two PNGs, four for a wildfire:

- natural colour (bands B04-B03-B02, reflectance 0-0.25, or the range the scenario's
  SENTINEL2_NATURAL_REFLECTANCE gives the scene);
- for a wildfire scenario, false colour with short-wave infrared (B12-B8A-B04, reflectance
  0-0.4), as Landsat's 7-5-4: burnt forest is dark red-brown, active fire bright;
- for a wildfire scenario, the moisture in the vegetation by the normalised difference moisture
  index NDMI (B8A - B11) / (B8A + B11), in Landsat's NDMI colours, brown dry to blue moist;
  clouds, cloud shadows, water and missing data are transparent;
- water by the normalised difference water index NDWI (B03 - B08) / (B03 + B08):
  blue where NDWI is above 0, otherwise transparent; clouds, cloud shadows and
  missing data from the scene classification (SCL) are transparent as well.

The scenes are read from Microsoft Planetary Computer's open STAC catalogue with the
anonymous access token its API hands out; GDAL in Docker (as for Landsat) reads only
the map area and warps it to WGS 84; numpy and Pillow from the .venv write the NDWI.
The tool reports the share of the scenario's focus area each scene covers and the
cloud over it. Copernicus Sentinel data are free and open; SOURCE.json records the
products, the bands, the stretch and the notice.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from app.backend import scenario
from tools import geo_tools
from tools.fetch_landsat_scene import NDMI_COLOURS, STAC, get_json, run_gdal, without_token

COLLECTION = "sentinel-2-l2a"
TOKEN_URL = f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{COLLECTION}"
SENTINEL2_DIR = scenario.SENTINEL2_DIR
SCENES = scenario.SENTINEL2_SCENES
BBOX = scenario.MAP_BBOX
SIZE = scenario.SENTINEL2_SIZE
# The area each scene's coverage, cloud and water are reported for (west, south, east, north).
FOCUS_AREA = scenario.LANDSAT_FOCUS_AREA
WILDFIRE = scenario.INCIDENT == "wildfire"
NATURAL = {"bands": ["B04", "B03", "B02"], "reflectance": (0.0, 0.25)}
# Short-wave infrared, near infrared and red, for the fires' burnt areas.
SWIR = {"bands": ["B12", "B8A", "B04"], "reflectance": (0.0, 0.4)}
COMPOSITES = {"natural": NATURAL, **({"swir": SWIR} if WILDFIRE else {})}
# Scenes whose natural colour has another stretch, by scene name.
NATURAL_REFLECTANCE = scenario.SENTINEL2_NATURAL_REFLECTANCE


def composites_for(scene: str, stretches: dict[str, tuple[float, float]] = NATURAL_REFLECTANCE) -> dict[str, dict]:
    """The composites of a scene, with its own natural-colour stretch if the scenario gives one."""
    if scene not in stretches:
        return COMPOSITES
    return {**COMPOSITES, "natural": {**NATURAL, "reflectance": tuple(stretches[scene])}}
# Narrow near infrared and short-wave infrared at 1.6 µm, both 20 m, for the NDMI.
NDMI_BANDS = ("B8A", "B11")
RAW_BANDS = ("B03", "B08", "SCL", *(NDMI_BANDS if WILDFIRE else ()))
# Scene classification: 0 no data, 1 saturated, 3 cloud shadow, 6 water, 8-9 cloud, 10 thin cirrus.
SCL_NO_DATA = (0, 1)
SCL_CLOUDY = (3, 8, 9, 10)
SCL_WATER = 6
WATER_RGBA = (30, 120, 220, 210)
NOTICE = (f"Contains modified Copernicus Sentinel data {scenario.PERIOD_START.year}, processed by Techseed "
          "(Planetary Computer, sentinel-2-l2a)")
LICENCE = "https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice (free and open)"


def dn_for(reflectance: float, baseline: str) -> int:
    """The Level-2A digital number of a surface reflectance; from baseline 04.00 the DN has an offset of 1000."""
    offset = 1000 if baseline >= "04.00" else 0
    return round(reflectance * 10000 + offset)


def datatake_items(prefix: str) -> list[dict]:
    """The catalogue items of one datatake over the map area, in id order."""
    day = datetime.strptime(prefix.split("_")[2][:8], "%Y%m%d").replace(tzinfo=timezone.utc)
    query = urlencode({
        "collections": COLLECTION, "bbox": ",".join(str(value) for value in BBOX), "limit": 50,
        "datetime": f"{day:%Y-%m-%dT%H:%M:%SZ}/{day + timedelta(days=1):%Y-%m-%dT%H:%M:%SZ}",
    })
    items = [item for item in get_json(f"{STAC}/search?{query}")["features"] if item["id"].startswith(prefix)]
    if not items:
        raise RuntimeError(f"no {COLLECTION} item named {prefix}… over the map area")
    return sorted(items, key=lambda item: item["id"])


def warp_steps(urls: dict[str, list[str]], scene: str, baseline: str, bbox: tuple[float, ...] = BBOX,
               size: tuple[int, int] = SIZE) -> tuple[list[list[str]], list[str]]:
    """The GDAL steps (geo_tools): one mosaic per band over the area, the natural-colour PNG and the raw bands;
    and the files to clean up."""
    west, south, east, north = bbox
    steps = []
    for band in sorted(urls):
        # The classification is a set of classes: nearest neighbour, never interpolated.
        method = "near" if band == "SCL" else "bilinear"
        steps.append(["gdalwarp", "-q", "--config", "GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR", "-overwrite", "-t_srs", "EPSG:4326",
                      "-te", *map(str, (west, south, east, north)), "-ts", str(size[0]), str(size[1]),
                      "-srcnodata", "0", "-dstnodata", "0", "-r", method, *(f"/vsicurl/{url}" for url in urls[band]), f"{band}.tif"])
    for band in RAW_BANDS:
        steps.append(["gdal_translate", "-q", "-of", "EHdr", f"{band}.tif", f"{scene}-{band}.bil"])
    for name, composite in composites_for(scene).items():
        low, high = (dn_for(value, baseline) for value in composite["reflectance"])
        steps.append(["gdalbuildvrt", "-q", "-separate", f"{name}.vrt", *(f"{band}.tif" for band in composite["bands"])])
        steps.append(["gdal_translate", "-q", "-ot", "Byte", "-scale", str(low), str(high), "1", "255", "-a_nodata", "0",
                      "-of", "PNG", f"{name}.vrt", f"{scene}-{name}.png"])
    return steps, [*(f"{band}.tif" for band in sorted(urls)), "*.vrt", "*.aux.xml"]


def warp_script(urls: dict[str, list[str]], scene: str, baseline: str, bbox: tuple[float, ...] = BBOX,
                size: tuple[int, int] = SIZE) -> str:
    """The steps as the GDAL container's shell script."""
    return geo_tools.shell_script(*warp_steps(urls, scene, baseline, bbox, size))


def focus_rows_cols(size: tuple[int, int], bbox: tuple[float, ...], area: tuple[float, ...]) -> tuple[slice, slice]:
    """The rows and columns of the image that cover the focus area."""
    west, south, east, north = bbox
    area_west, area_south, area_east, area_north = area
    width, height = size
    cols = slice(round((area_west - west) / (east - west) * width), round((area_east - west) / (east - west) * width))
    rows = slice(round((north - area_north) / (north - south) * height), round((north - area_south) / (north - south) * height))
    return rows, cols


def water_image(out: Path, scene: str, baseline: str, size: tuple[int, int] = SIZE) -> tuple[float, float, float]:
    """Write the NDWI water PNG; return the shares of the focus area with data, under cloud and with water, in per cent."""
    import numpy as np
    from PIL import Image

    width, height = size
    read = lambda band, kind: np.fromfile(out / f"{scene}-{band}.bil", dtype=kind).reshape(height, width)  # noqa: E731
    green, nir, scl = read("B03", "<u2").astype("f4"), read("B08", "<u2").astype("f4"), read("SCL", "u1")
    no_data = np.isin(scl, SCL_NO_DATA) | (green == 0) | (nir == 0)
    cloudy = np.isin(scl, SCL_CLOUDY)
    offset = dn_for(0.0, baseline)
    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi = ((green - offset) - (nir - offset)) / ((green - offset) + (nir - offset))
    water = ~no_data & ~cloudy & np.isfinite(ndwi) & (ndwi > 0)
    rgba = np.zeros((height, width, 4), dtype="u1")
    rgba[water] = WATER_RGBA
    Image.fromarray(rgba, "RGBA").save(out / f"{scene}-water.png", optimize=True)
    rows, cols = focus_rows_cols(size, BBOX, FOCUS_AREA)
    has_data = ~no_data[rows, cols]
    total = has_data.size
    share = lambda mask: round(100.0 * float(mask.sum()) / total, 1)  # noqa: E731
    return share(has_data), share(cloudy[rows, cols] & has_data), share(water[rows, cols])


def ndmi_image(out: Path, scene: str, baseline: str, size: tuple[int, int] = SIZE) -> None:
    """Write the NDMI PNG in Landsat's NDMI colours; clouds, cloud shadows, water and gaps transparent."""
    import numpy as np
    from PIL import Image

    width, height = size
    read = lambda band, kind: np.fromfile(out / f"{scene}-{band}.bil", dtype=kind).reshape(height, width)  # noqa: E731
    nir, swir, scl = read("B8A", "<u2").astype("f4"), read("B11", "<u2").astype("f4"), read("SCL", "u1")
    offset = dn_for(0.0, baseline)
    with np.errstate(divide="ignore", invalid="ignore"):
        ndmi = ((nir - offset) - (swir - offset)) / ((nir - offset) + (swir - offset))
    valid = (~np.isin(scl, (*SCL_NO_DATA, *SCL_CLOUDY, SCL_WATER)) & (nir > offset) & (swir > offset)
             & np.isfinite(ndmi))
    rgba = np.zeros((height, width, 4), dtype="u1")
    stops = np.array([stop for stop, _ in NDMI_COLOURS], dtype="f4")
    for channel in range(3):
        rgba[..., channel] = np.interp(np.nan_to_num(ndmi), stops, [rgb[channel] for _, rgb in NDMI_COLOURS]).round().astype("u1")
    rgba[..., 3] = np.where(valid, 230, 0)
    Image.fromarray(rgba, "RGBA").save(out / f"{scene}-ndmi.png", optimize=True)


def process(prefix: str, token: str, out: Path, tools: str = "docker") -> dict:
    """Cut one datatake into its PNGs and return its record for SOURCE.json."""
    items = datatake_items(prefix)
    baseline = items[0]["properties"].get("s2:processing_baseline", "05.00")
    bands = {band for composite in COMPOSITES.values() for band in composite["bands"]} | set(RAW_BANDS)
    urls = {band: [f"{item['assets'][band]['href']}?{token}" for item in items] for band in bands}
    run = run_gdal(warp_steps(urls, prefix, baseline), out, tools)
    if run.returncode != 0:
        raise RuntimeError(f"GDAL failed for {prefix}:\n{without_token(run.stderr, token)[-2000:]}")
    coverage, cloud, water = water_image(out, prefix, baseline)
    if WILDFIRE:
        ndmi_image(out, prefix, baseline)
    for band in RAW_BANDS:
        for suffix in (".bil", ".hdr", ".prj", ".bil.aux.xml"):
            (out / f"{prefix}-{band}{suffix}").unlink(missing_ok=True)
    return {
        "scene": prefix,
        "products": [item["id"] for item in items],
        "acquired_utc": items[0]["properties"]["datetime"][:19] + "Z",
        "processing_baseline": baseline,
        "focus_area_coverage_pct": coverage,
        "focus_area_cloud_pct": cloud,
        "focus_area_water_pct": water,
        "images": {
            **{name: {"file": f"{prefix}-{name}.png", "bands": "-".join(composite["bands"]), "reflectance": list(composite["reflectance"])}
               for name, composite in composites_for(prefix).items()},
            "water": {"file": f"{prefix}-water.png", "bands": "(B03-B08)/(B03+B08) > 0", "masked": "SCL 0, 1, 3, 8, 9, 10"},
            **({"ndmi": {"file": f"{prefix}-ndmi.png", "bands": "(B8A-B11)/(B8A+B11)", "index": [stop for stop, _ in NDMI_COLOURS],
                         "masked": "SCL 0, 1, 3, 6, 8, 9, 10"}} if WILDFIRE else {}),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--scenes", nargs="+", choices=sorted(SCENES), default=list(SCENES), help="which of the scenario's scenes")
    parser.add_argument("--out", type=Path, default=SENTINEL2_DIR, help=argparse.SUPPRESS)
    geo_tools.add_argument(parser)
    args = parser.parse_args(argv)
    tools = geo_tools.choice(args.tools)
    if not SCENES or args.out is None:
        parser.exit(1, f"fetch_sentinel2_scene: the scenario {scenario.NAME} has no Sentinel-2 scenes\n")
    token = get_json(TOKEN_URL)["token"]
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for role in args.scenes:
        try:
            record = process(SCENES[role], token, args.out, tools)
        except RuntimeError as exc:
            parser.exit(1, f"fetch_sentinel2_scene: {exc}\n")
        records.append({"role": role, **record})
        print(f"{role}: {record['scene']} ({len(record['products'])} rutor) – data över {record['focus_area_coverage_pct']} % "
              f"av fokusområdet, moln {record['focus_area_cloud_pct']} %, vatten {record['focus_area_water_pct']} %")
    west, south, east, north = BBOX
    (args.out / "SOURCE.json").write_text(json.dumps({
        "scenes": records,
        "bounds_west_south_east_north": [west, south, east, north],
        "size_px": list(SIZE),
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "processing": "gdalwarp to EPSG:4326 (bilinear; SCL nearest), a linear stretch to 8 bit; NDWI"
                      + (" and NDMI" if WILDFIRE else "") + " with numpy",
        **({"ndmi_colours": [[stop, list(rgb)] for stop, rgb in NDMI_COLOURS]} if WILDFIRE else {}),
        "notice": NOTICE,
        "licence": LICENCE,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
