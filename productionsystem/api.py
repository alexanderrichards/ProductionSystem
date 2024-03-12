"""Client side Python wrapped REST API."""
import logging
import urllib.parse as up
import requests


class JSI:
    """Object providing Pythonic access to the HTTP RESTful API used by the backend server."""

    __slots__ = ("_url", "_cert", "_verify", "_logger")

    def __init__(self, url, cert=None, verify=False):
        """
        Initialise.

        Args:
            url (str): JSI URL
            cert (str or tuple(str, str), optional):  If String, path to ssl client cert file (.pem). If Tuple,
                                                      ('cert', 'key') pair. Defaults to None.
            verify (str or bool, optional): Either a boolean, in which case it controls whether we verify
                                            the server's TLS certificate, or a string, in which case it must be
                                            a path to a CA bundle to use. Defaults to False.
        """
        if not isinstance(url, str):
            raise TypeError("Expected url to be a string, received %r" % url)
        if not isinstance(cert, (type(None), str, tuple)):
            raise TypeError("Expected cert to be either None, str or a tuple(str, str), received %r" % cert)
        if not isinstance(verify, (bool, str)):
            raise TypeError("Expected verify to be either bool or str, received %r" % verify)
        self._url = up.urlsplit(url)
        self._cert = cert
        self._verify = verify
        self._logger = logging.getLogger("JSI_API")

    def get_requests(self, request_id=None):
        """
        Get JSI requests.

        Get requests from the JSI. This method can be used both with as well as
        without the 'request_id' parameter. When provided, the method will
        return a single request from the JSI matching the id given. It will
        also return the list of parametric jobs associated with that request.
        If no request with the given id is found then an HTTPError(404) will be
        raised.

        If the method is used without any parameters then all JSI requests are
        returned. In this case the parametric jobs for each request are not
        returned.

        Note that this operation requires the user's DN to be registered in the
        JSI.

        Args:
            request_id (int, optional): The numerical id of the request to get.
                                        Defaults to None in which case all
                                        requests are returned.

        Returns:
            list: List of requests (represented as dictionaries).

        Raises:
            requests.exceptions.HTTPError: Problem with the request
            requests.exceptions.SSLError: Problem with the SSL
        """
        if not isinstance(request_id, (int, type(None))):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        path = "api/requests"
        if request_id is None:
            url = up.urlunsplit(self._url._replace(path=path))
            ret = requests.get(url, verify=self._verify, cert=self._cert)
            ret.raise_for_status()
            return ret.json()

        path += "/%d" % request_id
        url = up.urlunsplit(self._url._replace(path=path))
        ret = requests.get(url, verify=self._verify, cert=self._cert)
        ret.raise_for_status()
        request = ret.json()

        path += "/parametricjobs"
        url = up.urlunsplit(self._url._replace(path=path))
        ret = requests.get(url, verify=self._verify, cert=self._cert)
        ret.raise_for_status()
        return [dict(request, parametricjobs=ret.json())]

    def create_request(self, request):
        """
        Create JSI Request.

        Send a new request entry to the JSI. The new request will be in the
        "Requested" state until approved by an admin.

        Note that this operation requires the user's DN to be registered in the
        JSI.

        Args:
            request (dict): Dictionary representation of the request,
                            inlcuding all necessary parameters.
                            e.g. {
                                  "description": "Hello world",
                                  "parametricjobs": [
                                                     {"site": "ANY", "priority": 3},
                                                     {"site": "ANY", "priority": 2}
                                                    ]
                                 }

        Raises:
            requests.exceptions.HTTPError: Problem with the request
            requests.exceptions.SSLError: Problem with the SSL
        """
        if not isinstance(request, dict):
            raise TypeError("request parameter should be of type dict, received %r" % request)
        url = up.urlunsplit(self._url._replace(path="api/requests"))
        ret = requests.post(url, json={"request": request},
                            verify=self._verify, cert=self._cert)
        ret.raise_for_status()
        return ret

    def modify_request_status(self, request_id, status):
        if not isinstance(status, str):
            raise TypeError("status parameter should be of type str, received %r" % status)
        if not isinstance(request_id, int):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        path = "api/requests/%d" % request_id
        url = up.urlunsplit(self._url._replace(path=path))
        ret = requests.put(url, data={"status": status.capitalize()},
                           verify=self._verify, cert=self._cert)
        ret.raise_for_status()
        return ret        

    def approve_request(self, request_id):
        """
        Approve JSI request.

        Move a request into the 'Approved' state such that it gets picked up
        and submitted by the backend monitoring.

        Note that this operation requires the user's DN to be registered in the
        JSI and for them to also have admin privilages.

        Args:
            request_id (int): The numerical id of the request to approve.

        Raises:
            requests.exceptions.HTTPError: Problem with the request
            requests.exceptions.SSLError: Problem with the SSL
        """
        if not isinstance(request_id, int):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        path = "api/requests/%d" % request_id
        url = up.urlunsplit(self._url._replace(path=path))
        ret = requests.put(url, data={"status": "Approved"},
                           verify=self._verify, cert=self._cert)
        ret.raise_for_status()
        return ret

    def mark_checked(self, request_id):
        """
        Mark JSI request as checked.

        Move a request into the 'Checked' state.

        Note that this operation requires the user's DN to be registered in the
        JSI and for them to also have admin privilages.

        Args:
            request_id (int): The numerical id of the request to approve.

        Raises:
            requests.exceptions.HTTPError: Problem with the request
            requests.exceptions.SSLError: Problem with the SSL
        """
        if not isinstance(request_id, int):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        path = "api/requests/%d" % request_id
        url = up.urlunsplit(self._url._replace(path=path))
        ret = requests.put(url, data={"status": "Checked"},
                           verify=self._verify, cert=self._cert)
        ret.raise_for_status()
        return ret

    def mark_closed(self, request_id):
        """
        Mark JSI request as closed.

        Move a request into the 'Closed' state.

        Note that this operation requires the user's DN to be registered in the
        JSI and for them to also have admin privilages.

        Args:
            request_id (int): The numerical id of the request to approve.

        Raises:
            requests.exceptions.HTTPError: Problem with the request
            requests.exceptions.SSLError: Problem with the SSL
        """
        if not isinstance(request_id, int):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        path = "api/requests/%d" % request_id
        url = up.urlunsplit(self._url._replace(path=path))
        ret = requests.put(url, data={"status": "Closed"},
                           verify=self._verify, cert=self._cert)
        ret.raise_for_status()
        return ret

    def delete_request(self, request_id):
        """Delete JSI request.

        Schedules a requests for removal by placing it in the "Removing" state
        such that it gets picked up and deleted by the backend monitoring. The
        backend will also attempt to remove all associated DIRAC jobs from the
        DIRAC system as well.

        Note that this operation requires the user's DN to be registered in the
        JSI and for them to also have admin privilages.

        Args:
            request_id (int): The numerical id of the request to delete.

        Raises:
            HTTPError: Problem with the request
            SSLError: Problem with the SSL
        """
        if not isinstance(request_id, int):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        path = "api/requests/%d" % request_id
        url = up.urlunsplit(self._url._replace(path=path))
        ret = requests.delete(url, verify=self._verify, cert=self._cert)
        ret.raise_for_status()
        return ret


if __name__ == "__main__":
    # jsi = JSI("http://localhost:8080")
    # print(jsi.get_requests())
    # print(jsi.get_requests(1))
    # jsi.create_request({"description": "Hello world",
    #                     "parametricjobs": [{"site": "ANY", "priority": 3},
    #                                        {"site": "LCG.UKI-LT2-IC-HEP.uk", "priority": 2}]})
    # jsi.approve_request(4)
    # jsi.delete_request(3)

    jsi = JSI("https://lzprod01.grid.hep.ph.ic.ac.uk:8443", verify=False,
              cert=(r"C:\Users\infer\.globus\usercert.pem", r"C:\Users\infer\.globus\userkey-unenc.pem"))
    print(jsi.get_requests())
    # print(jsi.get_requests(777))
