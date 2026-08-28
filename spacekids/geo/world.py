"""World land raster (coarse 1-degree equirectangular) for the Spotter map.

Generated once from Natural Earth's 110m land GeoJSON - packed as hex rows so
the app keeps zero runtime internet needs.  ``land_cells()`` returns a list of
(cell_x, cell_y) integer cells that are land, ready for the painter.
"""

import numpy as np

from . import world_data as _data

W = _data.WORLD_W
H = _data.WORLD_H

_CELLS = None


def _decode():
    mask = np.zeros((H, W), dtype=bool)
    for j, row in enumerate(_data.WORLD_ROWS):
        raw = bytes.fromhex(row)
        bits = int.from_bytes(raw, "big")
        for i in range(W):
            mask[j, i] = bool(bits & (1 << (W - 1 - i)))
    return mask


def land_mask():
    return _decode()


def land_cells():
    """Precomputed list of (x, y) land cells in raster space (y = row)."""
    global _CELLS
    if _CELLS is None:
        _CELLS = list(zip(*np.nonzero(_decode())[::-1]))
        _CELLS = [(int(x), int(y)) for x, y in _CELLS]
    return _CELLS


def latlon_to_cell(lat_deg, lon_deg):
    """Raster cell (x, y) for a geographic coordinate."""
    x = int(np.clip((lon_deg + 180.0) / 360.0 * W, 0, W - 1))
    y = int(np.clip((90.0 - lat_deg) / 180.0 * H, 0, H - 1))
    return x, y