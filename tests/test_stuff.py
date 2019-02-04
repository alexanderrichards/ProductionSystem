"""Test Stuff."""
from unittest import TestCase
import pkg_resources
from productionsystem.config import ConfigSystem


# def setup_module(module):
#     """ setup any state specific to the execution of the given module."""
#     config_instance = ConfigSystem.setup(None)  # pylint: disable=no-member
#     config_instance.entry_point_map = pkg_resources.get_entry_map('productionsystem')
#     return config_instance


class TestStuff(TestCase):
    """Test case."""

    def test_bob(self):
        """test bob."""
        pass
