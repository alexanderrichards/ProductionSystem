"""DIRAC RPC Server."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin
from future.utils import text_to_native_str

import logging
# from types import FunctionType
import rpyc
from rpyc.utils.server import ThreadedServer
from daemonize import Daemonize
# pylint: disable=import-error
from DIRAC.Interfaces.API.Job import Job
from DIRAC.Interfaces.API.Dirac import Dirac
from DIRAC.Core.DISET.RPCClient import RPCClient

# logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


# def autoexpose(cls):
#     """Tag all methods as exposed."""
#     for i, j in vars(cls).copy().iteritems():
#         if isinstance(j, FunctionType) and not\
#            (i.startswith('__') or i.startswith('exposed_')):
#             setattr(cls, "exposed_%s" % i, j)
#     return cls

class FixedJob(Job):
    """Fixed DIRAC Job class."""

    def setInputSandbox(self, files):
        """
        Set the input sandbox.

        This method uses if type(files) == list in DIRAC which fails for
        rpc type <netref list>. isinstance should be used instead. Solution
        is to intercept this arg and cast it to a list.
        """
        if isinstance(files, list):
            files = list(files)
        return super(FixedJob, self).setInputSandbox(files)

    def setPriority(self, priority):
        """Set the job Priority."""
        super(FixedJob, self)._setParamValue(text_to_native_str("Priority"), priority)


class FixedDirac(Dirac):
    """Fixed DIRAC Dirac class."""

    def getJobStatus(self, jobid):
        """
        Return the status of DIRAC jobs.

        This method does not have an encoder setup for type set
        let alone rpc type type <netref set>. we intercept the arg here and
        cast to a list.
        """
        if isinstance(jobid, (list, set)):
            jobid = list(jobid)
        return super(FixedDirac, self).getJobStatus(jobid)

    def rescheduleJob(self, jobid):
        """
        Reschedule the given jobs.

        This method does not have an encoder setup for type set
        let alone rpc type type <netref set>. we intercept the arg here and
        cast to a list.
        """
        if isinstance(jobid, (list, set)):
            jobid = list(jobid)
        return super(FixedDirac, self).rescheduleJob(jobid)


# Switched from inheritance to composition as the DIRAC _MagicMethods were
# not playing nicely with RPyC. using composition as a wrapper is better as
# keeps all the DIRAC stuff server side.
class RPCClientWrapper(object):
    """Fixed DIRAC RPC Client."""

    def __init__(self, *args, **kwargs):
        """Initialise."""
        self._wrapped = RPCClient(*args, **kwargs)

    def listDirectory(self, *args):
        """Expose list directory."""
        return self._wrapped.listDirectory(*args)


class DiracService(rpyc.Service):
    """DIRAC RPyC Service."""

    exposed_Job = FixedJob
    exposed_Dirac = FixedDirac
    exposed_RPCClient = RPCClientWrapper


class DiracDaemon(Daemonize):
    """DIRAC daemon to host the server."""

    def __init__(self, address, **kwargs):
        """Initialise."""
        self._address = address
        super(DiracDaemon, self).__init__(action=self.main, **kwargs)

    def main(self):
        """Daemon main."""
        # Set up the threaded server in the daemon main
        # else the file descriptors will be closed when daemon starts.
        hostname, port = self._address
        ThreadedServer(DiracService,
                       hostname=hostname,
                       port=port,
                       logger=self.logger,
                       protocol_config={"allow_public_attrs": True,
                                        "sync_request_timeout": 600,  # 10 mins
                                        "allow_pickle": True}).start()
