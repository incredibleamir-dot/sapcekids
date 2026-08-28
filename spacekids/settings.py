"""Small persisted settings store (JSON in the user's home folder).

Like the places file, the path can be moved with ``SPACEKIDS_SETTINGS`` so
tests never touch the real profile.  Everything is just a dict of strings and
numbers - no importing the UI, so ``theme`` can depend on this module safely.
"""

import json
import os

DEFAULTS = {
    "theme": "Space Night",
    "stars": 200,           # space scenes star-field density
    "playback": 1,          # PlayBar default speed index (1 == 2x)
}


def _path():
    env = os.environ.get("SPACEKIDS_SETTINGS")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), ".spacekids",
                        "settings.json")


def _read():
    try:
        with open(_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {str(k): v for k, v in data.items() if isinstance(v, (str, int, float, bool))}
    except (FileNotFoundError, ValueError):
        return {}
    except Exception:
        return {}


def _write(data):
    path = _path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass


def all():
    data = dict(DEFAULTS)
    data.update(_read())
    return data


def get(key, default=None):
    if default is None and key in DEFAULTS:
        default = DEFAULTS[key]
    return all().get(key, default)


def set(key, value):
    data = _read()
    data[key] = value
    _write(data)


def reset():
    try:
        os.remove(_path())
    except OSError:
        pass