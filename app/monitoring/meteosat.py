"""Meteosat's cloud mask over the area, live, as the Flen scenarios show it (app/backend/meteosat_clm.py,
tools/fetch_meteosat_clm.py): the cloudy share of the area's SEVIRI pixels every 15 minutes.

EUMETSAT's Cloud Mask (MSG, 0 degree; EO:EUM:DAT:MSG:CLM) classes every pixel of the full disk as
clear over water, clear over land, cloud or no data; a product is about 550 kB and comes about an
hour after its time. The share says why an optical image (sentinel2.py) is old or missing: it has
been cloudy. A few kilometres per pixel this far north; the screens say so.

The newest product is fetched when it is newer than the last, read with the scenarios' tool and
thrown away; the last day's shares are kept in data/monitoring/<area>/meteosat-clm/clm.json. It needs
the EUMETSAT API key in ~/.eumdac/credentials and eumdac and eccodes (tools/requirements-meteosat.txt);
without them the source says so and the rest goes on. The product is Core under EUMETSAT's data
policy (CC BY 4.0).
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

COLLECTION = "EO:EUM:DAT:MSG:CLM"
# In the form EUMETSAT's data policy (article 6.3) asks for.
ATTRIBUTION = "Contains modified EUMETSAT Meteosat product {year} (MSG Cloud Mask, CC BY 4.0)"
KEEP = timedelta(days=1)
SEARCH_BACK = timedelta(hours=3)
# A search of the Data Store takes seconds, and a product comes every 15 minutes.
ASK_EVERY = timedelta(minutes=10)
# The product's satellite (MSG3-SEVI-...) as the screens name it.
SATELLITES = {"MSG1": "Meteosat-8", "MSG2": "Meteosat-9", "MSG3": "Meteosat-10", "MSG4": "Meteosat-11"}


def satellite_name(product_id: str) -> str:
    code = product_id.split("-", 1)[0]
    return SATELLITES.get(code, code)


class CloudMask:
    def __init__(self, bbox: tuple[float, float, float, float], data_dir: Path) -> None:
        self.bbox = bbox
        self.dir = data_dir / "meteosat-clm"
        self.file = self.dir / "clm.json"
        self.index_file = self.dir / "index.npy"
        try:
            self.saved = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.saved = {"series": []}
        self.asked: datetime | None = None

    @property
    def meta(self) -> dict[str, Any] | None:
        series = self.saved.get("series") or []
        if not series:
            return None
        last = series[-1]
        return {**last, "series": series, "pixels_in_area": self.saved.get("pixels_in_area"),
                "attribution": ATTRIBUTION.format(year=last["time_utc"][:4])}

    def update(self, now: datetime | None = None) -> dict[str, Any] | None:
        import eumdac  # only the monitoring's Meteosat source needs it
        import numpy

        from tools.fetch_meteosat_clm import area_index, cloud_pct, read_grib
        from tools.fetch_meteosat_cth import CREDENTIALS, download, time_of

        from app.monitoring.sources import MissingKey

        now = now or datetime.now(timezone.utc)
        if not CREDENTIALS.is_file():
            raise MissingKey(f"ingen EUMETSAT-nyckel i {CREDENTIALS}")
        if self.asked and now - self.asked < ASK_EVERY:
            return self.meta
        self.asked = now
        key, secret = CREDENTIALS.read_text(encoding="utf-8").strip().split(",", 1)
        token = eumdac.AccessToken((key, secret))
        found = list(eumdac.DataStore(token).get_collection(COLLECTION).search(dtstart=now - SEARCH_BACK, dtend=now))
        if not found:
            return self.meta
        newest = max(found, key=lambda item: time_of(str(item)))
        stamp = time_of(str(newest))
        series = self.saved.get("series") or []
        if series and series[-1]["time_utc"] >= stamp:
            return self.meta
        self.dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.dir) as work:
            data = download(newest, token, Path(work) / f"{newest}.zip").read_bytes()
        known = self.index_file.is_file()
        size, values, lats, lons = read_grib(data, positions=not known)
        index = numpy.load(self.index_file) if known else area_index(lats, lons, size, self.bbox)
        if not known:
            numpy.save(self.index_file, index)
        since = (now - KEEP).strftime("%Y-%m-%dT%H:%M:%SZ")
        series = [item for item in series if item["time_utc"] >= since]
        series.append({"time_utc": stamp, "cloud_pct": cloud_pct(values[index]), "satellite": satellite_name(str(newest))})
        self.saved = {"pixels_in_area": int(len(index)), "series": series}
        self.file.write_text(json.dumps(self.saved, ensure_ascii=False) + "\n", encoding="utf-8")
        return self.meta
