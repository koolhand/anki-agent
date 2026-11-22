#!/usr/bin/env python3
"""Offline checks for the media-sync wire format in anki.py (no network).

Run: python3 tests/test_media_sync.py
"""
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skill" / "anki"))

import anki  # noqa: E402


class UploadZip(unittest.TestCase):
    def test_metadata_names_each_file(self):
        body = anki.MediaSyncClient._upload_zip([("a.mp3", b"AAA"), ("b.mp3", b"BB")])
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            self.assertEqual(sorted(zf.namelist()), ["0", "1", "_meta"])
            meta = json.loads(zf.read("_meta"))
            self.assertEqual(meta, [["a.mp3", "0"], ["b.mp3", "1"]])
            self.assertEqual(zf.read("0"), b"AAA")
            self.assertEqual(zf.read("1"), b"BB")

    def test_entries_are_stored_not_deflated(self):
        body = anki.MediaSyncClient._upload_zip([("a.mp3", b"AAA")])
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            for info in zf.infolist():
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)


class Envelope(unittest.TestCase):
    def test_data_unwrapped(self):
        self.assertEqual(anki.MediaSyncClient._data(b'{"data": [1, 2], "err": ""}'), [1, 2])

    def test_error_raised(self):
        with self.assertRaises(anki.AnkiError):
            anki.MediaSyncClient._data(b'{"err": "file was modified on another device"}')


if __name__ == "__main__":
    unittest.main(verbosity=2)
