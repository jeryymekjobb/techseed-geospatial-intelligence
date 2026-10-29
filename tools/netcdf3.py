"""Read the variables of a classic NetCDF file (format 1 or 2, the CDF header) with numpy.

Sentinel-1's ocean products (OCN) are classic NetCDF, which h5py cannot open, and the demo's
.venv has no netCDF4 or SciPy; the format is simple enough to read here. Only variables without
the record dimension are read, which is all the OCN product's wind grid needs.
"""

from __future__ import annotations

import struct
from typing import Any

import numpy as np

# NetCDF's types: byte, char, short, int, float, double, all big-endian.
TYPES = {1: ">i1", 2: "S1", 3: ">i2", 4: ">i4", 5: ">f4", 6: ">f8"}


class NetCDF3:
    def __init__(self, data: bytes) -> None:
        if data[:3] != b"CDF" or data[3] not in (1, 2):
            raise ValueError("not a classic NetCDF file")
        self.data = data
        self.position = 4
        offset_size = 8 if data[3] == 2 else 4
        self._u32()  # the number of records
        dimensions = self._list(lambda: (self._name(), self._u32()))
        self.attributes = self._attributes()
        self.variables: dict[str, tuple[list[int], int, int, dict[str, Any]]] = {}
        for _ in range(self._count()):
            name = self._name()
            shape = [dimensions[self._u32()][1] for _ in range(self._u32())]
            attributes = self._attributes()
            kind = self._u32()
            self._u32()  # the variable's size
            begin = struct.unpack(">Q" if offset_size == 8 else ">I", data[self.position:self.position + offset_size])[0]
            self.position += offset_size
            self.variables[name] = (shape, kind, begin, attributes)

    def _u32(self) -> int:
        value = struct.unpack(">I", self.data[self.position:self.position + 4])[0]
        self.position += 4
        return value

    def _count(self) -> int:
        self._u32()  # the list's tag, or zero when absent
        return self._u32()

    def _list(self, read) -> list:
        return [read() for _ in range(self._count())]

    def _name(self) -> str:
        size = self._u32()
        text = self.data[self.position:self.position + size].decode()
        self.position += (size + 3) // 4 * 4
        return text

    def _values(self, kind: int, count: int) -> Any:
        dtype = np.dtype(TYPES[kind])
        raw = self.data[self.position:self.position + count * dtype.itemsize]
        self.position += (count * dtype.itemsize + 3) // 4 * 4
        return raw.decode(errors="replace") if kind == 2 else np.frombuffer(raw, dtype)

    def _attributes(self) -> dict[str, Any]:
        result = {}
        for _ in range(self._count()):
            name = self._name()
            kind = self._u32()
            result[name] = self._values(kind, self._u32())
        return result

    def array(self, name: str) -> np.ndarray:
        shape, kind, begin, _ = self.variables[name]
        dtype = np.dtype(TYPES[kind])
        return np.frombuffer(self.data, dtype, int(np.prod(shape)), begin).reshape(shape)
