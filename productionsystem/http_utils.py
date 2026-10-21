"""Provide HTTP method names and TLS contexts for outbound HTTPS requests.

This module centralizes the TLS configuration used by HTTP clients that may
authenticate with an X.509 client certificate. It uses Python's standard
``ssl`` module to create contexts that can be supplied to HTTPX through its
``verify`` argument, without relying on HTTPX-specific certificate arguments.

Client authentication and server verification are independent settings. The
client certificate identifies this application to the remote server; the trust
configuration determines whether this application accepts the server's
certificate and hostname. Supplying a client certificate does not establish
trust in the server, and disabling server verification does not prevent the
client certificate from being loaded.

The module does not make HTTP requests, open network connections, or manage
HTTP client lifetimes. Certificate and trust-store files are loaded when
``create_ssl_context`` is called.

Example:
    Configure an HTTPX client with server verification and a separate client
    certificate and private key::

        import httpx

        from productionsystem.http_utils import HTTPMethod, create_ssl_context

        context = create_ssl_context(
            cert=("/etc/client/certificate.pem", "/etc/client/private-key.pem"),
            verify="/etc/client/trusted-ca-bundle.pem",
        )

        #either use the generic request method with HTTPMethod enum
        with httpx.Client(verify=context) as client:
            response = client.request(HTTPMethod.GET, "https://example.org/")
        
        # or use the convenience method directly
        with httpx.Client(verify=context) as client:
            response = client.get("https://example.org/")
"""
import os
import ssl
from enum import StrEnum


class HTTPMethod(StrEnum):
    """Represent the HTTP request methods supported by this enumeration.

    Each member is a string-valued enumeration constant whose value and string
    representation are the uppercase HTTP method token. Members can therefore
    be passed to HTTP client APIs that accept method strings, while retaining
    named constants for application code. This is a selected set of methods,
    not an exhaustive list of all HTTP methods.

    Attributes:
        GET: Request a representation of the target resource (``"GET"``).
        POST: Submit data for processing by the target resource (``"POST"``).
        PUT: Create or replace the target resource's representation (``"PUT"``).
        DELETE: Request removal of the target resource (``"DELETE"``).
        PATCH: Apply partial modifications to the target resource (``"PATCH"``).
    """

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


def create_ssl_context(cert: str | tuple[str, str] | None = None, verify: bool | str = True) -> ssl.SSLContext:
    """Build a TLS client context with optional X.509 client authentication.

    Create a new context on each call, configure server certificate verification,
    and then load a client certificate and private key if supplied. The returned
    context is suitable for the ``verify`` argument of ``httpx.Client`` or
    ``httpx.get``. No connection is attempted, so successful creation does not
    establish that a remote server is reachable or will accept the certificate.

    Args:
        cert (str | tuple[str, str] | None): Client credentials in PEM format.
            A string names a combined file containing the certificate and its
            private key. A two-element tuple names the certificate file first
            and the separate private-key file second. The certificate file may
            also contain intermediate certificates needed to build the client's
            chain. ``None`` leaves the context without client credentials.
            Paths are passed directly to ``ssl.SSLContext.load_cert_chain``;
            relative paths resolve against the current working directory.
        verify (bool | str): Server verification configuration. ``True`` uses
            ``ssl.create_default_context`` with certificate-chain and hostname
            verification enabled and OpenSSL's default trust locations. These
            locations can be influenced by ``SSL_CERT_FILE`` and
            ``SSL_CERT_DIR``. A string naming an existing directory is loaded
            as an OpenSSL hashed CA directory using ``capath``; every other
            string is treated as a CA bundle filename using ``cafile``. These
            explicit trust locations are added to the default roots, allowing
            both publicly trusted and grid-issued server certificates to verify.
            ``False`` disables both certificate-chain and
            hostname verification. Defaults to ``True``.

    Returns:
        ssl.SSLContext: A newly configured TLS client context with the requested
        trust settings and, when provided, the client certificate and private
        key. Callers own the context and may further configure it before use.

    Raises:
        OSError: A certificate, private-key file, or CA bundle cannot be opened
            or read. This includes ``FileNotFoundError`` and
            ``PermissionError``. OpenSSL may defer loading individual hashed
            CA-directory entries until a TLS handshake, so not all trust-store
            problems are detected here.
        ssl.SSLError: OpenSSL rejects the loaded TLS material, for example
            because PEM data is malformed, the private key does not match the
            certificate, or an encrypted private key cannot be decrypted.
            This exception is also a subclass of ``OSError``.
        TypeError: An argument passed to the underlying SSL APIs has an
            unsupported type, or a certificate tuple has an unsupported number
            of elements. Type annotations are not enforced at runtime.

    Warning:
        ``verify=False`` leaves connections vulnerable to server impersonation
        and interception. Use verified server certificates and the appropriate
        CA trust store for production connections, including those that use
        client-certificate authentication.

    Note:
        This helper does not accept a private-key password. When an encrypted
        key is supplied, OpenSSL may prompt interactively for its password,
        which is unsuitable for unattended daemon startup. Such callers should
        arrange secure key handling or construct a context separately with
        ``SSLContext.load_cert_chain(password=...)``.

        The default trust roots come from Python/OpenSSL, not an explicitly
        selected ``certifi`` bundle. They may differ from HTTPX's own default
        trust configuration. Existing ``ssl.SSLContext`` instances are not
        supported as input to this helper's ``verify`` parameter.

    Examples:
        Use the default server trust store without a client certificate::

            context = create_ssl_context()

        Authenticate with a combined certificate and private-key file::

            context = create_ssl_context(cert="/etc/client/combined.pem")

        Use separate client credentials and add a hashed grid CA directory
        alongside the default system roots::

            context = create_ssl_context(
                cert=("/etc/client/cert.pem", "/etc/client/key.pem"),
                verify="/etc/grid-security/certificates",
            )

            with httpx.Client(verify=context) as client:
                response = client.get("https://example.org/")
    """
    if verify is False:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    elif isinstance(verify, str):
        verify = os.path.expandvars(os.path.expanduser(verify))
        context = ssl.create_default_context()
        if os.path.isdir(verify):
            context.load_verify_locations(capath=verify)
        else:
            context.load_verify_locations(cafile=verify)
    else:
        context = ssl.create_default_context()

    if isinstance(cert, tuple):
        context.load_cert_chain(*(os.path.expandvars(os.path.expanduser(c)) for c in cert))
    elif cert is not None:
        context.load_cert_chain(os.path.expandvars(os.path.expanduser(cert)))
    return context
