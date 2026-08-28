"""Edge cases for the persisted settings store and the theme engine."""

import json
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
try:
    from tests.helpers import isolated_env
except ImportError:
    from helpers import isolated_env

from spacekids import settings
from spacekids import theme


class TestSettings(unittest.TestCase):
    def test_defaults_and_merge(self):
        with isolated_env():
            data = settings.all()
            self.assertEqual(data["theme"], "Space Night")
            self.assertEqual(data["stars"], 200)
            self.assertEqual(data["playback"], 1)

    def test_get_returns_defaults(self):
        with isolated_env():
            self.assertEqual(settings.get("theme"), "Space Night")
            self.assertEqual(settings.get("stars"), 200)
            self.assertIsNone(settings.get("missing.key"))

    def test_get_explicit_default(self):
        with isolated_env():
            self.assertEqual(settings.get("missing.key", "fallback"),
                             "fallback")

    def test_set_and_get_roundtrip(self):
        with isolated_env():
            settings.set("stars", 333)
            settings.set("theme", "Aurora")
            settings.set("playback", 3)
            self.assertEqual(settings.get("stars"), 333)
            self.assertEqual(settings.get("theme"), "Aurora")
            self.assertEqual(settings.get("playback"), 3)

    def test_types_preserved(self):
        with isolated_env():
            settings.set("stars", 300)
            settings.set("theme", "Sunny Day")
            self.assertIsInstance(settings.get("stars"), int)
            self.assertIsInstance(settings.get("theme"), str)

    def test_reset(self):
        with isolated_env():
            settings.set("stars", 500)
            settings.reset()
            self.assertEqual(settings.get("stars"), 200)
            self.assertEqual(settings.get("playback"), 1)

    def test_corrupt_file_gives_defaults(self):
        with isolated_env() as tmp:
            with open(settings._path(), "w", encoding="utf-8") as fh:
                fh.write("garbage[[[")
            self.assertEqual(settings.get("theme"), "Space Night")
            self.assertEqual(settings.get("stars"), 200)

    def test_non_scalar_values_dropped_on_read(self):
        with isolated_env():
            with open(settings._path(), "w", encoding="utf-8") as fh:
                json.dump({"theme": "Sunny Day", "stars": 250,
                           "playback": 2, "list": [1, 2, 3],
                           "dict": {"a": 1}, "nested": None}, fh)
            data = settings.all()
            self.assertEqual(data["theme"], "Sunny Day")
            self.assertEqual(data["stars"], 250)
            self.assertEqual(data["playback"], 2)
            self.assertNotIn("list", data)
            self.assertNotIn("dict", data)
            self.assertNotIn("nested", data)

    def test_missing_file(self):
        with isolated_env() as tmp:
            self.assertFalse(os.path.exists(settings._path()))
            self.assertEqual(settings.get("theme"), "Space Night")

    def test_reset_missing_is_silent(self):
        with isolated_env():
            settings.reset()  # nothing there yet
            self.assertEqual(settings.get("stars"), 200)


class TestTheme(unittest.TestCase):
    def setUp(self):
        self._name = theme.active_name()

    def tearDown(self):
        theme.set_active(self._name, persist=False)

    def test_palettes_complete(self):
        keys = set(theme._KEYS)
        for name in theme.themes():
            pal = theme._PALETTES[name]
            self.assertEqual(set(pal), keys, name)
            for key, val in pal.items():
                self.assertIsInstance(val, str)
                self.assertTrue(val.startswith("#"), (name, key, val))
                self.assertEqual(len(val), 7, (name, key, val))

    def test_themes_list(self):
        self.assertEqual(theme.themes(),
                         ["Space Night", "Rainbow Kids", "Sunny Day",
                          "Moonlight", "Aurora"])

    def test_attribute_forwarding(self):
        for name in theme.themes():
            theme.set_active(name, persist=False)
            self.assertEqual(theme.BG, theme._PALETTES[name]["BG"])
            self.assertEqual(theme.C_SAT, theme._PALETTES[name]["C_SAT"])
            self.assertEqual(theme.active_name(), name)

    def test_unknown_attribute_raises(self):
        with self.assertRaises(AttributeError):
            theme.DOES_NOT_EXIST

    def test_set_active_unknown_keeps(self):
        before = theme.active_name()
        theme.set_active("Not A Theme", persist=False)
        self.assertEqual(theme.active_name(), before)

    def test_set_active_same_is_noop(self):
        theme.set_active(theme.active_name(), persist=False)
        fired = []
        theme.on_change(lambda: fired.append(1))
        theme.set_active(theme.active_name(), persist=False)
        self.assertEqual(fired, [])
        theme.set_active("Aurora", persist=False)
        self.assertEqual(fired, [1])

    def test_listener_fires(self):
        fired = []
        theme.on_change(lambda: fired.append(theme.active_name()))
        theme.set_active("Moonlight", persist=False)
        self.assertEqual(fired, ["Moonlight"])
        theme.set_active("Rainbow Kids", persist=False)
        self.assertEqual(fired[-1], "Rainbow Kids")

    def test_persist_flag_writes_settings(self):
        with isolated_env():
            theme.set_active("Sunny Day")  # persist=True
            self.assertEqual(settings.get("theme"), "Sunny Day")
            theme.set_active("Moonlight", persist=False)
            self.assertEqual(settings.get("theme"), "Sunny Day")

    def test_blurbs(self):
        for name in theme.themes():
            self.assertTrue(theme.blurb(name), name)
        self.assertEqual(theme.blurb("nope"), "")

    def test_css_for_roles(self):
        theme.set_active("Space Night", persist=False)
        self.assertTrue(theme.css_for("text").startswith("color: "))
        self.assertTrue(theme.css_for("muted").startswith("color: "))
        self.assertTrue(theme.css_for("dim").startswith("color: "))
        self.assertTrue(theme.css_for("accent").startswith("color: "))
        self.assertIn("border-left", theme.css_for("fact"))
        self.assertTrue(theme.css_for("bogus").startswith("color: "))

    def test_chip_color(self):
        col = theme.chip_color("ok")
        self.assertEqual(col.name().lower(),
                         theme._PALETTES[theme.active_name()]["OK"].lower())
        theme.set_active("Rainbow Kids", persist=False)
        self.assertEqual(theme.chip_color("err").name().lower(),
                         theme.RAINBOW_KIDS["ERR"].lower())
        self.assertEqual(theme.chip_color("odd").name().lower(),
                         theme.RAINBOW_KIDS["TEXT_MUT"].lower())

    def test_chip_color_aliases(self):
        self.assertEqual(theme.chip_color("error").name(),
                         theme.chip_color("err").name())
        self.assertEqual(theme.chip_color("no").name(),
                         theme.chip_color("err").name())

    def test_build_stylesheet(self):
        for name in theme.themes():
            theme.set_active(name, persist=False)
            css = theme.build_stylesheet()
            self.assertIn("background:", css)
            self.assertIn("font-family", css)
            self.assertIn(theme._PALETTES[name]["ACCENT"].upper(), css.upper())

    def test_fonts(self):
        theme.set_active("Space Night", persist=False)
        f = theme.font(12, bold=True)
        self.assertEqual(f.pointSize(), 12)
        self.assertTrue(f.bold())
        fm = theme.font(9, mono=True)
        self.assertEqual(fm.family(), theme.MONO)
        self.assertEqual(theme.FAMILY, "Segoe UI")


if __name__ == "__main__":
    unittest.main(verbosity=2)