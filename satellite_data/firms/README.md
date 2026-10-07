# NASA FIRMS archive extracts, Sweden, 2014 and 2018

Raw fire-detection archive downloads from NASA FIRMS, used for the Västmanland
2014 and the Ljusdal/Kårböle 2018 wildfire scenarios. The files are unchanged as downloaded; `SHA256SUMS` lists
their checksums; check them with `sha256sum -c SHA256SUMS` in this directory.

Source: NASA FIRMS (Fire Information for Resource Management System), archive
download, <https://firms.modaps.eosdis.nasa.gov/>. Downloaded 2026-10-01 (2014) and
2026-10-07 (2018). NASA
asks users of FIRMS data to acknowledge the source.

| Request | Product | Rows | Dates (UTC) | Coverage |
|---|---|---:|---|---|
| 816007 | MODIS Collection 6.1 (`M-C61`), Terra and Aqua | 562 | 2014-07-01 – 2014-08-30 | 55.45–68.05° N, 11.93–23.32° E |
| 816008 | VIIRS S-NPP Collection 2 (`SV-C2`), 375 m | 2,594 | 2014-07-01 – 2014-08-31 | 55.37–68.05° N, 11.42–23.33° E |
| 818930 | MODIS Collection 6.1 (`M-C61`), Terra and Aqua | 1,140 | 2018-03-19 – 2018-12-29 | 55.68–67.53° N, 11.78–23.39° E |
| 818934 | VIIRS S-NPP Collection 2 (`SV-C2`), 375 m | 6,629 | 2018-01-02 – 2018-12-31 | 55.39–68.11° N, 11.18–23.39° E |
| 818932 | VIIRS NOAA-20 Collection 2 (`J1V-C2`), 375 m | 6,257 | 2018-04-01 – 2018-12-31 | 55.41–67.88° N, 11.16–23.40° E |

Dates and coverage are those observed in the files, not the request parameters.
Each `fire_archive_*.csv` is byte-identical to the CSV inside its `DL_FIRE_*.zip`.
`Readme.txt` (and the identical copy `Readme_sv.txt`) only links to the FIRMS
readme at <https://firms.modaps.eosdis.nasa.gov/download/Readme.txt>.

Data notes:

- `acq_date` and `acq_time` (HHMM) are UTC.
- A detection is a satellite pixel with a thermal anomaly, not a mapped fire
  perimeter.
- `type` 0 is a presumed vegetation fire; other values (static land sources,
  offshore) are not part of the fire.
- In the VIIRS S-NPP files, the `instrument` column contains `SNPP`; in the NOAA-20
  file the `satellite` is `N20` and the `instrument` `VIIRS`. VIIRS `confidence` is
  `l`, `n` or `h`; MODIS `confidence` is 0–100.
- The 2018 requests covered the whole year; the Readme.txt in their zips is the same
  one-line link as in 2014's, so it is not kept twice.

Derived layers for the scenario are produced with `tools/firms_extract.py`, for
example:

```bash
python3 tools/firms_extract.py satellite_data/firms/fire_archive_M-C61_816007.csv satellite_data/firms/fire_archive_SV-C2_816008.csv --out data/firms-vastmanland-2014 --start 2014-07-29 --end 2014-08-14 --bbox 59.70,60.10,15.90,16.50
```
