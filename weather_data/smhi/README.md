# SMHI weather observations, 29 July – 14 August 2014

Hourly observations from the two SMHI automatic weather stations nearest to the
Västmanland 2014 fire that measure temperature, humidity, wind, gusts and
precipitation, for the period 2014-07-29 – 2014-08-14 (UTC).

Source: SMHI öppna data, meteorologiska observationer,
<https://opendata-download-metobs.smhi.se/>, quality-controlled archive
(`corrected-archive`), downloaded 2026-10-01. Licence: Creative Commons
Erkännande 4.0 SE; name SMHI as the source. Changes: the period was selected and
the hourly parameters of each station were merged into one file.

| File | Station | Position | Distance and direction from the fire's centre |
|---|---|---|---|
| `sala-a-96560.csv` | Sala A (96560) | 59.9093 N, 16.6843 E, 57 m | about 29 km east |
| `kloten-a-95540.csv` | Kloten A (95540) | 59.8703 N, 15.2522 E | about 52 km west |

The fire's centre is taken as 59.89 N, 16.175 E, the mean of the FIRMS
detections. `stations.json` lists units, SMHI parameter numbers and measurement
heights.

Columns (one row per UTC hour, 408 per station, no missing values):

| Column | SMHI parameter | Unit |
|---|---|---|
| `temp_c` | 1, air temperature, instantaneous, 2 m | °C |
| `rh_pct` | 6, relative humidity, instantaneous, 2 m | % |
| `wind_speed_ms` | 4, wind speed, 10-minute mean, 10 m | m/s |
| `wind_dir_deg` | 3, wind direction (from), 10-minute mean, 10 m | degrees |
| `gust_ms` | 21, gust, hourly maximum, 10 m | m/s |
| `precip_mm` | 7, precipitation, one-hour sum | mm |

Each value has a `*_quality` column with SMHI's quality code; all values in this
period are `G` (checked and approved).

Limitations:

- The stations are 29 and 52 km from the fire; local wind at the fire may have
  differed, and a large fire creates its own local winds.
- Wind direction 0 with speed 0 means calm.
- Check SMHI's parameter descriptions for exactly which interval an hourly sum or
  maximum refers to before relying on the hour.

`spinup/sala-a-96560.csv` has the same columns for Sala A, 2014-05-01 –
2014-07-28 (2,134 hours; a few values are missing or marked `Y`, suspect, by
SMHI). It runs the Fire Weather Index codes in from the start of the season for
the fire-spread forecast.

Regenerate with:

```bash
python3 tools/fetch_smhi_weather.py 96560 95540 --start 2014-07-29 --end 2014-08-14 --out weather_data/smhi
python3 tools/fetch_smhi_weather.py 96560 --start 2014-05-01 --end 2014-07-28 --out weather_data/smhi/spinup
```
