"""Test utils.py."""
from unittest import TestCase
import productionsystem.utils as utils


class TestUtils(TestCase):
    """Test case for utils.py."""

    def test_expand_path(self):
        """test expand_path function."""
        self.assertEqual(utils.expand_path("~"), r"C:\Users\infer")
        self.assertEqual(utils.expand_path("~/$OS"), r"C:\Users\infer\Windows_NT")

    def test_igroup(self):
        """test igroup generator."""
        input = list(range(11))
        self.assertEqual(list(utils.igroup(input, 3)), [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10]])


class TestTemporaryFileManagerContext(TestCase):
    """Test case for the TemporaryFileManagerContext class."""

    def test__init__(self):
        pass

    def test__enter__(self):
        pass

    def test__exit__(self):
        pass

    def test_new_file(self):
        pass

    def test_new_dir(self):
        pass
