"""DIRAC RPC Client utilities."""
import logging
from contextlib import contextmanager
import rpyc

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


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
