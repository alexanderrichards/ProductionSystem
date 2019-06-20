"""DIRAC RPC Client utilities."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin

import logging
from contextlib import contextmanager
import copy
import rpyc

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

# This is not strictly necessary as all works without it when deep copying
# However it bypasses the standard deepcopy implementation
# which does type detection for unknown netref type and uses getattr('__deepcopy__')
# which causes an not found exception server side. This tidy's up server side log since we know
# netref<class='__builtin__.dict'> behaves as a dict
# NOTE can't use dict or list as py2 compatibility layer rebinds these so use {}.__class__ etc.
netref_cache = rpyc.core.netref.builtin_classes_cache
netref_dict = netref_cache.get('builtins.dict', netref_cache[('dict', {}.__class__.__module__)])
copy._deepcopy_dispatch[netref_dict] = copy._deepcopy_dict
# Add the other basic collection types
netref_list = netref_cache.get('builtins.list', netref_cache[('list', [].__class__.__module__)])
copy._deepcopy_dispatch[netref_list] = copy._deepcopy_list
netref_tuple = netref_cache.get('builtins.tuple', netref_cache[('tuple', tuple.__module__)])
copy._deepcopy_dispatch[netref_tuple] = copy._deepcopy_tuple


# Used in Solid to list the DIRAC file catalogue
@contextmanager
def dirac_rpc_client(rpc_endpoint, host="localhost", port=18861):
    """RPC DIRAC RPC client context."""
    conn = rpyc.connect(host, port, config={"allow_public_attrs": True,
                                            "sync_request_timeout": 300})  # 5 mins
    try:
        yield conn.root.RPCClient(rpc_endpoint)
    finally:
        conn.close()


@contextmanager
def dirac_api_client(host="localhost", port=18861):
    """RPC DIRAC API client context."""
    conn = rpyc.connect(host, port, config={"allow_public_attrs": True,
                                            "sync_request_timeout": 300})
    try:
        yield conn.root.Dirac()
    finally:
        conn.close()


@contextmanager
def dirac_api_job_client(host="localhost", port=18861):
    """RPC DIRAC API client and DIRAC job handle context."""
    conn = rpyc.connect(host, port, config={"allow_public_attrs": True,
                                            "sync_request_timeout": 300})
    try:
        yield conn.root.Dirac(), conn.root.Job
    finally:
        conn.close()
