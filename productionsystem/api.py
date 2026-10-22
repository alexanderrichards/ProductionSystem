"""
Client side Python wrapped REST API.

Expose request retrieval and lifecycle operations through ``JSI``. Outbound
requests use HTTPX with the client's configured TLS credentials.
"""
import logging
import urllib.parse as up
from typing import Any

import httpx

from productionsystem.sql.enums import LocalStatus
from productionsystem.http_utils import HTTPMethod, create_ssl_context

type RequestsList = list[dict[str, Any]]
type RequestDict = dict[str, Any]

__all__ = ("JSI", "LocalStatus")


class JSI:
    """
    Object providing Pythonic access to the HTTP RESTful API used by the backend server.

    Store a service URL and TLS settings for request operations. Each operation
    creates a short-lived HTTP client and returns buffered responses or decoded
    request data, so callers do not need to manage a connection pool.
    """
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

    def _request(self, method: HTTPMethod, endpoint: str, **kwargs) -> httpx.Response:
        """
        Send a buffered request using the configured X509 credentials.

        Args:
            method (HTTPMethod): HTTP verb to send.
            endpoint (str): Path replacing the path in the configured URL.
            **kwargs: Additional request options forwarded to HTTPX.

        Returns:
            httpx.Response: Buffered response, available after the client closes.
                HTTP error statuses are not checked by this helper.

        Raises:
            OSError: If TLS credentials or trust material cannot be loaded.
            httpx.RequestError: If the HTTP request cannot be completed.
        """
        with httpx.Client(verify=create_ssl_context(self._cert, self._verify)) as client:
            return client.request(method=method.value,
                                  url=up.urlunsplit(self._url._replace(path=endpoint)),
                                  **kwargs)

    def get_requests(self, request_id: int | None = None) -> RequestsList:
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
            RequestsList: List of requests (represented as dictionaries).

        Raises:
            httpx.HTTPStatusError: Problem with the request
            httpx.ConnectError: Problem with the SSL
        """
        if not isinstance(request_id, (int, type(None))):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        endpoint = "api/requests"
        if request_id is None:
            ret = self._request(HTTPMethod.GET, endpoint=endpoint)
            ret.raise_for_status()
            return ret.json()

        endpoint += f"/{request_id}"
        ret = self._request(HTTPMethod.GET, endpoint=endpoint)
        ret.raise_for_status()
        request = ret.json()

        endpoint += "/parametricjobs"
        ret = self._request(HTTPMethod.GET, endpoint=endpoint)
        ret.raise_for_status()
        return [dict(request, parametricjobs=ret.json())]

    def create_request(self, request: RequestDict) -> httpx.Response:
        """
        Create JSI Request.

        Send a new request entry to the JSI. The new request will be in the
        "Requested" state until approved by an admin.

        Note that this operation requires the user's DN to be registered in the
        JSI.

        Args:
            request (dict[str, Any]): Dictionary representation of the request,
                                      including all necessary parameters. For example::

                                          {
                                              "description": "Hello world",
                                              "parametric_jobs": [
                                                  {"site": "ANY", "priority": 3},
                                                  {"site": "ANY", "priority": 2}
                                              ]
                                          }

        Raises:
            httpx.HTTPStatusError: Problem with the request
            httpx.ConnectError: Problem with the SSL

        Returns:
            httpx.Response: Response from the create-request endpoint.
        """
        if not isinstance(request, dict):
            raise TypeError("request parameter should be of type dict, received %r" % request)
        ret = self._request(HTTPMethod.POST, endpoint="api/requests", json={"request": request})
        ret.raise_for_status()
        return ret

    def modify_request_status(self, request_id: int, status: LocalStatus) -> httpx.Response:
        """
        Change the status of an existing JSI request.

        Args:
            request_id (int): Identifier of the request to update.
            status (LocalStatus): New request status.

        Returns:
            httpx.Response: The response returned by the JSI service.

        Raises:
            TypeError: If ``request_id`` or ``status`` has an invalid type.
            httpx.HTTPStatusError: If the service rejects the update.
        """
        if not isinstance(status, LocalStatus):
            raise TypeError("status parameter should be of type LocalStatus, received %r" % status)
        if not isinstance(request_id, int):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        ret = self._request(HTTPMethod.PUT,
                            endpoint=f"api/requests/{request_id}",
                            data={"status": status.name.capitalize()})
        ret.raise_for_status()
        return ret

    def approve_request(self, request_id: int) -> httpx.Response:
        """
        Approve JSI request.

        Move a request into the 'Approved' state such that it gets picked up
        and submitted by the backend monitoring.

        Note that this operation requires the user's DN to be registered in the
        JSI and for them to also have admin privilages.

        Args:
            request_id (int): The numerical id of the request to approve.

        Raises:
            httpx.HTTPStatusError: Problem with the request
            httpx.ConnectError: Problem with the SSL

        Returns:
            httpx.Response: Response from the approve-request update.
        """
        if not isinstance(request_id, int):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        ret = self._request(HTTPMethod.PUT, endpoint=f"api/requests/{request_id}", data={"status": "Approved"})
        ret.raise_for_status()
        return ret

    def mark_checked(self, request_id: int) -> httpx.Response:
        """
        Mark JSI request as checked.

        Move a request into the 'Checked' state.

        Note that this operation requires the user's DN to be registered in the
        JSI and for them to also have admin privilages.

        Args:
            request_id (int): The numerical id of the request to approve.

        Raises:
            httpx.HTTPStatusError: Problem with the request
            httpx.ConnectError: Problem with the SSL

        Returns:
            httpx.Response: Response from the checked-status update.
        """
        if not isinstance(request_id, int):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        ret = self._request(HTTPMethod.PUT, endpoint=f"api/requests/{request_id}", data={"status": "Checked"})
        ret.raise_for_status()
        return ret

    def mark_closed(self, request_id: int) -> httpx.Response:
        """
        Mark JSI request as closed.

        Move a request into the 'Closed' state.

        Note that this operation requires the user's DN to be registered in the
        JSI and for them to also have admin privilages.

        Args:
            request_id (int): The numerical id of the request to approve.

        Raises:
            httpx.HTTPStatusError: Problem with the request
            httpx.ConnectError: Problem with the SSL

        Returns:
            httpx.Response: Response from the closed-status update.
        """
        if not isinstance(request_id, int):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        ret = self._request(HTTPMethod.PUT, endpoint=f"api/requests/{request_id}", data={"status": "Closed"})
        ret.raise_for_status()
        return ret

    def delete_request(self, request_id: int) -> httpx.Response:
        """
        Delete JSI request.

        Schedules a requests for removal by placing it in the "Removing" state
        such that it gets picked up and deleted by the backend monitoring. The
        backend will also attempt to remove all associated DIRAC jobs from the
        DIRAC system as well.

        Note that this operation requires the user's DN to be registered in the
        JSI and for them to also have admin privilages.

        Args:
            request_id (int): The numerical id of the request to delete.

        Raises:
            httpx.HTTPStatusError: Problem with the request
            httpx.ConnectError: Problem with the SSL

        Returns:
            httpx.Response: Response from the delete-request endpoint.
        """
        if not isinstance(request_id, int):
            raise TypeError("request_id parameter should be of type int, received %r" % request_id)
        ret = self._request(HTTPMethod.DELETE, endpoint=f"api/requests/{request_id}")
        ret.raise_for_status()
        return ret


if __name__ == "__main__":
    # jsi = JSI("http://localhost:8080")
    # print(jsi.get_requests())
    # print(jsi.get_requests(1))
    # jsi.create_request({"description": "Hello world",
    #                     "parametric_jobs": [{"site": "ANY", "priority": 3},
    #                                        {"site": "LCG.UKI-LT2-IC-HEP.uk", "priority": 2}]})
    # jsi.approve_request(4)
    # jsi.delete_request(3)

    jsi = JSI("https://lzprod01.grid.hep.ph.ic.ac.uk:8443",
              verify=False,
              cert=(r"C:\Users\infer\.globus\usercert.pem", r"C:\Users\infer\.globus\userkey-unenc.pem"))
    print(jsi.get_requests())
    # print(jsi.get_requests(777))
