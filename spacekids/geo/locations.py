"""Places library shared by the satellite pages.

A handful of famous cities are always there; places the kid adds are saved to
a JSON file in the user's home directory so they stick around after quitting.
Set ``SPACEKIDS_LOCATIONS`` to move that file somewhere else (handy for tests).
"""

import json
import os

from ..astro import satellites

BUILTIN = [{"name": name, "lat": float(lat), "lon": float(lon), "user": False}
           for name, lat, lon in satellites.CITIES]


def _store_path():
    env = os.environ.get("SPACEKIDS_LOCATIONS")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), ".spacekids",
                        "locations.json")


def _read_user():
    try:
        with open(_store_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [dict(rec) for rec in data if isinstance(rec, dict)]
    except (FileNotFoundError, ValueError):
        return []
    except Exception:
        return []


def _clean(recs):
    out = []
    for rec in recs:
        try:
            name = str(rec.get("name")).strip()
            lat = float(rec.get("lat"))
            lon = float(rec.get("lon"))
        except (TypeError, ValueError):
            continue
        if name and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            out.append({"name": name, "lat": lat, "lon": lon, "user": True})
    return out


def _write(recs):
    path = _store_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(recs, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass


def all_locations():
    """Built-in cities followed by the user's saved places."""
    return BUILTIN + _clean(_read_user())


def user_names():
    return [rec["name"] for rec in all_locations() if rec["user"]]


def find(name):
    for rec in all_locations():
        if rec["name"] == name:
            return rec
    return None


def add_location(name, lat, lon):
    name = str(name).strip()
    if not name or not (-90.0 <= float(lat) <= 90.0) or not (-180.0 <= float(lon) <= 180.0):
        raise ValueError("place must have a name and a real latitude/longitude")
    recs = _clean(_read_user())
    found = next((rec for rec in recs if rec["name"] == name), None)
    rec = {"name": name, "lat": round(float(lat), 4),
           "lon": round(float(lon), 4), "user": True}
    if found:
        found.update(rec)
    else:
        recs.append(rec)
    _write(recs)
    return name


def remove_location(name):
    recs = _clean(_read_user())
    recs = [rec for rec in recs if rec["name"] != name]
    _write(recs)