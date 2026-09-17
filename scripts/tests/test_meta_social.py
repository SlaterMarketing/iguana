"""Offline tests for scripts/meta-social.py (captions and the image header parser). No network.

    python3 -m unittest discover -s scripts/tests -v
"""

import importlib.util
import pathlib
import re
import struct
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "meta-social.py"
spec = importlib.util.spec_from_file_location("meta_social", SCRIPT)
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)

VENUE = {"name": "Iguana Comedy", "city": "Playa del Carmen"}


def spanish_open_mic(**overrides):
    event = {"slug": "playa-del-carmen-2026-09-22", "name": "Noche de Open Mic - Espanol!", "date": "2026-09-22",
             "showTime": None, "doorsOpen": None, "language": "es", "tags": ["open-mic"], "priceFrom": 5000,
             "priceCurrency": "MXN", "status": "on-sale", "venue": VENUE}
    event.update(overrides)
    return event


def english_show(**overrides):
    event = {"slug": "big-show", "name": "Big Show \u2014 Live", "date": "2026-10-03", "showTime": "21:00",
             "doorsOpen": "20:30", "language": "en", "tags": [], "priceFrom": 25050, "priceCurrency": "usd",
             "status": "on-sale", "venue": VENUE}
    event.update(overrides)
    return event


def png(width, height):
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"


def jpeg(width, height, sof=0xC0):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    dqt = b"\xff\xdb" + struct.pack(">H", 4) + b"\x00\x00"
    frame = bytes([0xFF, sof]) + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + dqt + frame + b"\xff\xda\x00\x02" + b"\x00" * 10 + b"\xff\xd9"


class CaptionTests(unittest.TestCase):
    def test_spanish_open_mic_both_puts_spanish_first(self):
        caption = ms.build_caption(spanish_open_mic(), "both", "facebook")
        spanish, english = caption.split("\n\n* * *\n\n")
        self.assertTrue(spanish.startswith("Noche de Open Mic: Espanol!\nMartes 22 de septiembre\n"))
        self.assertIn("Entrada libre. Reserva tu lugar por 50 MXN con bebida gratis.", spanish)
        self.assertIn("https://iguanacomedy.com/es/eventos/playa-del-carmen-2026-09-22/", spanish)
        self.assertIn("Tuesday, September 22", english)
        self.assertIn("Free entry. Reserve a seat for 50 MXN and get a free drink.", english)
        self.assertIn("Show in Spanish.", english)
        self.assertIn("https://iguanacomedy.com/en/events/playa-del-carmen-2026-09-22/", english)
        self.assertTrue(caption.endswith("#PlayaDelCarmen #StandUp #Comedia #ComediaEnVivo #ComedyClub #OpenMic"))

    def test_instagram_has_no_url_and_says_link_in_bio(self):
        for event in (spanish_open_mic(), english_show()):
            caption = ms.build_caption(event, "both", "instagram")
            self.assertNotRegex(caption, r"https?://")
            self.assertIn("link in bio", caption)
            self.assertIn("link en la bio", caption)
            self.assertEqual(ms.caption_problems(caption, "instagram"), [])

    def test_english_show_first_with_doors_time_and_price(self):
        caption = ms.build_caption(english_show(), "both", "facebook")
        english, spanish = caption.split("\n\n* * *\n\n")
        self.assertTrue(english.startswith("Big Show: Live\nSaturday, October 3, doors 8:30 PM, show 9 PM\n"))
        self.assertIn("Tickets from 250.50 USD.", english)
        self.assertIn("Sábado 3 de octubre, puertas 20:30 h, show 21:00 h", spanish)
        self.assertIn("Show en inglés.", spanish)

    def test_single_language_has_no_separator_and_no_language_note(self):
        caption = ms.build_caption(english_show(), "en", "facebook")
        self.assertNotIn("* * *", caption)
        self.assertNotIn("Show", caption.replace("Big Show", ""))
        self.assertTrue(caption.endswith("#PlayaDelCarmen #StandUp #ComedyClub"))

    def test_no_price_line_when_price_unknown_and_free_wording_when_zero(self):
        self.assertIsNone(ms.price_line(english_show(priceFrom=None), "en"))
        self.assertEqual(ms.price_line(english_show(priceFrom=0), "es"), "Entrada libre.")
        self.assertEqual(ms.price_line(spanish_open_mic(priceFrom=None), "en"), "Free entry. Reserve a seat and get a free drink.")

    def test_never_emits_dashes(self):
        event = english_show(name="A \u2013 B\u2014C - D", venue={"name": "Bar \u2014 Uno", "city": "Tulum"})
        for platform in ("facebook", "instagram"):
            caption = ms.build_caption(event, "both", platform)
            self.assertIsNone(re.search("[\u2013\u2014]| - ", caption), caption)

    def test_venue_falls_back_to_brand(self):
        self.assertEqual(ms.venue_line({"venue": None}), "Iguana Comedy, Playa del Carmen")

    def test_time_formats(self):
        self.assertEqual(ms.format_time("00:15", "en"), "12:15 AM")
        self.assertEqual(ms.format_time("12:00", "en"), "12 PM")
        self.assertEqual(ms.format_time("20:00:00", "es"), "20:00 h")
        self.assertIsNone(ms.format_time("soon", "en"))


class ImageTests(unittest.TestCase):
    def test_png_dimensions(self):
        self.assertEqual(ms.image_dimensions(png(1080, 1350)), ("png", 1080, 1350))

    def test_jpeg_baseline_and_progressive(self):
        self.assertEqual(ms.image_dimensions(jpeg(1600, 900)), ("jpeg", 1600, 900))
        self.assertEqual(ms.image_dimensions(jpeg(640, 800, sof=0xC2)), ("jpeg", 640, 800))

    def test_rejects_other_formats_and_truncation(self):
        with self.assertRaises(ValueError):
            ms.image_dimensions(b"GIF89a\x01\x00\x01\x00")
        with self.assertRaises(ValueError):
            ms.image_dimensions(b"\x89PNG\r\n\x1a\n\x00\x00")
        with self.assertRaises(ValueError):
            ms.image_dimensions(b"\xff\xd8\xff\xda\x00\x02")  # scan data before any frame header

    def test_instagram_aspect_ratio_limits(self):
        self.assertIsNone(ms.ratio_problem(1080, 1350))   # 4:5 exactly
        self.assertIsNone(ms.ratio_problem(1910, 1000))   # 1.91:1 exactly
        self.assertIsNone(ms.ratio_problem(1080, 1080))
        self.assertIn("taller", ms.ratio_problem(1080, 1920))  # 9:16 story format
        self.assertIn("wider", ms.ratio_problem(2000, 1000))


if __name__ == "__main__":
    unittest.main()
