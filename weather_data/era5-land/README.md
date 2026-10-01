# ERA5-Land hourly reanalysis, 29 July – 14 August 2014

Hourly ERA5-Land values on the 0.1° grid (about 11 × 6 km) over 59.7–60.1° N,
15.8–16.5° E (5 × 8 = 40 grid points), 2014-07-29 00:00 – 2014-08-14 23:00 UTC,
used for the wind arrows in the fire map.

Source: Copernicus Climate Change Service (C3S) Climate Data Store, dataset
`reanalysis-era5-land`, doi:10.24381/cds.e2161bac, downloaded 2026-10-01.
Licence: CC BY 4.0. Attribution: "Contains modified Copernicus Climate Change
Service information (ERA5-Land)". Changes: the area and period were selected,
and wind speed, wind direction, relative humidity and hourly precipitation were
derived as described below.

| Column | Meaning | Unit |
|---|---|---|
| `time_utc` | Valid time | UTC |
| `latitude`, `longitude` | Grid point | degrees, WGS 84 |
| `u10_ms`, `v10_ms` | 10 m wind towards east and north (ERA5-Land `u10`, `v10`) | m/s |
| `wind_speed_ms` | √(u² + v²) | m/s |
| `wind_from_deg` | Direction the wind blows from, 0 = north, 90 = east | degrees |
| `t2m_c`, `d2m_c` | 2 m temperature and dewpoint (`t2m`, `d2m`) | °C |
| `rh_pct` | Relative humidity from `t2m` and `d2m` (Magnus formula) | % |
| `precip_mm` | Precipitation in the hour ending at `time_utc`, from the accumulated `tp` | mm |

Limitations:

- ERA5-Land is a model reanalysis, not a measurement. It does not include the
  fire's own effect on the local wind.
- A 0.1° grid smooths local variation; values differ from the SMHI stations
  (for example 31.5 °C here and 34.4 °C at Sala A at 12 UTC on 4 August).
- Precipitation is modelled and can differ from station measurements.

`era5-land-fwi-spinup-2014.csv` has the same columns for 2014-05-01 – 2014-07-28
at the grid points 59.9 N 16.1 E and 59.9 N 16.2 E. It is used only to run the
Fire Weather Index codes in from the start of the season before the fire.

Regenerate (needs the repository's `.venv` with `cdsapi` and `netCDF4`, a CDS
token in `~/.cdsapirc` and the accepted dataset licence):

```bash
.venv/bin/python tools/fetch_era5_land.py --area 60.1,15.8,59.7,16.5 --start 2014-07-29 --end 2014-08-14 --raw-dir /tmp/era5-land --out weather_data/era5-land/era5-land-vastmanland-2014.csv
.venv/bin/python tools/fetch_era5_land.py --area 59.95,16.1,59.85,16.25 --start 2014-05-01 --end 2014-07-28 --raw-dir /tmp/era5-land-spinup --out weather_data/era5-land/era5-land-fwi-spinup-2014.csv
```
