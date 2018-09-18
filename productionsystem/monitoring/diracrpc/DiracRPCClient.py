"""DIRAC RPC Client utilities."""
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
netref_dict = rpyc.core.netref.builtin_classes_cache[('dict', '__builtin__')]
copy._deepcopy_dispatch[netref_dict] = copy._deepcopy_dict

# Used in Solid to list the DIRAC file catalogue
@contextmanager
def dirac_rpc_client(rpc_endpoint, host="localhost", port=18861):
    """RPC DIRAC RPC client context."""
    conn = rpyc.connect(host, port, config={"allow_public_attrs": True})
    try:
        yield conn.root.RPCClient(rpc_endpoint)
    finally:
        conn.close()


@contextmanager
def dirac_api_client(host="localhost", port=18861):
    """RPC DIRAC API client context."""
    conn = rpyc.connect(host, port, config={"allow_public_attrs": True})
    try:
        yield conn.root.Dirac()
    finally:
        conn.close()


@contextmanager
def dirac_api_job_client(host="localhost", port=18861):
    conn = rpyc.connect(host, port, config={"allow_public_attrs": True})
    try:
        yield conn.root.Dirac(), conn.root.Job
    finally:
        conn.close()
