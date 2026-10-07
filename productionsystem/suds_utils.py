"""
Suds utility module.

A couple of utility classes for working with certificate
authentication in suds.
"""
from __future__ import annotations

import io

import httpx
from suds.client import Client
from suds.transport import Reply
from suds.transport.https import HttpAuthenticated


class HttpCertAuthenticated(HttpAuthenticated):
    """
    Certificate authenticated http transport.
    """
    def __init__(self, cert, verify=True, **kwargs):
        """
        Initialise.

        Args:
            **kwargs: Additional options forwarded to ``HttpAuthenticated``.
            cert (tuple): Tuple containing the path to the cert file followed
                          by the path to the key file as strings.
            verify (bool/str): Whether to verify the handled request url. If a
                               string is given then this is used as the path to
                               a CA_BUNDLE file or directory with certificates of
                               trusted CAs. Note: If verify is set to a path to a
                               directory, the directory must have been processed
                               using the c_rehash utility supplied with OpenSSL.
                               This list of trusted CAs can also be specified through
                               the SSL_CERT_FILE environment variable (this may
                               cause pip to fail to validate against PyPI).

        """
        HttpAuthenticated.__init__(self, **kwargs)
        self._client = httpx.Client(cert=cert, verify=verify)

    def open(self, request):
        """
        Open the url.

        Open the url in the specified request.

        Args:
            request: Suds request object containing the URL to fetch.

        Returns:
            io.BytesIO: Buffered response body for suds to read.
        """
        # Suds expects a file-like object supporting .read(); httpx doesn't expose
        # a raw urllib3-style stream so the body is buffered into a BytesIO instead.
        response = self._client.get(request.url)
        return io.BytesIO(response.content)

    def send(self, request):
        """
        Send the request.

        Args:
            request: Suds request object containing URL, SOAP body, and headers.

        Returns:
            Reply: Suds transport reply built from the HTTP response.
        """
        response = self._client.post(request.url,
                                     content=request.message,
                                     headers=request.headers)
        return Reply(response.status_code, response.headers, response.content)


class CertClient(Client):
    """
    Certificate authenticated suds client.
    """
    def __init__(self, url, cert, verify=True, **kwargs):
        """
        Initialise.

        Sets up the underlying client with a certificate authenticated
        http transport. This can be overridden if the user provides an
        alternative transport in keyword args.

        Args:
            **kwargs: Additional suds client options, including an optional transport override.
            url (str): The url to connect to.
            cert (tuple): Tuple containing the path to the cert file followed
                          by the path to the key file as strings.
            verify (bool/str): Whether to verify the url. If a string is given
                               then this is used as the path to a CA_BUNDLE file
                               or directory with certificates of trusted CAs.
                               Note: If verify is set to a path to a directory,
                               the directory must have been processed using the
                               c_rehash utility supplied with OpenSSL. This list
                               of trusted CAs can also be specified through the
                               REQUESTS_CA_BUNDLE environment variable (this may
                               cause pip to fail to validate against PyPI).

        """
        kwargs.setdefault('transport', HttpCertAuthenticated(cert, verify))
        Client.__init__(self, url, **kwargs)
        # Shouldn't be necessary but Client is ignoring the headers kwarg
        headers = kwargs.get('headers', None)
        self.set_options(headers=headers)


__all__ = ('HttpCertAuthenticated', 'CertClient')
