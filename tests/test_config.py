import tempfile
import unittest
from pathlib import Path

from jobapply.config import AppConfig


class ConfigTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            config = AppConfig(board_limit=42, per_company=3)
            config.save(path)
            loaded = AppConfig.load(path)
            self.assertEqual(loaded.board_limit, 42)
            self.assertEqual(loaded.per_company, 3)
