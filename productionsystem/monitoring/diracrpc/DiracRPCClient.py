"""DIRAC RPC Client utilities."""
import logging
from contextlib import contextmanager
import rpyc

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


@contextmanager
def dirac_rpc_client(host="localhost", port=18861):
    """DIRAC RPC client context."""
    conn = rpyc.connect(host, port, config={"allow_public_attrs": True})
    try:
        yield conn.root.RPCClient
    finally:
        conn.close()


@contextmanager
def dirac_api_client(host="localhost", port=18861):
    """RPC DIRAC API client context."""
    conn = rpyc.connect(host, port, config={"allow_public_attrs": True})
    try:
        yield conn.root.dirac_api
    finally:
        conn.close()


@contextmanager
def dirac_api_job_client(host="localhost", port=18861):
    conn = rpyc.connect(host, port, config={"allow_public_attrs": True})
    try:
        yield conn.root.dirac_api, conn.root.Job
    finally:
        conn.close()
