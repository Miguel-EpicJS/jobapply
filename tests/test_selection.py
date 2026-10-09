import unittest

from jobapply.selection import parse_id_ranges


class SelectionTests(unittest.TestCase):
    def test_mixed_ranges(self):
        self.assertEqual(parse_id_ranges("1,2-5,8,5"), [1, 2, 3, 4, 5, 8])

    def test_rejects_invalid_ranges(self):
        with self.assertRaises(ValueError):
            parse_id_ranges("5-2")
